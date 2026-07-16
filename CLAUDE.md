# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: CalmDog

Django 5.2 e-learning + e-shop platform for dog training. Active development branch: `refactor-cart-system`.

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

### CourseAccess & module sequencing

`CourseAccess` (payments app) links a user to a `Course` + `CoursePlan`. Key fields:
- `expires_at` — set **only on creation** (guard: `self.pk is None`). Never overwrite on save.
- `bypass_module_sequencing` — skips sequential quiz requirement; set `True` for legacy/admin users.
- `has_access()` — checks `is_active` + `expires_at`.

Module quiz sequencing logic lives in `courses/views.py:build_module_steps()`. Quiz questions are hardcoded in `MODULE_STEP_QUIZZES` dict (keyed by `course.slug → module.order → step_number`). To add quizzes for a new course/module, extend this dict.

### Course marketing content

`COURSE_MARKETING_CONTENT` dict in `payments/views.py` holds rich marketing data (hero text, metrics, curriculum, etc.) keyed by `course.slug`. If a course slug has no entry, `course_detail` falls back to a generic template branch. `Course.coming_soon = True` disables all "Add to cart" buttons.

### Packeta / Zásilkovna

`payments/services/packeta.py` uses **SOAP XML API** (`https://www.zasilkovna.cz/api/rest`). Functions:
- `create_packet(order)` — creates shipment, returns `{packet_id, tracking_number}`
- `get_packet_label_pdf(packet_id)` — returns raw PDF bytes (base64-decoded from API)
- `get_packet_status(packet_id)` — returns status dict

Set `PACKETA_MODE=mock` in env to skip real API calls during development. Admin has retry actions for failed shipments.

### File storage (R2 / S3)

When `USE_S3_STORAGE=1`, all `FileField`/`ImageField` uploads go to Cloudflare R2 via `django-storages`. **Always use `.open("rb")` instead of `.path`** when reading stored files — `.path` breaks on R2. Example:
```python
return FileResponse(order.invoice_pdf.open("rb"), ...)
```

### Design system (CSS)

- Base design tokens: `courses/static/css/base.css` — CSS variables (`--sage`, `--sage-deep`, `--text-dark`, etc.), `.btn-sage`, `.btn-outline-sage`, navbar
- Page-specific CSS files loaded via `{% block extra_css %}`
- Design patterns: kicker with `::before` line, Playfair Display headings, `#f5f5f0` background, `border-radius: 28px` cards, sage green (`#5f766b`, `#6f8780`) primary color
- Body text color: `#2f3e3a` (dark forest green, NOT pure black)

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
| `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL` | **Mandatory whenever `DJANGO_DEBUG` is unset/`0`** — `config/settings.py` raises `RuntimeError` at import time (before any view/command code runs) if either falls back to its dev sentinel value while not in debug mode. This applies to **every** Render service, including cron jobs — not just the web services. Must be declared (`sync: false`) in every service's `envVars` block in `render.yaml` *and* have its value filled in manually per-service in the Render dashboard (`sync: false` doesn't carry a value across services). |

### Hotel app

Landing page + reservation interest form. Availability fetched from iCal URL (`HOTEL_ICAL_URL`) via `hotel/services/calendar.py` and exposed at `/hotel/api/volne-terminy/` as JSON. Uses Flatpickr.js for date selection.

---

## Deployment (Render.com)

- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start: `gunicorn config.wsgi:application`
- Stripe webhook must be registered for the production domain; secret goes in `STRIPE_WEBHOOK_SECRET`
- `PACKETA_MODE=mock` is set in `render.yaml` for the staging service
- **Every service in `render.yaml`** (both `web` and `cron` types) needs its own `DJANGO_SECRET_KEY` and `DJANGO_ADMIN_URL` env vars — see [Settings / env vars](#settings--env-vars). New cron jobs added to `render.yaml` have historically forgotten these and crashed on first run (`RuntimeError: Missing DJANGO_ADMIN_URL in production.`); check for this when adding a new cron/service.
