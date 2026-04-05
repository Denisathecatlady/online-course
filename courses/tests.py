from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, Module, ModuleProgress, ModuleQuizProgress
from courses.views import MODULE_STEP_QUIZZES


class PublicPagesTests(TestCase):
    def test_trainings_page_renders(self):
        response = self.client.get(reverse("courses:trainings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Praktické tréninky pro klidnější soužití se psem")
        self.assertContains(response, "Individuální konzultace problémového chování psa")

    def test_about_us_page_renders(self):
        response = self.client.get(reverse("courses:about_us"))

        self.assertRedirects(response, reverse("courses:cemu_se_venujeme"))

    def test_about_subpages_render(self):
        for route_name in [
            "courses:cemu_se_venujeme",
            "courses:nase_filozofie",
            "courses:moje_vzdelani",
            "courses:muj_pribeh",
        ]:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)


class ModuleQuizFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="testpass123",
        )
        self.client.force_login(self.user)

        self.course = Course.objects.create(
            title="Konejšivé signály v praxi",
            slug="konejsive-signaly-v-praxi",
            is_active=True,
        )
        self.module_one = Module.objects.create(
            course=self.course,
            order=1,
            title="Úvod do konejšivých signálů",
            slug="uvod-do-konejsivych-signalu",
            vimeo_embed_url1="https://player.vimeo.com/video/100001",
            vimeo_embed_url2="https://player.vimeo.com/video/100002",
            vimeo_embed_url3="https://player.vimeo.com/video/100003",
        )
        self.module_two = Module.objects.create(
            course=self.course,
            order=2,
            title="Pokračování kurzu",
            slug="pokracovani-kurzu",
            vimeo_embed_url1="https://player.vimeo.com/video/100004",
        )

    def _quiz_payload(self, step):
        quiz = MODULE_STEP_QUIZZES[self.course.slug][1][step]
        return {
            f"question_{question['id']}": question["correct"]
            for question in quiz["questions"]
        }

    def test_second_module_is_locked_until_first_module_is_completed(self):
        with patch("courses.views.require_course_access", return_value=True):
            response = self.client.get(
                reverse(
                    "courses:module_detail",
                    kwargs={"course_slug": self.course.slug, "slug": self.module_two.slug},
                )
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("courses:course_dashboard", kwargs={"slug": self.course.slug}),
        )

    def test_cannot_submit_second_quiz_before_passing_first(self):
        with patch("courses.views.require_course_access", return_value=True):
            response = self.client.post(
                reverse(
                    "courses:submit_module_quiz",
                    kwargs={
                        "course_slug": self.course.slug,
                        "slug": self.module_one.slug,
                        "step": 2,
                    },
                ),
                data=self._quiz_payload(2),
                follow=True,
            )

        self.assertContains(response, "Nejdřív dokonči test z předchozí části modulu.")
        self.assertFalse(
            ModuleQuizProgress.objects.filter(
                user=self.user,
                module=self.module_one,
                step=2,
            ).exists()
        )

    def test_passing_all_three_quizzes_unlocks_second_module(self):
        with patch("courses.views.require_course_access", return_value=True):
            for step in (1, 2, 3):
                response = self.client.post(
                    reverse(
                        "courses:submit_module_quiz",
                        kwargs={
                            "course_slug": self.course.slug,
                            "slug": self.module_one.slug,
                            "step": step,
                        },
                    ),
                    data=self._quiz_payload(step),
                    follow=True,
                )
                self.assertEqual(response.status_code, 200)

        module_progress = ModuleProgress.objects.get(user=self.user, module=self.module_one)
        self.assertTrue(module_progress.completed)
        self.assertEqual(
            ModuleQuizProgress.objects.filter(
                user=self.user,
                module=self.module_one,
                passed=True,
            ).count(),
            3,
        )

        with patch("courses.views.require_course_access", return_value=True):
            unlocked_response = self.client.get(
                reverse(
                    "courses:module_detail",
                    kwargs={"course_slug": self.course.slug, "slug": self.module_two.slug},
                )
                )
            self.assertEqual(unlocked_response.status_code, 200)

    def test_existing_user_with_bypass_keeps_next_module_unlocked(self):
        with patch(
            "courses.views.require_course_access",
            return_value=SimpleNamespace(bypass_module_sequencing=True),
        ):
            response = self.client.get(
                reverse(
                    "courses:module_detail",
                    kwargs={"course_slug": self.course.slug, "slug": self.module_two.slug},
                )
            )

        self.assertEqual(response.status_code, 200)
