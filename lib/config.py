"""
Central configuration for the Instagram Auto-Publish System.
All constants, environment variables, and shared settings live here.
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional in production (GitHub Actions uses real env vars)


# ---------------------------------------------------------------------------
# Environment variable loading with clear error messages
# ---------------------------------------------------------------------------
class MissingEnvVarError(Exception):
    """Raised when a required environment variable / secret is not set."""
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvVarError(f"Missing required environment variable: {name}")
    return value


def optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def load_service_account_json() -> str:
    """Loads the Google service account JSON, preferring a Base64-encoded
    secret (GOOGLE_SERVICE_ACCOUNT_JSON_B64) when present. Base64 is
    immune to the newline/whitespace/character corruption that commonly
    happens when copy-pasting raw multi-line JSON through UIs and editors.
    Falls back to the raw GOOGLE_SERVICE_ACCOUNT_JSON secret if the
    Base64 variant isn't set.
    """
    import base64

    b64_value = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    if b64_value:
        try:
            return base64.b64decode(b64_value).decode("utf-8")
        except Exception as e:
            raise MissingEnvVarError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON_B64 exists but failed to decode: {e}"
            )
    return require_env("GOOGLE_SERVICE_ACCOUNT_JSON")


def check_required_env_vars(names: list) -> None:
    """Call at the start of every script to fail fast with a clear message."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Google Sheets structure
# ---------------------------------------------------------------------------
DAILY_LOG_TAB = "Daily_Log"
CURRENT_PLAN_TAB = "Current_Plan"
PLAN_HISTORY_TAB = "Plan_History"
SYSTEM_CONTROL_TAB = "System_Control"

DAILY_LOG_HEADERS = [
    "date", "post_index", "topic_slug", "hook_line", "fact_line", "cta_line",
    "caption_arabic", "hashtags", "background_query", "drive_file_id",
    "scheduled_time", "status", "published_at", "cleaned_at",
]

CURRENT_PLAN_HEADERS = [
    "date", "post_count",
    "post_1_type", "post_1_time", "post_1_bg_keywords", "post_1_bg_file_id",
    "post_2_type", "post_2_time", "post_2_bg_keywords", "post_2_bg_file_id",
    "post_3_type", "post_3_time", "post_3_bg_keywords", "post_3_bg_file_id",
]

PLAN_HISTORY_HEADERS = CURRENT_PLAN_HEADERS + ["archived_month"]

STATUS_READY = "ready"
STATUS_PUBLISHED = "published"
STATUS_CLEANED = "cleaned"

SYSTEM_STATUS_ACTIVE = "active"
SYSTEM_STATUS_PAUSED = "paused"


# ---------------------------------------------------------------------------
# Video / image generation
# ---------------------------------------------------------------------------
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_DURATION_SECONDS = 6

FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Tajawal-ExtraBold.ttf")

COLOR_HOOK = "#E8C468"     # gold
COLOR_FACT = "#FFFFFF"     # white
COLOR_CTA = "#D4D4D4"      # light gray
OVERLAY_COLOR = (26, 26, 46)   # #1A1A2E as RGB
OVERLAY_OPACITY = 0.65         # 65% opacity dark layer behind text

FONT_SIZE_HOOK = 78
FONT_SIZE_FACT = 64
FONT_SIZE_CTA = 46

# Word-count budgets enforced after Gemini generation
WORD_LIMITS = {
    "hook_line": (4, 6),
    "fact_line": (8, 12),
    "cta_line": (3, 5),
}

PIXABAY_FALLBACK_KEYWORDS = "abstract dark gradient calm"


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
BAGHDAD_TZ = "Asia/Baghdad"
CLEANUP_DELAY_HOURS = 2
TOPIC_HISTORY_LOOKBACK = 40
CONTAINER_POLL_MAX_ATTEMPTS = 60
CONTAINER_POLL_INTERVAL_SECONDS = 10


# ---------------------------------------------------------------------------
# Instagram Graph API
# ---------------------------------------------------------------------------
GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# NOTE: confirm this permission name matches what appears in your Meta App
# dashboard (Products -> Instagram -> Permissions). Documented as
# instagram_content_publish for the Facebook-Login-for-Business flow.
REQUIRED_IG_PERMISSION = "instagram_content_publish"


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
GEMINI_MODEL_NAME = "gemini-2.0-flash"
GEMINI_MAX_TOPIC_RETRIES = 2


# ---------------------------------------------------------------------------
# Content category (fixed per current plan)
# ---------------------------------------------------------------------------
CONTENT_CATEGORY = "quick_psychological_facts"
