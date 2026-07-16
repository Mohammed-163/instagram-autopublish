"""
Three-tier error handling:

1. CriticalError    — external, unrecoverable (token dead, key invalid).
                       Telegram alert + stop. No auto-fix attempted.
2. RecoverableError — expected, known fix (quota exceeded, transient network).
                       Handled by plain retry/key-rotation logic, no AI involved.
3. UnexpectedError  — anything else. Captured, sent to Gemini for diagnosis,
                       fix applied on a new branch, PR opened, Telegram notified.
                       NEVER auto-merged.
"""
import traceback

import requests

from . import config


class CriticalError(Exception):
    """External failure requiring manual intervention. No auto-fix."""
    pass


class RecoverableError(Exception):
    """Expected, retryable failure. Handled by plain code, not AI."""
    pass


class UnexpectedError(Exception):
    """Anything not anticipated. Routed to Gemini diagnosis + PR flow."""
    pass


def create_fix_pr(gemini_client, github_pat: str, github_repo: str,
                   file_path: str, error_message: str, code_snippet: str, date_str: str) -> str:
    """Creates a branch with a Gemini-suggested fix and opens a PR.
    Returns the PR URL. Never merges automatically."""
    suggested_fix = gemini_client.diagnose_error(error_message, code_snippet)

    branch_name = f"auto-fix/error-{date_str}"
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
    api_base = f"https://api.github.com/repos/{github_repo}"

    # 1. get default branch SHA
    repo_info = requests.get(api_base, headers=headers, timeout=20).json()
    default_branch = repo_info.get("default_branch", "main")
    ref = requests.get(f"{api_base}/git/ref/heads/{default_branch}", headers=headers, timeout=20).json()
    base_sha = ref["object"]["sha"]

    # 2. create new branch
    requests.post(
        f"{api_base}/git/refs", headers=headers, timeout=20,
        json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
    )

    # 3. get current file content + sha, then update it on the new branch
    file_info = requests.get(
        f"{api_base}/contents/{file_path}", headers=headers,
        params={"ref": branch_name}, timeout=20,
    ).json()

    import base64
    new_content_b64 = base64.b64encode(suggested_fix.encode("utf-8")).decode("utf-8")
    requests.put(
        f"{api_base}/contents/{file_path}", headers=headers, timeout=20,
        json={
            "message": f"Auto-fix suggestion for error on {date_str}",
            "content": new_content_b64,
            "sha": file_info.get("sha"),
            "branch": branch_name,
        },
    )

    # 4. open the PR
    pr_resp = requests.post(
        f"{api_base}/pulls", headers=headers, timeout=20,
        json={
            "title": f"Auto-fix suggestion: {error_message[:80]}",
            "head": branch_name,
            "base": default_branch,
            "body": f"**رسالة الخطأ:**\n```\n{error_message}\n```\n\n"
                    f"هذا إصلاح مقترح آلياً من Gemini. يتطلب مراجعة يدوية قبل الدمج — لا يُدمج تلقائياً أبداً.",
        },
    )
    pr_data = pr_resp.json()
    return pr_data.get("html_url", "")


def handle_unexpected(notifier, gemini_client, github_pat: str, github_repo: str,
                       file_path: str, code_snippet: str, date_str: str) -> None:
    """Call from an except block. Captures the current exception, gets a
    Gemini fix suggestion, opens a PR, and notifies via Telegram."""
    error_message = traceback.format_exc()
    try:
        pr_url = create_fix_pr(gemini_client, github_pat, github_repo, file_path,
                                error_message, code_snippet, date_str)
        notifier.alert_pr(error_message[:300], pr_url)
    except Exception as pr_error:
        # If even the auto-fix-PR flow fails, fall back to a plain critical alert
        notifier.alert_critical(
            "فشل خطأ غير متوقع + فشلت آلية اقتراح الإصلاح أيضاً",
            f"الخطأ الأصلي:\n{error_message[:500]}\n\nخطأ آلية PR:\n{pr_error}",
        )
