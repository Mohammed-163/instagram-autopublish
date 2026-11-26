"""
Token refresh — runs on its own schedule every config.TOKEN_REFRESH_INTERVAL_DAYS
days (independent from monthly_task.py).

Why this is its own script:
Previously the Meta long-lived-token renewal only happened as step 1 of the
monthly planning task (monthly_task.py) — a 7-step job that also calls
Gemini and Pixabay and writes to Sheets. If ANY later step in that job (or
the job itself) failed to even run for a given month (infra hiccup, Actions
outage, a broken monthly_task.yml, etc.), the token could go unrenewed for a
much longer stretch, and since long-lived tokens expire in ~60 days, that's
a real risk of everything going dark with almost no warning.

This script exchanges the token, checks account readability, and updates the
GitHub secret. Best-effort Meta metadata separately reports whether the
effective deadline moved; a successful exchange alone is not proof.
"""
import base64
import os
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.telegram_notifier import TelegramNotifier
from lib.token_health import TokenHealth, inspect_token, renewal_summary

REQUIRED_VARS = [
    "IG_ACCESS_TOKEN", "IG_BUSINESS_ID", "FB_APP_ID", "FB_APP_SECRET",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "GH_PAT", "GH_REPO",
]


def update_github_secret(github_pat: str, github_repo: str, secret_name: str, secret_value: str) -> None:
    """Updates a repository secret via the GitHub API (libsodium-encrypted)."""
    from nacl import encoding, public

    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
    api_base = f"https://api.github.com/repos/{github_repo}"

    key_resp = requests.get(f"{api_base}/actions/secrets/public-key", headers=headers, timeout=20)
    key_resp.raise_for_status()
    key_data = key_resp.json()
    public_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    resp = requests.put(
        f"{api_base}/actions/secrets/{secret_name}", headers=headers, timeout=20,
        json={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
    )
    if resp.status_code not in (201, 204):
        raise RuntimeError(f"Failed updating GitHub secret {secret_name}: HTTP {resp.status_code}")


def _try_token_audit(label: str, app_id: str, app_secret: str, token: str) -> TokenHealth | None:
    """Metadata is diagnostic only: an outage must not interrupt renewal."""
    try:
        result = inspect_token(app_id, app_secret, token)
        print(f"{label} Meta token metadata: {result.summary()}")
        return result
    except Exception:
        # Neither provider errors nor request URLs belong in public logs.
        print(f"{label} Meta token metadata unavailable; continuing existing renewal.")
        return None


def main():
    config.check_required_env_vars(REQUIRED_VARS)
    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))

    try:
        current_token = config.require_env("IG_ACCESS_TOKEN")

        app_id = config.require_env("FB_APP_ID")
        app_secret = config.require_env("FB_APP_SECRET")
        before = _try_token_audit("Current", app_id, app_secret, current_token)

        # Preserve the existing weekly exchange. Metadata is informational
        # and does not alter exchange, verification or secret storage.
        new_token = InstagramClient.exchange_token(
            app_id, app_secret, current_token,
        )

        ig = InstagramClient(new_token, config.require_env("IG_BUSINESS_ID"))
        if not ig.verify_token():
            raise CriticalError("التوكن الجديد بعد التجديد لم يجتز التحقق (verify_token فشل)")

        update_github_secret(config.require_env("GH_PAT"), config.require_env("GH_REPO"), "IG_ACCESS_TOKEN", new_token)

        after = _try_token_audit("Stored candidate", app_id, app_secret, new_token)
        now = datetime.now(timezone.utc)
        summary = renewal_summary(before, after, int(now.timestamp()))
        notifier.send(
            f"تمت مبادلة توكن Instagram وحفظه في GitHub ({now.date()}). "
            f"{summary} الفحص المعتاد التالي خلال {config.TOKEN_REFRESH_INTERVAL_DAYS} أيام."
        )
        print("Token exchanged, account read verified, and GitHub secret updated.")
        print(summary)

    except (CriticalError, InstagramAPIError) as e:
        # Refresh failing is serious but not necessarily fatal *today* — the
        # OLD token (still in the secret) may still have weeks of life left.
        # Alert loudly so a human fixes FB_APP_SECRET/permissions well before
        # the old token actually expires.
        notifier.alert_critical(
            "فشل تجديد توكن Instagram (مهم: يجب المتابعة قبل انتهاء صلاحية التوكن الحالي)",
            str(e) if isinstance(e, CriticalError) else "Meta رفضت مبادلة التوكن. لم تُعرض استجابة الخادم لتجنّب كشف بيانات الاعتماد.",
        )
        sys.exit(1)
    except Exception as e:
        # requests exceptions can contain their URL, including secrets.
        print(f"Token exchange/update failed ({type(e).__name__}).")
        notifier.alert_critical("خطأ غير متوقع أثناء تجديد توكن Instagram", type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()
