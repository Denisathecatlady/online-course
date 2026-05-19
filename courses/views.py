from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.urls import reverse
from django.templatetags.static import static
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils.timezone import now
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Min, Prefetch, Q

import os
from types import SimpleNamespace

from .models import Course, Module, ModuleProgress, ModuleQuizProgress, CoursePlan
from payments.models import CourseAccess


# ======================================
# ACCESS HELPER
# ======================================

def has_course_admin_access(user):
    try:
        profile_role = user.profile.role
    except (AttributeError, ObjectDoesNotExist):
        profile_role = None

    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser or profile_role == "admin")
    )


def get_admin_course_access():
    return SimpleNamespace(
        bypass_module_sequencing=True,
        is_admin_access=True,
        plan=None,
        plan_id=None,
    )


def is_admin_course_access(course_access):
    return bool(getattr(course_access, "is_admin_access", False))


def require_course_access(user, course):
    if has_course_admin_access(user):
        return get_admin_course_access()

    access = CourseAccess.objects.filter(
        user=user,
        course=course,
        is_active=True
    ).first()

    if not access or not access.has_access():
        raise Http404("Přístup vypršel.")

    return access


def has_module_sequence_bypass(course_access):
    return bool(getattr(course_access, "bypass_module_sequencing", False))


MODULE_STEP_QUIZZES = {
    "konejsive-signaly-v-praxi": {
        1: {
            1: {
                "title": "Test k části 1",
                "questions": [
                    {
                        "id": "step1_q1",
                        "prompt": "Když pes odvrací hlavu, olizuje se nebo zpomaluje pohyb, nejčastěji tím:",
                        "options": [
                            {"value": "a", "label": "zvyšuje tlak na druhého psa nebo člověka"},
                            {"value": "b", "label": "se snaží situaci zklidnit a snížit napětí"},
                            {"value": "c", "label": "ukazuje, že ho situace vůbec nezajímá"},
                        ],
                        "correct": "b",
                    },
                    {
                        "id": "step1_q2",
                        "prompt": "Prvním cílem člověka při čtení konejšivých signálů je hlavně:",
                        "options": [
                            {"value": "a", "label": "rozpoznat nepohodu včas a upravit situaci"},
                            {"value": "b", "label": "okamžitě psa opravit povelem"},
                            {"value": "c", "label": "ověřit, že pes zlobí schválně"},
                        ],
                        "correct": "a",
                    },
                ],
            },
            2: {
                "title": "Test k části 2",
                "questions": [
                    {
                        "id": "step2_q1",
                        "prompt": "Proč je důležité hodnotit psí signály v kontextu celé situace?",
                        "options": [
                            {"value": "a", "label": "protože jeden signál sám o sobě nemusí stačit k pochopení významu"},
                            {"value": "b", "label": "protože jednotlivé signály nikdy nic neznamenají"},
                            {"value": "c", "label": "protože kontext je důležitý jen u štěňat"},
                        ],
                        "correct": "a",
                    },
                    {
                        "id": "step2_q2",
                        "prompt": "Když pes vysílá jemné signály nepohody, vhodná reakce člověka bývá:",
                        "options": [
                            {"value": "a", "label": "zvýšit tlak, aby si zvykl rychleji"},
                            {"value": "b", "label": "ubrat náročnost a dát psovi víc prostoru"},
                            {"value": "c", "label": "signály ignorovat, dokud nezačne vrčet"},
                        ],
                        "correct": "b",
                    },
                ],
            },
            3: {
                "title": "Závěrečný test modulu",
                "questions": [
                    {
                        "id": "step3_q1",
                        "prompt": "Který přístup nejlépe odpovídá práci s konejšivými signály v praxi?",
                        "options": [
                            {"value": "a", "label": "pes musí situaci vždy zvládnout bez úprav prostředí"},
                            {"value": "b", "label": "čteme signály psa, předcházíme přetížení a pomáháme mu uspět"},
                            {"value": "c", "label": "řešíme hlavně viditelné chování, ne příčinu"},
                        ],
                        "correct": "b",
                    },
                    {
                        "id": "step3_q2",
                        "prompt": "Po úspěšném dokončení všech tří testů v modulu 1 se má stát:",
                        "options": [
                            {"value": "a", "label": "odemkne se další část kurzu"},
                            {"value": "b", "label": "uživatel musí počkat na ruční schválení"},
                            {"value": "c", "label": "modul se vrátí na začátek"},
                        ],
                        "correct": "a",
                    },
                ],
            },
        }
    }
}


def get_module_quiz_config(course, module):
    return (
        MODULE_STEP_QUIZZES
        .get(course.slug, {})
        .get(module.order, {})
    )


def build_module_steps(user, course, module, sequence_bypass=False):
    quiz_config = get_module_quiz_config(course, module)
    quiz_progress_map = {
        progress.step: progress
        for progress in ModuleQuizProgress.objects.filter(user=user, module=module)
    }

    steps = []
    previous_quiz_passed = True

    for step_number, video_url in [
        (1, module.vimeo_embed_url1),
        (2, module.vimeo_embed_url2),
        (3, module.vimeo_embed_url3),
    ]:
        if not video_url:
            continue

        quiz = quiz_config.get(step_number)
        quiz_progress = quiz_progress_map.get(step_number)
        quiz_passed = bool(quiz_progress and quiz_progress.passed)
        is_unlocked = previous_quiz_passed or sequence_bypass

        steps.append({
            "number": step_number,
            "title": f"Video část {step_number}",
            "video_url": video_url,
            "quiz": quiz,
            "quiz_passed": quiz_passed,
            "quiz_progress": quiz_progress,
            "attempts_count": quiz_progress.attempts_count if quiz_progress else 0,
            "is_unlocked": is_unlocked,
        })

        if quiz:
            previous_quiz_passed = quiz_passed

    quiz_total_steps = sum(1 for step in steps if step["quiz"])
    quiz_passed_steps = sum(1 for step in steps if step["quiz_passed"])

    return {
        "steps": steps,
        "has_quiz_flow": bool(quiz_total_steps),
        "quiz_total_steps": quiz_total_steps,
        "quiz_passed_steps": quiz_passed_steps,
        "all_quizzes_passed": quiz_total_steps > 0 and quiz_total_steps == quiz_passed_steps,
    }


def sync_module_completion_from_quizzes(user, course, module, course_access=None):
    learning_flow = build_module_steps(
        user,
        course,
        module,
        sequence_bypass=has_module_sequence_bypass(course_access),
    )

    if not learning_flow["has_quiz_flow"]:
        return None, learning_flow

    progress, _ = ModuleProgress.objects.get_or_create(user=user, module=module)

    if learning_flow["all_quizzes_passed"] and not progress.completed:
        progress.completed = True
        progress.completed_at = now()
        progress.save(update_fields=["completed", "completed_at"])
    elif not learning_flow["all_quizzes_passed"] and progress.completed and not has_module_sequence_bypass(course_access):
        progress.completed = False
        progress.completed_at = None
        progress.save(update_fields=["completed", "completed_at"])

    return progress, learning_flow


def build_module_timeline_items(course, module, module_steps, *, module_completed=False, sequence_bypass=False):
    items = []
    pdf_inserted = False

    for step in module_steps:
        has_quiz = bool(step.get("quiz"))
        quiz_passed = bool(step.get("quiz_passed"))
        video_complete = quiz_passed if has_quiz else module_completed

        items.append({
            "kind": "video",
            "step_number": step["number"],
            "title": step["title"],
            "subtitle": module.title,
            "video_url": step["video_url"],
            "is_unlocked": bool(step["is_unlocked"]),
            "is_complete": video_complete,
        })

        if has_quiz:
            items.append({
                "kind": "quiz",
                "step_number": step["number"],
                "title": f"Krátký test k části {step['number']}",
                "subtitle": step["quiz"]["title"],
                "quiz": step["quiz"],
                "attempts_count": step["attempts_count"],
                "quiz_passed": quiz_passed,
                "is_unlocked": bool(step["is_unlocked"]),
                "is_complete": quiz_passed,
            })

            if module.pdf_file and not pdf_inserted and step["number"] == 1:
                pdf_unlocked = quiz_passed or sequence_bypass
                items.append({
                    "kind": "pdf",
                    "step_number": step["number"],
                    "title": f"Poznámky k části {step['number']}",
                    "subtitle": f"Modul {module.order} — shrnutí",
                    "href": reverse(
                        "courses:download_module_pdf",
                        kwargs={"course_slug": course.slug, "slug": module.slug},
                    ),
                    "is_unlocked": pdf_unlocked,
                    "is_complete": pdf_unlocked,
                })
                pdf_inserted = True

    if module.pdf_file and not pdf_inserted:
        items.append({
            "kind": "pdf",
            "step_number": len(module_steps) or 1,
            "title": "Studijní PDF",
            "subtitle": f"Modul {module.order} — doprovodné materiály",
            "href": reverse(
                "courses:download_module_pdf",
                kwargs={"course_slug": course.slug, "slug": module.slug},
            ),
            "is_unlocked": True,
            "is_complete": module_completed,
        })

    for position, item in enumerate(items, start=1):
        item["position"] = position

    completed_items = sum(1 for item in items if item["is_complete"])
    total_items = len(items)

    return {
        "items": items,
        "completed_items": completed_items,
        "total_items": total_items,
        "progress_percent": round((completed_items / total_items) * 100) if total_items else 0,
    }


def is_module_unlocked_for_user(user, course, module, progress_map=None, course_access=None):
    if has_module_sequence_bypass(course_access):
        return True

    previous_module = (
        course.modules
        .filter(order__lt=module.order)
        .order_by("-order")
        .first()
    )

    if previous_module is None:
        return True

    if progress_map is None:
        progress_map = {
            progress.module_id: progress
            for progress in ModuleProgress.objects.filter(user=user, module__course=course)
        }

    previous_progress = progress_map.get(previous_module.id)
    return bool(previous_progress and previous_progress.completed)


def evaluate_step_quiz(quiz, submitted_data):
    if not quiz:
        return False, False

    answers = {}

    for question in quiz["questions"]:
        answer = submitted_data.get(f"question_{question['id']}")
        if not answer:
            return False, False
        answers[question["id"]] = answer

    is_correct = all(
        answers[question["id"]] == question["correct"]
        for question in quiz["questions"]
    )
    return True, is_correct


# ======================================
# PUBLIC PAGES
# ======================================

PUBLIC_COURSE_IMAGE_PATHS = {
    "konejsive-signaly-v-praxi": "img/courses/psi-rec-konejsive-signaly-agrese-stekani.png",
    "netahani-na-voditku": "img/courses/kurz_netahani_na_voditku.png",
}


def get_public_course_image_url(course):
    image_path = PUBLIC_COURSE_IMAGE_PATHS.get(course.slug)
    if image_path:
        return static(image_path)
    if course.image:
        return course.image.url
    return static("img/shared/hero-dog.jpg")


def get_course_listing_image_url(course, index):
    image_path = f"img/courses/online_kurz_{index}.png"
    static_file = settings.BASE_DIR / "courses" / "static" / image_path
    if static_file.exists():
        return static(image_path)
    return get_public_course_image_url(course)


def _format_czech_count(value, singular, paucal, plural):
    if value % 100 in {11, 12, 13, 14}:
        form = plural
    else:
        last_digit = value % 10
        if last_digit == 1:
            form = singular
        elif last_digit in {2, 3, 4}:
            form = paucal
        else:
            form = plural
    return f"{value} {form}"

@require_GET
def home(request):
    featured_courses = list(
        Course.objects
        .filter(is_active=True)
        .annotate(
            active_plan_count=Count("plans", filter=Q(plans__is_active=True), distinct=True),
            min_price=Min("plans__price", filter=Q(plans__is_active=True)),
        )
        .prefetch_related(
            Prefetch(
                "plans",
                queryset=CoursePlan.objects.filter(is_active=True).order_by("price"),
            ),
            "modules",
        )[:2]
    )

    for index, course in enumerate(featured_courses, start=1):
        course.public_image_url = get_public_course_image_url(course)
        course.listing_image_url = get_course_listing_image_url(course, index)
        course.listing_description = (
            course.public_intro
            or course.about_text
            or course.private_intro
            or "Praktický online kurz zaměřený na klidnější soužití se psem."
        )
        active_plans = list(course.plans.all())
        course.active_plan_count = len(active_plans)
        course.access_days = min((plan.access_duration_days for plan in active_plans), default=None)
        course.module_count = course.modules.count()
        course.meta_access = (
            _format_czech_count(course.access_days, "den", "dny", "dní")
            if course.access_days
            else None
        )
        course.meta_modules = (
            _format_czech_count(course.module_count, "modul", "moduly", "modulů")
            if course.module_count
            else None
        )
        course.meta_variants = (
            _format_czech_count(course.active_plan_count, "varianta", "varianty", "variant")
            if course.active_plan_count
            else None
        )

    plans = (
        CoursePlan.objects
        .filter(is_active=True)
        .select_related("course")
        .order_by("-price")
    )

    return render(request, "courses/home.html", {
        "courses": featured_courses,
        "plans": plans,
    })


@require_GET
def course_detail_public(request, slug):
    course = get_object_or_404(
        Course,
        slug=slug,
        is_active=True
    )
    course.public_image_url = get_public_course_image_url(course)

    plans = course.plans.filter(is_active=True)

    return render(request, "courses/course_detail_public.html", {
        "course": course,
        "plans": plans,
    })


def about(request):
    return render(request, "courses/about.html")


def about_us(request):
    return redirect("courses:trainings")


def cemu_se_venujeme(request):
    return redirect("courses:trainings")


def nase_filozofie(request):
    return render(request, "courses/nase_filozofie.html")


def moje_vzdelani(request):
    return render(request, "courses/moje_vzdelani.html")


def muj_pribeh(request):
    return render(request, "courses/muj_pribeh.html", {
        "hide_site_footer": True,
    })


def contact(request):
    contact_cards = [
        {
            "title": "Telefon",
            "value": "+420 608 163 824",
            "href": "tel:+420608163824",
            "theme": "sage",
            "icon": "phone",
        },
        {
            "title": "E-mail",
            "value": "info@calmdog.cz",
            "href": "mailto:info@calmdog.cz",
            "theme": "accent",
            "icon": "mail",
        },
        {
            "title": "Lokalita",
            "value": "Česká republika",
            "href": "",
            "theme": "dark",
            "icon": "pin",
        },
    ]

    team_members = [
        {
            "role": "Zakladatelka & hlavní trenérka",
            "name": "Ing. Andrea Zoulová",
            "subtitle": "Dog Behavior Specialist",
            "description": (
                "Andreu zajímá hlavně to, proč se pes chová tak, jak se chová. "
                "Zaměřuje se na psí komunikaci, konejšivé signály, reaktivitu "
                "a práci s emocemi u psů i jejich lidí. Vzdělávání staví na "
                "etických principech a respektu k potřebám zvířat."
            ),
            "image_url": static("img/contact/andrea_zoulova_portret.png"),
            "accent_class": "contact-team-card-sage",
        },
        {
            "role": "Trenérka & technická podpora",
            "name": "Bc. Denisa Zoulová",
            "subtitle": "Junior Dog Behavior Specialist · Technical Support",
            "description": (
                "Denisa se stará o to, aby všechno fungovalo od online kurzů po "
                "zákaznickou podporu. Zároveň se věnuje tréninkům pod vedením Andrey "
                "a pomáhá s komunikačními procházkami a socializačními aktivitami."
            ),
            "image_url": static("img/contact/denisa_zoulova_portret.png"),
            "accent_class": "contact-team-card-accent",
        },
    ]

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        if not all([name, email, subject, message]):
            messages.error(request, "Vyplňte prosím všechna pole.")
        else:
            recipient = "info@calmdog.cz"
            body = (
                f"Jmeno: {name}\n"
                f"E-mail: {email}\n\n"
                f"Predmet: {subject}\n\n"
                f"Zprava:\n{message}"
            )

            try:
                email_message = EmailMessage(
                    subject=f"Kontakt z webu: {subject}",
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or recipient,
                    to=[recipient],
                    reply_to=[email],
                )
                email_message.send(fail_silently=False)
                messages.success(request, "Zpráva byla odeslána.")
                return redirect("courses:contact")
            except Exception:
                messages.error(request, "Zprávu se nepodařilo odeslat. Zkuste prosím e-mail nebo telefon.")

    return render(request, "courses/contact.html", {
        "contact_cards": contact_cards,
        "team_members": team_members,
    })


def trainings(request):
    trainings_data = get_trainings_data()

    return render(request, "courses/trainings.html", {
        "trainings": trainings_data,
    })


def get_trainings_data():
    return [
        {
            "title": "Individuální konzultace problémového chování psa",
            "summary": "Porozumění příčině problémového chování a návrh vhodného řešení na míru.",
            "image": "img/trainings/treninky_1.png",
            "highlights": [
                "Porozumíme příčině problémového chování a navrhneme řešení.",
                "Naučíme se komunikovat se psem.",
                "Uspokojíme potřeby psa.",
            ],
            "duration": "1 h",
            "capacity": "1 pes",
            "price": "1 500 Kč",
        },
        {
            "title": "Psí řeč: konejšivé signály, signály agrese, štěkání",
            "summary": "Trénink zaměřený na čtení psí komunikace a lepší porozumění psím potřebám.",
            "image": "img/trainings/treninky_2.png",
            "highlights": [
                "Naučíme se pozorovat a rozumět psí komunikaci.",
                "Naučíme se komunikovat se psem.",
                "Uspokojíme psí potřeby.",
            ],
            "duration": "1 h",
            "capacity": "1 pes",
            "price": "1 500 Kč",
        },
        {
            "title": "Chůze na volném vodítku",
            "summary": "Klidnější a funkční procházky bez tahání na vodítku.",
            "image": "img/trainings/treninky_3.png",
            "highlights": [
                "Naučíme psa netahat na vodítku.",
                "Uspokojíme psí potřeby.",
                "Naučíme se psí řeč.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Komunikační / socializační procházky",
            "summary": "Podpora psů, kteří potřebují zvládnout kontakt s jinými psy klidněji.",
            "image": "img/trainings/treninky_4.png",
            "highlights": [
                "Pochopíme příčinu reaktivity na psy.",
                "Pomůžeme psu zvládnout kontakt s ostatními psy.",
                "Naučíme psa těšit se z přítomnosti jiných psů.",
            ],
            "duration": "1 h",
            "capacity": "2–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Socializační aktivity",
            "summary": "Bezpečné seznamování psa s prostředím, které mu dělá potíže.",
            "image": "img/trainings/treninky_5.png",
            "highlights": [
                "Pochopíme příčinu reaktivity a bázlivosti vašeho psa.",
                "Pomůžeme psu zvládnout kontakt s obtížným prostředím.",
                "Vyměníme strach za zvědavost.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Aktivity zvyšující sebevědomí psa / snižující stres",
            "summary": "Činnosti, které pomáhají psovi lépe zvládat tlak a budovat jistotu.",
            "image": "img/trainings/treninky_6.png",
            "highlights": [
                "Budeme zvyšovat sebevědomí psa a snižovat stres.",
                "Budeme pečovat o psí pohybový aparát.",
                "Naučíme se psí řeč.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
    ]


def gdpr(request):
    return render(request, "courses/gdpr.html")


def privacy_policy(request):
    return render(request, "courses/privacy_policy.html")


def terms(request):
    return render(request, "courses/terms.html")


def cookies_view(request):
    return render(request, "pages/cookies.html")


# ======================================
# COURSE DASHBOARD (PRIVATE)
# ======================================

@login_required
@require_GET
@never_cache
def course_dashboard(request, slug):

    course = get_object_or_404(Course, slug=slug)

    # 🔐 kontrola přístupu včetně expirace
    course_access = require_course_access(request.user, course)

    modules = list(course.modules.all())

    progress_map = {
        progress.module_id: progress
        for progress in ModuleProgress.objects.filter(user=request.user, module__in=modules)
    }

    for module in modules:
        synced_progress, learning_flow = sync_module_completion_from_quizzes(
            request.user,
            course,
            module,
            course_access=course_access,
        )
        if synced_progress:
            progress_map[module.id] = synced_progress

        module.requires_quiz_flow = learning_flow["has_quiz_flow"]
        module.quiz_total_steps = learning_flow["quiz_total_steps"]
        module.quiz_passed_steps = learning_flow["quiz_passed_steps"]

    for module in modules:
        module_progress = progress_map.get(module.id)
        module.is_completed = bool(module_progress and module_progress.completed)
        module.is_unlocked = is_module_unlocked_for_user(
            request.user,
            course,
            module,
            progress_map=progress_map,
            course_access=course_access,
        )

        if not module.is_unlocked:
            previous_module = (
                course.modules
                .filter(order__lt=module.order)
                .order_by("-order")
                .first()
            )
            module.locked_reason = (
                f"Nejdříve dokončete modul {previous_module.order}."
                if previous_module else "Modul je zatím zamčený."
            )
        elif (
            has_module_sequence_bypass(course_access)
            and not is_admin_course_access(course_access)
            and module.requires_quiz_flow
        ):
            module.locked_reason = "Máte zachované odemčení z původního průchodu kurzem. Testy si můžete doplnit postupně."
        elif module.requires_quiz_flow:
            module.locked_reason = f"{module.quiz_passed_steps} / {module.quiz_total_steps} testů splněno"
        else:
            module.locked_reason = ""

    total_modules = len(modules)
    completed_modules = sum(1 for module in modules if module.is_completed)
    current_module = next(
        (module for module in modules if module.is_unlocked and not module.is_completed),
        None,
    )
    if current_module is None and modules:
        current_module = modules[-1]

    progress_percent = (
        int((completed_modules / total_modules) * 100)
        if total_modules else 0
    )
    duration_weeks = None
    if course_access.plan_id and course_access.plan and course_access.plan.access_duration_days:
        duration_weeks = max(1, course_access.plan.access_duration_days // 7)

    return render(request, "courses/course_dashboard.html", {
        "course": course,
        "course_access": course_access,
        "modules": modules,
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "progress_percent": progress_percent,
        "current_module": current_module,
        "duration_weeks": duration_weeks,
        "hide_site_navbar": True,
        "hide_site_footer": True,
    })


# ======================================
# MODULE DETAIL
# ======================================

@login_required
@require_GET
@never_cache
@xframe_options_sameorigin
def module_detail(request, course_slug, slug):

    course = get_object_or_404(Course, slug=course_slug)

    course_access = require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        course=course,
        slug=slug
    )

    synced_progress, learning_flow = sync_module_completion_from_quizzes(
        request.user,
        course,
        module,
        course_access=course_access,
    )

    progress_map = {
        progress.module_id: progress
        for progress in ModuleProgress.objects.filter(user=request.user, module__course=course)
    }
    if synced_progress:
        progress_map[module.id] = synced_progress

    if not is_module_unlocked_for_user(
        request.user,
        course,
        module,
        progress_map=progress_map,
        course_access=course_access,
    ):
        messages.error(request, "Tento modul se odemkne až po dokončení předchozího modulu.")
        return redirect("courses:course_dashboard", slug=course.slug)

    module_progress = progress_map.get(module.id)
    sequence_bypass = has_module_sequence_bypass(course_access)
    timeline = build_module_timeline_items(
        course,
        module,
        learning_flow["steps"],
        module_completed=bool(module_progress and module_progress.completed),
        sequence_bypass=sequence_bypass,
    )
    next_module = (
        course.modules
        .filter(order__gt=module.order)
        .order_by("order")
        .first()
    )
    next_module_unlocked = (
        bool(next_module) and is_module_unlocked_for_user(
            request.user,
            course,
            next_module,
            progress_map=progress_map,
            course_access=course_access,
        )
    )

    return render(request, "courses/module_detail.html", {
        "course": course,
        "module": module,
        "module_progress": module_progress,
        "module_steps": learning_flow["steps"],
        "timeline_items": timeline["items"],
        "timeline_completed_items": timeline["completed_items"],
        "timeline_total_items": timeline["total_items"],
        "timeline_progress_percent": timeline["progress_percent"],
        "next_module": next_module,
        "next_module_unlocked": next_module_unlocked,
        "has_step_quiz_flow": learning_flow["has_quiz_flow"],
        "quiz_total_steps": learning_flow["quiz_total_steps"],
        "quiz_passed_steps": learning_flow["quiz_passed_steps"],
        "has_module_sequence_bypass": sequence_bypass,
        "hide_site_navbar": True,
        "hide_site_footer": True,
    })


# ======================================
# PDF DOWNLOAD
# ======================================

@login_required
@require_GET
@never_cache
def download_module_pdf(request, course_slug, slug):

    course = get_object_or_404(Course, slug=course_slug)

    require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        course=course,
        slug=slug
    )

    if not module.pdf_file:
        raise Http404("PDF není k dispozici.")

    try:
        file_name = module.pdf_file.name.split("/")[-1]
        return FileResponse(
            module.pdf_file.open("rb"),
            as_attachment=True,
            filename=file_name,
            content_type="application/pdf",
        )
    except (FileNotFoundError, OSError):
        raise Http404("Soubor nebyl nalezen.")


# ======================================
# MODULE PROGRESS
# ======================================

@login_required
@require_POST
def toggle_module_completion(request, course_slug, module_id):

    course = get_object_or_404(Course, slug=course_slug)

    course_access = require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        id=module_id,
        course=course
    )

    learning_flow = build_module_steps(
        request.user,
        course,
        module,
        sequence_bypass=has_module_sequence_bypass(course_access),
    )
    if learning_flow["has_quiz_flow"]:
        messages.error(
            request,
            "Tento modul se dokončí automaticky po úspěšném splnění všech testů.",
        )
        return redirect("courses:module_detail", course_slug=course.slug, slug=module.slug)

    progress, _ = ModuleProgress.objects.get_or_create(
        user=request.user,
        module=module
    )

    progress.completed = not progress.completed
    progress.completed_at = now() if progress.completed else None
    progress.save()

    return redirect(
        "courses:module_detail",
        course_slug=course.slug,
        slug=module.slug
    )


@login_required
@require_POST
def submit_module_quiz(request, course_slug, slug, step):
    course = get_object_or_404(Course, slug=course_slug)

    course_access = require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        course=course,
        slug=slug,
    )

    progress_map = {
        progress.module_id: progress
        for progress in ModuleProgress.objects.filter(user=request.user, module__course=course)
    }

    if not is_module_unlocked_for_user(
        request.user,
        course,
        module,
        progress_map=progress_map,
        course_access=course_access,
    ):
        messages.error(request, "Tento modul je zatím zamčený.")
        return redirect("courses:course_dashboard", slug=course.slug)

    learning_flow = build_module_steps(
        request.user,
        course,
        module,
        sequence_bypass=has_module_sequence_bypass(course_access),
    )
    selected_step = next(
        (step_data for step_data in learning_flow["steps"] if step_data["number"] == step),
        None,
    )

    if not selected_step or not selected_step["quiz"]:
        raise Http404("Test pro tento krok neexistuje.")

    if not selected_step["is_unlocked"]:
        messages.error(request, "Nejdříve dokončete test z předchozí části modulu.")
        return redirect(
            f"{reverse('courses:module_detail', kwargs={'course_slug': course.slug, 'slug': module.slug})}#step-{step}"
        )

    answers_complete, is_correct = evaluate_step_quiz(selected_step["quiz"], request.POST)

    if not answers_complete:
        messages.error(request, "Odpovězte prosím na všechny otázky v testu.")
        return redirect(
            f"{reverse('courses:module_detail', kwargs={'course_slug': course.slug, 'slug': module.slug})}#step-{step}"
        )

    quiz_progress, _ = ModuleQuizProgress.objects.get_or_create(
        user=request.user,
        module=module,
        step=step,
    )
    quiz_progress.attempts_count += 1

    if is_correct:
        if not quiz_progress.passed:
            quiz_progress.passed = True
            quiz_progress.passed_at = now()
        quiz_progress.save(update_fields=["attempts_count", "passed", "passed_at"])

        synced_progress, refreshed_flow = sync_module_completion_from_quizzes(
            request.user,
            course,
            module,
            course_access=course_access,
        )

        if synced_progress and synced_progress.completed:
            messages.success(
                request,
                "Test je splněný. Máte hotový celý modul a další modul se právě odemkl.",
            )
        else:
            next_step = next(
                (
                    step_data for step_data in refreshed_flow["steps"]
                    if step_data["number"] == step + 1 and step_data["is_unlocked"]
                ),
                None,
            )
            if next_step:
                messages.success(
                    request,
                    f"Test je splněný. Odemkla se {next_step['title'].lower()}.",
                )
            else:
                messages.success(request, "Test je splněný.")
    else:
        if quiz_progress.passed:
            quiz_progress.save(update_fields=["attempts_count"])
            messages.success(request, "Tento test už máte splněný.")
        else:
            quiz_progress.save(update_fields=["attempts_count"])
            messages.error(request, "Tentokrát to nevyšlo. Zkuste test znovu, počet pokusů není omezený.")

    return redirect(
        f"{reverse('courses:module_detail', kwargs={'course_slug': course.slug, 'slug': module.slug})}#step-{step}"
    )
