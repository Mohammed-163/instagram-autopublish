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

This script does ONE thing: refresh the token, verify it, update the GitHub
secret, and alert on success/failure. Running it weekly instead of monthly
means even several missed/failed runs in a row still leave a wide safety
margin before the ~60-day expiry.
"""
import base64
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.telegram_notifier import TelegramNotifier

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
        raise RuntimeError(f"Failed updating GitHub secret {secret_name}: {resp.status_code} - {resp.text}")


def main():
    config.check_required_env_vars(REQUIRED_VARS)
    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))

    try:
        current_token = config.require_env("IG_ACCESS_TOKEN")

        # Refresh even if the current token still verifies fine — the point
        # is to keep resetting the 60-day clock on a short, reliable cadence,
        # not to wait until something is already close to breaking.
        new_token = InstagramClient.exchange_token(
            config.require_env("FB_APP_ID"), config.require_env("FB_APP_SECRET"), current_token,
        )

        ig = InstagramClient(new_token, config.require_env("IG_BUSINESS_ID"))
        if not ig.verify_token():
            raise CriticalError("التوكن الجديد بعد التجديد لم يجتز التحقق (verify_token فشل)")

        update_github_secret(config.require_env("GH_PAT"), config.require_env("GH_REPO"), "IG_ACCESS_TOKEN", new_token)

        notifier.notify_success(
            f"تم تجديد توكن Instagram بنجاح ({datetime.utcnow().strftime('%Y-%m-%d')}). "
            f"التجديد التالي خلال {config.TOKEN_REFRESH_INTERVAL_DAYS} أيام."
        )
        print("✓ Token refreshed, verified, and GitHub secret updated.")

    except (CriticalError, InstagramAPIError) as e:
        # Refresh failing is serious but not necessarily fatal *today* — the
        # OLD token (still in the secret) may still have weeks of life left.
        # Alert loudly so a human fixes FB_APP_SECRET/permissions well before
        # the old token actually expires.
        notifier.alert_critical(
            "فشل تجديد توكن Instagram (مهم: يجب المتابعة قبل انتهاء صلاحية التوكن الحالي)",
            str(e),
        )
        sys.exit(1)
    except Exception as e:
        notifier.alert_critical("خطأ غير متوقع أثناء تجديد توكن Instagram", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
