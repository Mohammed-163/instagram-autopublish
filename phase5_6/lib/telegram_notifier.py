"""
Telegram notifications. Stateless — every script imports and calls send()
directly for any status update or error.
"""
import requests

MAX_MESSAGE_LENGTH = 4096


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message, splitting it if it exceeds Telegram's length limit.
        Returns True if all chunks sent successfully, False otherwise.
        Never raises — a failed notification should not crash the calling script.
        """
        chunks = [message[i:i + MAX_MESSAGE_LENGTH]
                  for i in range(0, len(message), MAX_MESSAGE_LENGTH)] or [""]

        all_ok = True
        for chunk in chunks:
            try:
                resp = requests.post(
                    self.api_url,
                    data={"chat_id": self.chat_id, "text": chunk, "parse_mode": parse_mode},
                    timeout=15,
                )
                if resp.status_code != 200:
                    print(f"⚠️ Telegram send failed ({resp.status_code}): {resp.text}")
                    all_ok = False
            except requests.RequestException as e:
                print(f"⚠️ Telegram send exception: {e}")
                all_ok = False
        return all_ok

    def alert_critical(self, title: str, detail: str) -> bool:
        return self.send(f"🔴 <b>خطأ حرج</b>\n{title}\n\n{detail}")

    def alert_pr(self, error_summary: str, pr_url: str) -> bool:
        return self.send(f"🟡 <b>صار خطأ، تم اقتراح إصلاح</b>\n{error_summary}\n\nراجع الإصلاح هنا:\n{pr_url}")

    def notify_success(self, message: str) -> bool:
        return self.send(f"✅ {message}")
