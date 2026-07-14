import os
from pathlib import Path
import dj_database_url

# ======================================================
# BASE
# ======================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# .env – jen lokálně
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

# ======================================================
# CORE
# ======================================================

_DEV_SECRET_KEY = "dev-only-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEV_SECRET_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

if not DEBUG and SECRET_KEY == _DEV_SECRET_KEY:
    raise RuntimeError("Missing DJANGO_SECRET_KEY in production.")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower() or "development"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if h.strip()
    
]

SITE_URL = os.environ.get(
    "SITE_URL",
    "http://127.0.0.1:8000"
)

SHOW_PREVIEW_BANNER = os.environ.get("SHOW_PREVIEW_BANNER", "1") == "1" and APP_ENV != "production"

# calmdog.cz → www.calmdog.cz (jen v produkci)
# DOČASNĚ VYPNUTO 2026-07-14: způsobovalo smyčku přesměrování (redirect loop) –
# pravděpodobně koliduje s přesměrováním na straně Renderu/DNS opačným směrem.
# Než se ověří správné nastavení domény v Renderu, ať Django do přesměrování
# nezasahuje.
PREPEND_WWW = False




CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

_DEV_ADMIN_URL = "e3ff4a8b/"
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", _DEV_ADMIN_URL)

if not DEBUG and ADMIN_URL == _DEV_ADMIN_URL:
    raise RuntimeError("Missing DJANGO_ADMIN_URL in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ======================================================
# APPS
# ======================================================

INSTALLED_APPS = [
    # Vzhled adminu – MUSÍ být před django.contrib.admin
    "admin_interface",
    "colorfield",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # vyžaduje allauth

    # Autentizace – e-mail/heslo + sociální přihlášení (Google, Apple)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Apple se doplní později: "allauth.socialaccount.providers.apple",

    # Vylepšení adminu
    "import_export",
    "rangefilter",

    "accounts",
    "courses",
    "payments",
    "hotel",
    "shop",
    "trainings",
    "django.contrib.humanize",
]

USE_S3_STORAGE = os.environ.get("USE_S3_STORAGE", "0") == "1"

if USE_S3_STORAGE:
    INSTALLED_APPS.append("storages")

# ======================================================
# MIDDLEWARE
# ======================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # povinné pro allauth
]

# ======================================================
# URLS / TEMPLATES
# ======================================================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "payments.context_processors.cart_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ======================================================
# DATABASE
# ======================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ======================================================
# AUTH
# ======================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "accounts:my_courses"
LOGOUT_REDIRECT_URL = "courses:home"

# ======================================================
# ALLAUTH – e-mail/heslo + sociální přihlášení
# ======================================================

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",            # admin + superuser (username)
    "allauth.account.auth_backends.AuthenticationBackend",  # allauth (přihlášení e-mailem)
]

# --- Registrace a přihlášení e-mailem (bez uživatelského jména) ---
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_SIGNUP_FORM_CLASS = "accounts.forms.CalmDogSignupForm"  # + jméno a příjmení
ACCOUNT_EMAIL_VERIFICATION = "mandatory"      # účet aktivní až po ověření e-mailu
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"  # allauth username auto-vygeneruje z e-mailu
ACCOUNT_PREVENT_ENUMERATION = True              # neprozrazovat, které e-maily existují
ACCOUNT_CONFIRM_EMAIL_ON_GET = True             # potvrzení e-mailu jedním kliknutím z mailu

# Ochrana proti brute-force – limit neúspěšných přihlášení
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",
}

# --- Sociální přihlášení (Google; Apple se doplní později) ---
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True                # bez účtu → automaticky se vytvoří
SOCIALACCOUNT_LOGIN_ON_GET = True               # klik na tlačítko rovnou spustí OAuth
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"       # e-mail od Google je už ověřený
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                # Vlastní OAuth klient pro přihlášení (jiný než GOOGLE_OAUTH_* pro Kalendář).
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "key": "",
            }
        ],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

# ======================================================
# I18N
# ======================================================

LANGUAGE_CODE = "cs"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True

# ======================================================
# STATIC / MEDIA / STORAGES
# ======================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

if USE_S3_STORAGE:
    # Cloudflare R2 (S3 compatible)
    AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_ENDPOINT_URL = os.environ["AWS_S3_ENDPOINT_URL"]
    AWS_S3_REGION_NAME = "auto"

    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage"
    }

else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    }

# Soukromé soubory (faktury, přepravní štítky) – MIMO MEDIA_ROOT, takže je
# nikdy neservíruje veřejný static(MEDIA_URL, ...) fallback v config/urls.py.
# Přístup jen přes chráněné view (ověří vlastníka), ne přímým odkazem/URL.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ======================================================
# SECURITY
# ======================================================

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

ENABLE_HTTPS = os.environ.get("ENABLE_HTTPS", "0") == "1"

if ENABLE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = int(
        os.environ.get("DJANGO_HSTS_SECONDS", "31536000")
    )
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0


# ======================================================
# STRIPE
# ======================================================

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

if not DEBUG and not STRIPE_SECRET_KEY:
    raise RuntimeError("Missing STRIPE_SECRET_KEY in production.")

# ======================================================
# EMAIL (DEV)
# ======================================================

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "config.email_backend.IPv4EmailBackend",  # vynutí IPv4 – řeší ENETUNREACH na Render
)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = 10  # socket timeout v sekundách – zabrání blokování gunicorn workeru

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# ======================================================
#  PACKETA
# ======================================================

PACKETA_API_PASSWORD = os.environ.get("PACKETA_API_PASSWORD")
PACKETA_WIDGET_API_KEY = os.environ.get("PACKETA_WIDGET_API_KEY", "")
PACKETA_MODE = os.environ.get("PACKETA_MODE", "live").strip().lower() or "live"

# Výchozí hmotnost zásilky v kg (pokud není u produktu jinak)
PACKETA_DEFAULT_WEIGHT = float(os.environ.get("PACKETA_DEFAULT_WEIGHT", "0.5"))

# Název e-shopu zobrazený v Packeta systému
PACKETA_ESHOP_NAME = os.environ.get("PACKETA_ESHOP_NAME", "CalmDog")

PACKETA_MOCK_POINT_ID = os.environ.get("PACKETA_MOCK_POINT_ID", "mock-point-prague-1")
PACKETA_MOCK_POINT_NAME = os.environ.get(
    "PACKETA_MOCK_POINT_NAME",
    "TEST Zasilkovna, Praha 1",
)

# ======================================================
# HOTEL – GOOGLE CALENDAR (iCal)
# ======================================================
HOTEL_ICAL_URL = os.environ.get("HOTEL_ICAL_URL", "")

# ======================================================
# TRÉNINKY – GOOGLE CALENDAR (OAuth)
# ======================================================
# OAuth klient z Google Cloud Console (typ "Web application").
# Redirect URI musí být zaregistrované v Google Cloud a mířit na
# {SITE_URL}/treninky/google/callback/.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "")

# Když nejsou vyplněné klíče, celá Google Calendar integrace se elegantně
# přeskočí (rezervace, sloty, e-maily i profil fungují bez ní).
GOOGLE_CALENDAR_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# Scope pro čtení/zápis událostí v kalendáři trenéra.
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# ======================================================
# RECAPTCHA v3 – ochrana veřejných formulářů proti spamu
# ======================================================
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_SCORE_THRESHOLD = float(os.environ.get("RECAPTCHA_SCORE_THRESHOLD", "0.5"))

# Bez vyplněných klíčů (lokální vývoj) se ověření elegantně přeskočí –
# formuláře fungují dál, jen bez CAPTCHA ochrany.
RECAPTCHA_ENABLED = bool(RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY)

# Uzamčení prodeje (bez deploye – stačí nastavit SHOP_LOCKED=1 v Render env)
SHOP_LOCKED = os.environ.get("SHOP_LOCKED", "0") == "1"

# ======================================================
# ANALYTIKA
# ======================================================

# Google Tag Manager – Container ID (GTM-XXXXXXX).
# GTM spravuje všechny tagy (GA4, Clarity …) uvnitř GTM dashboardu.
# Prázdný řetězec = GTM se nevkládá do stránky.
GOOGLE_TAG_MANAGER_ID = os.environ.get("GOOGLE_TAG_MANAGER_ID", "GTM-TVJ3V6PS")

# Odkaz na Google recenzi – nastavit v Render env vars
GOOGLE_REVIEW_URL = os.environ.get("GOOGLE_REVIEW_URL", "")
# Počet dní po zaplacení, po kterých se odešle žádost o recenzi
REVIEW_DELAY_DAYS = int(os.environ.get("REVIEW_DELAY_DAYS", "30"))

# Verze cookie souhlasu. Pokud ji změníš (např. "2"), všichni uživatelé
# uvidí banner znovu a musí souhlas obnovit. Jinak se souhlas zachová.
COOKIE_CONSENT_VERSION = os.environ.get("COOKIE_CONSENT_VERSION", "1")

# Google Search Console – ověřovací kód pro meta tag.
# Získáš ho v Search Console → Ověřit vlastnictví → HTML tag.
GOOGLE_SEARCH_CONSOLE_VERIFICATION = os.environ.get("GOOGLE_SEARCH_CONSOLE_VERIFICATION", "")

# ======================================================
# LOGGING
# ======================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "admin.honeypot": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Aplikační logy (payments, shop, courses, …) – viditelné v Render logu
        "payments": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "shop": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "courses": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "trainings": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
