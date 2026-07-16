# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: CalmDog

Django 5.2 e-learning + e-shop platform for dog training. Two branches: `main` (production, `calmdog` Render service) and `staging` (preview, `calmdog-preview` Render service, own database). `refactor-cart-system` was the old long-lived dev branch — fast-forward-merged into `main` and retired; don't create work off it. Test changes on `staging` first, then promote (cherry-pick or merge) to `main`.

Stack: Python 3.10, Django 5.2, SQLite (local) / PostgreSQL (Render.com), Stripe Checkout, Cloudflare R2, WhiteNoise, Bootstrap 5 + custom CSS design system.

---

## Commands

```bash
# Run development server
python3 manage.py runserver

# Apply migrations
python3 manage.py migrate

# Create migration after model change
python3 manage.py makemigrations

# Django shell
python3 manage.py shell

# Collect static files (production)
python3 manage.py collectstatic --noinput
```

No test runner is configured — `tests.py` files exist but are empty.

---

## Architecture

### Apps

| App | Namespace | URL prefix | Responsibility |
|-----|-----------|------------|----------------|
| `courses` | `courses` | `/` | Homepage, editorial pages, e-learning (modules, quizzes, progress) |
| `payments` | `payments` | `/kurzy/` | Course listing/detail, cart, Stripe checkout, order/invoice, CourseAccess |
| `shop` | `shop` | `/voditka/` | Physical product (leash) variants, colors, stock |
| `accounts` | `accounts` | `/ucty/` | Auth, profile, my-courses |
| `hotel` | `hotel` | `/hotel/` | Hotel landing page, reservation interest form, iCal availability |
| `trainings` | `trainings` | `/moje-treninky/` | Training-slot booking/reservations; per-trainer Google Calendar OAuth (push bookings out + import availability in — see dedicated section below) |

Static files (CSS, images) live in `courses/static/` and are served via WhiteNoise. Each app with its own CSS has it in `{app}/static/{app}/css/`.

### Key data flow: purchase → access

1. **Cart** — `shop.CartItem` (session-based via `payments/services/cart.py`, keyed on user)
2. **Checkout** — Stripe Checkout session created in `payments/views.py:checkout()`; cart items become `Order` + `OrderItem` records
3. **Webhook** (`/payments/stripe-webhook/`) — on `checkout.session.completed`:
   - Reduces `ProductVariant.stock` with `select_for_update()` inside a transaction
   - Creates Packeta shipment (if physical items) via `payments/services/packeta.py`
   - Creates/finds `User` by email, creates `CourseAccess` records
   - Generates PDF invoice via `payments/services/invoice.py` (ReportLab), saves to R2
   - Sends confirmation email with invoice attached
   - For `Order.ShippingMethod.ZASILKOVNA` orders, also sends an internal notification email to `info@calmdog.cz` (`_send_order_notification_email` in `payments/views.py`) with the order summary and the Packeta label PDF attached (if the shipment was created) — lets the shop know a physical order arrived without checking the admin. Fires even if Packeta itself failed (includes the error text instead of a tracking number) so a failure isn't silently missed.
   - Both this internal email and the customer-facing confirmation email list each `shop` line item via the shared `_variant_description(variant)` helper, which appends color/length/type (`ProductVariant.color`/`length`/`type`) after the product name — without it, two orders for the same product in different colors/lengths were indistinguishable in the email body.

Checkout is guest-friendly (no login required) — `payments/templates/payments/checkout_form.html` prefills email/name fields from `cart.<field>` first, falling back to `user.<field>` **only inside `{% if user.is_authenticated %}`**. Don't reintroduce a bare `{{ x|default:user.email }}`-style filter default — `AnonymousUser` has no `email`/`first_name`/`last_name` attributes, and unlike a normal failed variable lookup in `{{ }}`, a `VariableDoesNotExist` raised while resolving a *filter argument* is not swallowed — it crashes the page with a 500 for every guest checkout.

### CourseAccess & module sequencing

`CourseAccess` (payments app) links a user to a `Course` + `CoursePlan`. Key fields:
- `expires_at` — set **only on creation** (guard: `self.pk is None`). Never overwrite on save.
- `bypass_module_sequencing` — skips sequential quiz requirement; set `True` for legacy/admin users.
- `has_access()` — checks `is_active` + `expires_at`.

Module quiz sequencing logic lives in `courses/views.py:build_module_steps()`. Quiz questions are hardcoded in `MODULE_STEP_QUIZZES` dict (keyed by `course.slug → module.order → step_number`). To add quizzes for a new course/module, extend this dict.

### Course marketing content

`COURSE_MARKETING_CONTENT` dict in `payments/views.py` holds rich marketing data (hero text, metrics, curriculum, etc.) keyed by `course.slug`. If a course slug has no entry, `course_detail` falls back to a generic template branch. `Course.coming_soon = True` disables all "Add to cart" buttons.

### Packeta / Zásilkovna

`payments/services/packeta.py` calls the legacy Zásilkovna XML API (`https://www.zasilkovna.cz/api/rest`). **Despite the naming/docstrings this is NOT SOAP** — no `soap:Envelope`/`soap:Body` wrapper; the request root element is the method name directly (`<createPacket>...</createPacket>`). Wrapping it in a SOAP envelope makes Packeta fail to parse the request (`RequestError: An error occured parsing request.`) — a bug that shipped silently for a long time because it only surfaces in `PACKETA_MODE=live`, never `mock`. Functions:
- `create_packet(order)` — creates shipment, returns `{packet_id, tracking_number}`
- `get_packet_label_pdf(packet_id)` — returns raw PDF bytes (base64-decoded from API)
- `get_packet_status(packet_id)` — returns status dict

Error responses use `<status>fault</status>` (or `error`) with the code in `<fault>` and message in `<string>`; a `PacketAttributesFault` includes a `<detail>` element with the specific invalid field — `_soap_call()` includes both in the raised `PacketaError` message so admin retry actions show the real reason without needing Render log access.

`PACKETA_ESHOP_NAME` (env var, defaults to `"CalmDog"` in code) must **exactly match** the "Označení" (internal identifier) field configured for the sender at client.packeta.com → Odesílatelé — a mismatch causes `PacketAttributesFault: Sender is not given`. Confirmed working value: `CalmDog.cz`.

Set `PACKETA_MODE=mock` in env to skip real API calls during development — `render.yaml` currently has `calmdog-preview` on `live` (for real-shipment testing), not `mock`. Admin (`payments/admin.py` `OrderAdmin`) has actions to retry shipment creation, retry label download, and resend the confirmation email — all surface their real error message via `messages.error`, no log-digging needed.

**Shipping price** is a literal set in `payments/views.py:shipping()` (Zásilkovna 99 Kč / Kurýr 119 Kč) — not derived from Packeta's own pricing, so update it by hand if Packeta's price list changes. Orders whose `items_total` reaches `Order.FREE_SHIPPING_THRESHOLD` (1500 Kč; check via `Order.qualifies_for_free_shipping`) get free shipping regardless of method.

### File storage (R2 / S3)

When `USE_S3_STORAGE=1`, all `FileField`/`ImageField` uploads go to Cloudflare R2 via `django-storages`. **Always use `.open("rb")` instead of `.path`** when reading stored files — `.path` breaks on R2. Example:
```python
return FileResponse(order.invoice_pdf.open("rb"), ...)
```

`render.yaml` currently has `USE_S3_STORAGE=0` on **both** `calmdog` and `calmdog-preview`, so invoices/Packeta labels (`private_storage`, `PRIVATE_MEDIA_ROOT`) live on Render's local disk — which is wiped on every redeploy/restart. Any view that serves one of these files must check `storage.exists(name)` and regenerate on demand if missing (invoice PDF: `generate_invoice_pdf(order)`), or it 500s with `FileNotFoundError`. Existing examples: `payments/admin.py` `download_invoice`, `accounts/views.py` `download_invoice`.

### Design system (CSS)

- Base design tokens: `courses/static/css/base.css` — CSS variables (`--sage`, `--sage-deep`, `--text-dark`, etc.), `.btn-sage`, `.btn-outline-sage`, navbar
- Page-specific CSS files loaded via `{% block extra_css %}`
- Design patterns: kicker with `::before` line, Playfair Display headings, `#f5f5f0` background, `border-radius: 28px` cards, sage green (`#5f766b`, `#6f8780`) primary color
- Body text color: `#2f3e3a` (dark forest green, NOT pure black)

### Administrace (Django admin)

Vlastní **verzovaný** design-systém administrace (styl „moderní SaaS": Stripe/Linear).
Nahradil dřívější DB-téma `django-admin-interface` (odebráno z `INSTALLED_APPS` i
`requirements.txt`; migrace `payments/0016_calmdog_admin_theme` je nyní no-op).

- **Barvy:** primární `#0E4C66` (navy), sekundární `#10B0C8` (tyrkys). Písmo Open Sans.
- **CSS:** `courses/static/admin/css/calmdog_admin.css` — jeden soubor, přepisuje CSS
  proměnné Django adminu (`--primary`, `--header-bg`, `--button-bg`…) + komponenty.
  Motiv je záměrně jen světlý (přepínač světlý/tmavý je skrytý).
- **Šablony:** `templates/admin/base_site.html` (načte CSS + font), `index.html`
  (dashboard: KPI karty + graf + rozcestník), `nav_sidebar.html` (navigace ve skupinách).
  Vlastní admin šablony **musí dědit z `admin/base_site.html`**, jinak se CSS nenačte.
- **Navigace/dashboard/ikony:** `courses/templatetags/calmdog_admin.py`.
  - `_NAV_GROUPS` = mapování modelů do sekcí (Prodej, Sklad, Akademie, Rezervace,
    Klienti, Marketing, Systém). Nový model se přidá do příslušné skupiny (nezařazené
    spadnou do „Ostatní", takže nikdy nezmizí).
  - `dashboard_metrics()` = KPI karty + data grafu. `_ICONS` = inline SVG (bez CDN).
- **Barevné štítky stavů:** jediný sdílený helper `config/admin_ui.py:badge(text, variant)`
  → `<span class="cd-badge cd-badge--{variant}">`; varianty `success|warning|danger|muted|info|primary`.
  Používej ho místo inline stylů (importuje se v `*/admin.py`).
- **Názvy sekcí** v menu = `verbose_name` v `*/apps.py` (česky). Modely mají české
  `verbose_name` v `Meta`.

### Settings / env vars

| Variable | Purpose |
|----------|---------|
| `DJANGO_DEBUG` | `1` for debug |
| `USE_S3_STORAGE` | `1` to enable R2 |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` | Cloudflare R2 credentials |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe |
| `PACKETA_API_PASSWORD`, `PACKETA_WIDGET_API_KEY` | Zásilkovna live |
| `PACKETA_MODE` | `mock` or `live` |
| `PACKETA_DEFAULT_WEIGHT` | Default shipment weight in kg (default `0.5`) |
| `HOTEL_ICAL_URL` | iCal feed URL for hotel availability |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP relay (Brevo, `smtp-relay.brevo.com`, port 587, TLS). Not declared in `render.yaml` — set manually per Render service. Brevo's "Authorized IPs" security feature (Settings → Security) must have SMTP keys deactivated or Render's outbound IP authorized, otherwise sends fail with `535`/`525 Unauthorized IP address`. |
| `DATABASE_URL` | PostgreSQL on Render; SQLite used locally if unset |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth for allauth "Sign in with Google" (customer login, `/ucty/google/login/callback/`). **Separate OAuth client** from `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` below — don't reuse one for the other, different redirect URI and consent scope. |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | Google Calendar OAuth for the `trainings` app's per-trainer calendar sync (`/moje-treninky/google/callback/`). Same credential pair also gates reading availability (see Trainings app section below) — no extra scope/re-consent needed. |
| `TRAININGS_IMPORT_HORIZON_DAYS` | How many days ahead `import_availability_from_google` looks when reading trainer availability calendars (default `60`). |
| `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL` | **Mandatory whenever `DJANGO_DEBUG` is unset/`0`** — `config/settings.py` raises `RuntimeError` at import time (before any view/command code runs) if either falls back to its dev sentinel value while not in debug mode. This applies to **every** Render service, including cron jobs — not just the web services. Must be declared (`sync: false`) in every service's `envVars` block in `render.yaml` *and* have its value filled in manually per-service in the Render dashboard (`sync: false` doesn't carry a value across services). |

### Hotel app

Landing page + reservation interest form. Availability fetched from iCal URL (`HOTEL_ICAL_URL`) via `hotel/services/calendar.py` and exposed at `/hotel/api/volne-terminy/` as JSON. Uses Flatpickr.js for date selection.

### Trainings app — Google Calendar availability import

`AvailabilityWindow` (trainer-authored time block) → `AvailabilityWindow.generate_slots()` materializes it into bookable `TrainingSlot` rows. Historically these windows were typed by hand in admin; they can now also be **imported automatically from Google Calendar** so a trainer can just drag-create an event instead:

- **`AvailabilityCalendar`** (`trainings/models.py`) maps one `(trainer, location)` pair to a dedicated Google Calendar ID (`google_calendar_id`) + `default_slot_minutes`. Each location needs its own calendar — **separate from** the trainer's main calendar that booking events get pushed to (`Trainer.google_calendar_id`, default `"primary"`), so reading availability never collides with existing reservations.
- `google_calendar.list_events(trainer, calendar_id, time_min, time_max)` (`trainings/services/google_calendar.py`) reads events via the trainer's existing OAuth token — the `calendar.events` scope already covers reading, so no re-consent is needed. `singleEvents=True` expands recurring events into per-instance rows.
- `availability_import.import_from_google()` (`trainings/services/availability_import.py`, new management command `import_availability_from_google`, chained into the existing `calmdog-training-gcal-sync` cron ahead of `sync_google_calendar`) turns each event into an `AvailabilityWindow` (`source="google"`, keyed by `google_event_id` for idempotent upsert) and calls `generate_slots()`. Session type/capacity are parsed from the event title: `"skupina N"` (case-insensitive) → group lesson, capacity `N`; anything else → individual, capacity 1. All-day, cancelled, and cross-midnight events are skipped and logged.
- When an event is deleted in Google, the matching window is deactivated and its **free** slots are removed — slots with any reservation (even a cancelled one) are kept, since `TrainingReservation.slot` is `on_delete=PROTECT`.
- Admin: register/edit calendars under "Kalendář dostupnosti"; the action **"Načíst termíny z Google"** triggers an import immediately instead of waiting for the cron.

---

## Deployment (Render.com)

- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start: `gunicorn config.wsgi:application`
- Stripe webhook must be registered for the production domain; secret goes in `STRIPE_WEBHOOK_SECRET`
- `PACKETA_MODE` is `live` on both `calmdog` and `calmdog-preview` in `render.yaml` (staging was switched from `mock` to `live` for real-shipment testing) — set to `mock` on staging if you need to avoid touching the real Zásilkovna account
- **Every service in `render.yaml`** (both `web` and `cron` types) needs its own `DJANGO_SECRET_KEY` and `DJANGO_ADMIN_URL` env vars — see [Settings / env vars](#settings--env-vars). New cron jobs added to `render.yaml` have historically forgotten these and crashed on first run (`RuntimeError: Missing DJANGO_ADMIN_URL in production.`); check for this when adding a new cron/service.
