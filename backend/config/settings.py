import os
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
DEBUG = os.getenv("B2C_DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("B2C_SECRET_KEY", "local-development-only-b2c-do-not-deploy")
FRONTEND_URL = os.getenv("B2C_FRONTEND_URL", "http://localhost:5176").rstrip("/")
ALLOWED_HOSTS = os.getenv("B2C_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
if DEBUG:
    # Locally the app is reached as both localhost and 127.0.0.1, and Django treats
    # them as different origins. Trust the sibling spelling so a stray address bar
    # does not turn every write into a CSRF rejection. Production keeps one origin.
    _dev = urlparse(FRONTEND_URL)
    _sibling = {"localhost": "127.0.0.1", "127.0.0.1": "localhost"}.get(_dev.hostname or "")
    if _sibling:
        CSRF_TRUSTED_ORIGINS.append(f"{_dev.scheme}://{_sibling}" + (f":{_dev.port}" if _dev.port else ""))
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("local-") or not FRONTEND_URL.startswith("https://")):
    raise ImproperlyConfigured("Production requires B2C_SECRET_KEY (50+ characters) and HTTPS B2C_FRONTEND_URL")
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "accounts", "allauth", "allauth.account", "allauth.headless", "rest_framework", "search"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "accounts.middleware.NoStoreMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "allauth.account.middleware.AccountMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates", "DIRS":[], "APP_DIRS":True, "OPTIONS":{"context_processors":["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]
# SQLite eşzamanlı istekte kilitlenmesin: WAL (okuyucu yazarı bloklamaz),
# yazmalar için IMMEDIATE transaction ve 20 sn bekleme.
DATABASES = {"default": {"ENGINE":"django.db.backends.sqlite3", "NAME":os.getenv("B2C_ACCOUNT_DB", str(PROJECT_DIR / "data/accounts.sqlite3")), "OPTIONS":{"timeout":20, "transaction_mode":"IMMEDIATE", "init_command":"PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"}}, "reference":{"ENGINE":"django.db.backends.sqlite3", "NAME":Path(os.getenv("B2C_REFERENCE_DB", str(PROJECT_DIR / "data/listings.sqlite3"))).resolve().as_uri()+"?mode=ro", "OPTIONS":{"uri":True}}}
if os.getenv("B2C_DATABASE_URL"):
    parsed = urlparse(os.environ["B2C_DATABASE_URL"])
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("B2C_DATABASE_URL must be PostgreSQL")
    DATABASES["default"] = {"ENGINE":"django.db.backends.postgresql", "NAME":parsed.path.lstrip("/"), "USER":unquote(parsed.username or ""), "PASSWORD":unquote(parsed.password or ""), "HOST":parsed.hostname, "PORT":parsed.port or 5432, "CONN_MAX_AGE":60}
DATABASE_ROUTERS = ["search.routers.ReferenceRouter"]
B2C_BASELINE_DB = os.getenv("B2C_BASELINE_DB", str(PROJECT_DIR / "data/paket_fiyatlari.db"))
# Fiyat analizi (search/services/b2c.py) artik 1.8 GB'lik galeri.db'ye degil,
# scripts/build_galeri_summary.py'nin urettigi iki kucuk JSON'a bakiyor (~13 MB).
B2C_GALERI_SUMMARY = os.getenv("B2C_GALERI_SUMMARY", str(PROJECT_DIR / "data/galeri_summary.json"))
B2C_GALERI_LATEST_SNAPSHOT = os.getenv("B2C_GALERI_LATEST_SNAPSHOT", str(PROJECT_DIR / "data/galeri_latest_snapshot.json"))
# Arac Rehberi (search/services/guide.py) coklu-snapshot analizi (ilan ne zaman
# yayindan kalkti, stok, satis suresi) icin hala TAM galeri.db'ye ihtiyac duyuyor;
# bu ayri bir is (bkz. README) -- galeri.db o sunucuda/o is icin korunuyor.
B2C_GALLERY_DB = os.getenv("B2C_GALLERY_DB", str(PROJECT_DIR / "data/galeri.db"))
B2C_REGIONAL_CACHE = Path(os.getenv("B2C_REGIONAL_CACHE", str(PROJECT_DIR / ".local/regional_deals.json")))
B2C_GUIDE_CACHE = Path(os.getenv("B2C_GUIDE_CACHE", str(PROJECT_DIR / ".local/vehicle_guide.json")))
B2C_TRAITS_DB = os.getenv("B2C_TRAITS_DB", str(PROJECT_DIR / "data/vehicle_traits.db"))
CACHES = {"default":{"BACKEND":"django.core.cache.backends.locmem.LocMemCache", "LOCATION":"b2c-local"}}
if os.getenv("B2C_REDIS_URL"):
    CACHES["default"] = {"BACKEND":"django_redis.cache.RedisCache", "LOCATION":os.environ["B2C_REDIS_URL"], "OPTIONS":{"CLIENT_CLASS":"django_redis.client.DefaultClient"}}
# Aynı girdiyle gelen analizler Redis'ten sunulur (0 = kapalı; Redis yoksa varsayılan kapalı).
B2C_ANALYSIS_CACHE_TTL = int(os.getenv("B2C_ANALYSIS_CACHE_TTL", "3600" if os.getenv("B2C_REDIS_URL") else "0"))
if not DEBUG and not os.getenv("B2C_REDIS_URL"):
    raise ImproperlyConfigured("Production requires shared B2C_REDIS_URL for rate limits")
REST_FRAMEWORK = {"EXCEPTION_HANDLER":"accounts.exceptions.api_exception_handler", "NUM_PROXIES":int(os.getenv("B2C_TRUSTED_PROXY_COUNT", "0")), "DEFAULT_AUTHENTICATION_CLASSES":["accounts.authentication.BrowserSessionAuthentication"], "DEFAULT_PERMISSION_CLASSES":["accounts.permissions.VerifiedUser"], "DEFAULT_THROTTLE_RATES":{"b2c_analysis":"20/min", "b2c_lookup":"30/min"}}
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# Without an explicit prefix allauth prepends "[<request host>] ", which leaks
# 127.0.0.1:8011 locally and the server host in production. The subject
# templates already carry the brand name.
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
# A six digit code beats a link: no localhost URL in the mail, and the person
# stays in the tab they signed up in. The code lives in that browser session.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
# allauth defaults to a dashed 8 character alphanumeric code; six digits is what
# people expect from an emailed verification code.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_FORMAT = {"length": 6, "numeric": True, "dashed": False}
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = 3
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = True
# Duplicate signups answer plainly ("this email already has an account") instead of
# the silent "verification sent" reply. Trade-off: signup and password reset now
# reveal whether an address has an account.
ACCOUNT_PREVENT_ENUMERATION = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_MAX_EMAIL_ADDRESSES = 1
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
ACCOUNT_RATE_LIMITS = {"login":"20/m/ip", "login_failed":"5/5m/key,20/5m/ip", "signup":"5/10m/ip", "reset_password":"3/10m/key,10/10m/ip", "reset_password_from_key":"10/10m/ip", "confirm_email":"1/m/key,5/10m/key,20/10m/ip", "b2c_resend":"1/m/key,5/10m/key,20/10m/ip"}
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)
HEADLESS_FRONTEND_URLS = {"account_confirm_email":FRONTEND_URL+"/verify-email/{key}", "account_reset_password":FRONTEND_URL+"/forgot-password", "account_reset_password_from_key":FRONTEND_URL+"/reset-password/{key}", "account_signup":FRONTEND_URL+"/signup", "account_login":FRONTEND_URL+"/login"}
AUTH_PASSWORD_VALIDATORS = [{"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS":{"min_length":10}}, {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"}]
PASSWORD_RESET_TIMEOUT = 3600
SESSION_COOKIE_NAME = "b2c_sessionid"
CSRF_COOKIE_NAME = "b2c_csrftoken"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_FAILURE_VIEW = "accounts.views.csrf_failure"
EMAIL_BACKEND = os.getenv("B2C_EMAIL_BACKEND") or "accounts.mail.PrivateFileBackend"
EMAIL_FILE_PATH = os.getenv("B2C_MAIL_DIR") or str(PROJECT_DIR / ".local/mail")
EMAIL_HOST = os.getenv("B2C_SMTP_HOST", "")
EMAIL_PORT = int(os.getenv("B2C_SMTP_PORT", "587"))
EMAIL_HOST_USER = os.getenv("B2C_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("B2C_SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("B2C_SMTP_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.getenv("B2C_FROM_EMAIL") or "Autosense <noreply@localhost>"
if not DEBUG and (EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend" or not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD or "localhost" in DEFAULT_FROM_EMAIL):
    raise ImproperlyConfigured("Production requires SMTP backend with credentials and a real B2C_FROM_EMAIL")
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Only set to 1 behind the supplied proxy, with the backend network private.
ALLAUTH_TRUSTED_PROXY_COUNT = int(os.getenv("B2C_TRUSTED_PROXY_COUNT", "0"))
