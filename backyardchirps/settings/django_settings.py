import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Everything the station builds up over time: the environment file, the database, saved
# clips, downloaded models and region packs. It sits outside the code directory so that
# an update can replace the whole release at once, without moving any data or downloading
# the models all over again.
#
# BACKYARDCHIRPS_DATA_DIR must come from the real process environment, meaning systemd or the
# shell. It cannot come from .env, because .env is itself read out of the directory this
# names. Left unset, every path stays inside the checkout, which is what a development
# machine wants.
_configured_data_dir = os.environ.get("BACKYARDCHIRPS_DATA_DIR")
DATA_DIR = Path(_configured_data_dir) if _configured_data_dir else BASE_DIR

load_dotenv(DATA_DIR / ".env")

try:
    VERSION = installed_version("backyardchirps")
except PackageNotFoundError:
    # Running from a source tree that was never installed, as happens on some CI paths.
    VERSION = "0.0.0+unknown"

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

# Keep the CSRF token in the session instead of its own cookie, so the Vite dev proxy has
# only one Set-Cookie header to pass through.
CSRF_USE_SESSIONS = True

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "backyardchirps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

if DEBUG:
    CSRF_TRUSTED_ORIGINS.append("http://localhost:5173")

ROOT_URLCONF = "backyardchirps.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backyardchirps.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "detections.db",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s  %(levelname)-8s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

LANGUAGE_CODE = "es"

TIME_ZONE = "Europe/Madrid"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "staticfiles"

LOCALE_PATHS = [BASE_DIR / "backyardchirps" / "locale"]

# ---------------------------------------------------------------------------
# Species data layout  (see docs/devel/species-data.md)
# ---------------------------------------------------------------------------
# The taxonomy and the photos are the same everywhere, so they ship with the code. The
# range maps and the occurrence rasters are framed on one region and come from a region
# pack instead, which a station downloads for wherever it sits. Nothing here is named
# after a country: the species list is derived from the station's coordinates.
SPECIES_DATA_DIR = BASE_DIR / "backyardchirps" / "species_data"
SPECIES_TAXONOMY_FILE = SPECIES_DATA_DIR / "taxonomy" / "birdnet_taxonomy.json"
SPECIES_IMAGES_DIR = SPECIES_DATA_DIR / "assets" / "images"

# Species data comes in two kinds. The committed seeds above ship with the code and never
# change while the app runs, so a release brings them and a rollback takes them away.
# Everything below is downloaded or regenerated on the machine and belongs with the data
# instead, if only because the models are large enough that re-fetching them on every
# update would be absurd.
#
# The two layouts are deliberately not mirrors of each other. Inside a data directory the
# names simply say what they hold, since that tree is read on its own and nothing in it is
# "generated" next to anything else. In a plain checkout everything stays where it always
# was, so development machines are untouched.
if _configured_data_dir:
    SPECIES_RUNTIME_DIR = DATA_DIR / "species"
    MODELS_DIR = DATA_DIR / "models"
    EBIRD_DATA_DIR = SPECIES_RUNTIME_DIR / "ebird_occurrence"
    RECORDER_STATE_DIR = DATA_DIR
else:
    SPECIES_RUNTIME_DIR = SPECIES_DATA_DIR / "generated"
    MODELS_DIR = SPECIES_RUNTIME_DIR / "birdnet3"
    EBIRD_DATA_DIR = SPECIES_DATA_DIR / "assets" / "ebird_occurrence"
    RECORDER_STATE_DIR = SPECIES_RUNTIME_DIR

# Where update_species_data, which a daily timer runs, writes its fresh taxonomy and
# species list. It never touches the committed files above, so those stay exactly as
# checked in for tests, CI and fresh installs to seed from. The app reads a runtime file
# whenever it finds one.
SPECIES_TAXONOMY_RUNTIME_FILE = SPECIES_RUNTIME_DIR / "taxonomy" / "birdnet_taxonomy.json"

# EBIRD_DATA_DIR holds the eBird Status & Trends data behind the seasonality timeline: one
# folder per species, named by eBird code, each holding a weekly raster and a CSV of band
# dates. MODELS_DIR holds the BirdNET 3 acoustic model and GeoModel.

# One <slug>.webp per species, framed on the region. Both this and EBIRD_DATA_DIR are
# symlinks a pack install moves, so this path never changes and nothing here has to know
# which pack is in use. A station with no pack has no directory here at all, which is a
# working state: a species page then shows no range map and everything else is unchanged.
SPECIES_RANGE_MAPS_DIR = SPECIES_RUNTIME_DIR / "range_maps"

# One <slug>.json per species, holding the addresses of a few example recordings on
# xeno-canto. Another symlink a pack install moves, for the same reason as the two above.
# The search that finds those recordings needs an API key and happens once, while a pack
# is built, so no station needs one: see docs/devel/species-data.md.
SPECIES_REFERENCE_CALLS_DIR = SPECIES_RUNTIME_DIR / "reference_calls"

# Downloaded region packs, meaning range maps and cropped occurrence rasters, one
# directory per pack id.
REGION_PACKS_DIR = DATA_DIR / "region-packs"

# How far an install of a region pack has got. A file, because the two web workers do not
# share memory and an install has to outlive the page that asked for it.
REGION_PACK_INSTALL_STATUS_FILE = DATA_DIR / "region-pack-install-status.json"

# The one-time token install.sh writes, which the setup wizard trades for the first admin
# account. Finishing the wizard deletes it, so its absence is what makes the wizard
# refuse to hand the station to a second person.
SETUP_TOKEN_FILE = DATA_DIR / "setup-token"
