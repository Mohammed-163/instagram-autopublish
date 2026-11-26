"""Read Meta token health and report only safe metadata."""

from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from . import config


class TokenMetadataError(Exception):
    """A sanitized Meta introspection error."""


@dataclass(frozen=True)
class TokenHealth:
    valid: bool
    expires_at: int | None
    data_access_expires_at: int | None
    can_publish: bool | None

    @property
    def effective_expiry(self) -> int | None:
        """Return the first deadline; zero means both are explicitly non-expiring."""
        if self.expires_at is None or self.data_access_expires_at is None:
            return None
        return min((d for d in (self.expires_at, self.data_access_expires_at) if d > 0), default=0)

    def summary(self) -> str:
        return (
            f"valid={self.valid}; token_expires={_display_time(self.expires_at)}; "
            f"data_access_expires={_display_time(self.data_access_expires_at)}; "
            f"publish_scope={self.can_publish}"
        )


def _timestamp(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 253402300799 else None


def _display_time(value: int | None) -> str:
    if value is None:
        return "unreported"
    if value == 0:
        return "none-reported-by-Meta"
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def inspect_token(app_id: str, app_secret: str, token: str) -> TokenHealth:
    try:
        resp = requests.get(
            f"{config.GRAPH_API_BASE}/debug_token",
            params={"input_token": token},
            headers={"Authorization": f"Bearer {app_id}|{app_secret}"},
            timeout=20,
        )
        payload = resp.json()
    except (requests.RequestException, ValueError):
        # Underlying errors can include the request URL and input token.
        raise TokenMetadataError("Could not read Meta token metadata") from None

    if not isinstance(payload, dict):
        raise TokenMetadataError("Invalid Meta token metadata response")
    data = payload.get("data")
    if not isinstance(data, dict) or resp.status_code != 200:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        safe_code = str(code) if type(code) is int else "unknown"
        raise TokenMetadataError(f"Meta token metadata unavailable (code={safe_code})")
    if type(data.get("is_valid")) is not bool:
        raise TokenMetadataError("Meta did not report token validity")
    if data["is_valid"] and str(data.get("app_id") or "") != str(app_id):
        raise TokenMetadataError("Meta token belongs to a different app")
    scopes = data.get("scopes")
    can_publish = "instagram_content_publish" in scopes if isinstance(scopes, list) else None
    return TokenHealth(
        valid=data["is_valid"],
        expires_at=_timestamp(data.get("expires_at")),
        data_access_expires_at=_timestamp(data.get("data_access_expires_at")),
        can_publish=can_publish,
    )


def renewal_summary(before: TokenHealth | None, after: TokenHealth | None, now: int) -> str:
    """Distinguish proof of extension from a successful exchange and save."""
    old = before.effective_expiry if before is not None else None
    new = after.effective_expiry if after is not None else None
    if after is None or old is None or new is None or not before.valid:
        status = "Meta لم يُتح التحقق من تمديد الصلاحية."
    elif not after.valid:
        status = "Meta أبلغ أن التوكن المرشح غير صالح في فحص البيانات."
    elif new != 0 and new <= now:
        status = "Meta أبلغ أن موعد انتهاء الصلاحية المرصود قد حلّ."
    elif old > 0 and (new == 0 or new > old):
        status = "Meta أكّد تمديد أقرب موعد انتهاء للصلاحية."
    elif new == old:
        status = "أقرب موعد انتهاء لم يتغيّر بحسب Meta."
    else:
        status = "Meta أبلغ أن أقرب موعد انتهاء صار أبكر."
    if after is None:
        return status

    if after.can_publish is not True:
        status += " لم يؤكد فحص البيانات وجود إذن النشر."
    deadlines = [
        d for d in (after.expires_at, after.data_access_expires_at)
        if d is not None and d > 0
    ]
    if deadlines:
        earliest = min(deadlines)
        if now < earliest <= now + 14 * 86400:
            status += f" تنبيه: موعد انتهاء مُبلّغ عنه خلال 14 يومًا ({_display_time(earliest)})."
        elif earliest <= now and (new is None or new > now):
            status += f" تنبيه: موعد انتهاء مُبلّغ عنه قد حلّ ({_display_time(earliest)})."
    return status
