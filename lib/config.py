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


def _load_b64_json_secret(b64_var_name: str, raw_var_name: str) -> str:
    """Shared helper: prefers a Base64-encoded secret (immune to the
    newline/whitespace corruption that happens when copy-pasting raw
    multi-line JSON through UIs and editors), falls back to the raw var.
    """
    import base64

    b64_value = os.environ.get(b64_var_name)
    if b64_value:
        try:
            return base64.b64decode(b64_value).decode("utf-8")
        except Exception as e:
            raise MissingEnvVarError(
                f"{b64_var_name} exists but failed to decode: {e}"
            )
    return require_env(raw_var_name)


def load_sheets_service_account_json() -> str:
    """Loads the Google Service Account JSON used ONLY for Google Sheets
    (gspread / Credentials.from_service_account_info). This is NOT the
    same credential type as Drive — see load_drive_oauth_token_json().
    """
    return _load_b64_json_secret(
        "GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SERVICE_ACCOUNT_JSON"
    )


def load_drive_oauth_token_json() -> str:
    """Loads the OAuth user-credential JSON (token.json content) used ONLY
    for Google Drive (Credentials.from_authorized_user_info). Service
    Accounts have 0 bytes of their own Drive storage quota, so Drive must
    use OAuth with the user's own account instead. This is a DIFFERENT
    credential format from the Sheets service account JSON above — do not
    reuse GOOGLE_SERVICE_ACCOUNT_JSON_B64 here.
    """
    return _load_b64_json_secret(
        "GOOGLE_OAUTH_TOKEN_JSON_B64", "GOOGLE_OAUTH_TOKEN_JSON"
    )


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
POST_PERFORMANCE_TAB = "Post_Performance"

DAILY_LOG_HEADERS = [
    "date", "post_index", "topic_slug", "hook_line", "fact_line", "cta_line",
    "caption_arabic", "hashtags", "background_query", "drive_file_id",
    "scheduled_time", "status", "published_at", "cleaned_at",
    "media_id", "insights_fetched", "reserved_at",
]

# Post_Performance tab - one row per published post, filled in 3 days after
# publish by scripts/fetch_insights.py. This is what gets sent to Gemini at
# monthly-plan time so it can learn which topics/angles actually perform.
POST_PERFORMANCE_HEADERS = [
    "date", "topic_slug", "hook_line", "fact_line", "caption_arabic",
    "hashtags", "media_id", "published_at", "fetched_at",
    "reach", "saved", "shares", "likes", "comments",
]

CURRENT_PLAN_HEADERS = [
    "date", "post_count",
    "post_1_type", "post_1_time", "post_1_bg_keywords", "post_1_bg_file_id",
    "post_2_type", "post_2_time", "post_2_bg_keywords", "post_2_bg_file_id",
    "post_3_type", "post_3_time", "post_3_bg_keywords", "post_3_bg_file_id",
]

PLAN_HISTORY_HEADERS = CURRENT_PLAN_HEADERS + ["archived_month"]

STATUS_READY = "ready"
STATUS_PUBLISHING = "publishing"  # reserved right before the actual IG API call, see publish.py
STATUS_PUBLISHED = "published"
STATUS_CLEANED = "cleaned"

# If a row is stuck in "publishing" longer than this, something failed
# between reserving it and confirming the publish — needs a human look
# rather than an automatic retry (retrying risks a real duplicate post if
# the first attempt actually succeeded on Instagram's side).
STALE_PUBLISHING_MINUTES = 20

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

# How long to wait after publish before pulling Instagram insights (reach/
# saved/shares need a few days to stabilize; Instagram also throttles very
# fresh media).
INSIGHTS_FETCH_DELAY_DAYS = 3

# Long-lived Meta tokens last ~60 days. We refresh independently of the
# monthly planning task so a Gemini/quota failure elsewhere can never block
# the refresh. Refreshing this often leaves a wide safety margin.
TOKEN_REFRESH_INTERVAL_DAYS = 7
TOKEN_EXPIRY_WARNING_DAYS = 20  # alert if a refresh is somehow overdue by more than this

# ---------------------------------------------------------------------------
# Image vetting (pre-publish moderation)
# ---------------------------------------------------------------------------
# We download several background candidates per post and let Gemini pick the
# one that best matches the topic AND passes a decency/Islamic-compliance
# check (no nudity, no alcohol/drugs imagery, no other haram content). This
# uses a SEPARATE, dedicated Gemini key (not part of the 3-key rotation used
# for text generation) so image moderation never competes for quota with
# daily content generation.
IMAGE_CANDIDATE_COUNT = 5
IMAGE_VETTING_MODEL_NAME = "gemini-3.5-flash-lite"


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
# Content-generation model (post writing). Previously gemini-3.5-flash-lite;
# the user asked for a non-Lite Flash model instead, so this now points at
# gemini-3.6-flash — the newest model in the list, still on the free-tier-
# friendly Flash line (just not the cost-optimized Lite variant).
GEMINI_MODEL_NAME = "gemini-3.6-flash"
GEMINI_MAX_TOPIC_RETRIES = 2


# ---------------------------------------------------------------------------
# Content category (fixed per current plan)
# ---------------------------------------------------------------------------
CONTENT_CATEGORY = "quick_psychological_facts"
