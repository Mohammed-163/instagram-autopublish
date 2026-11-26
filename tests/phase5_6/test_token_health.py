import unittest
from unittest.mock import Mock, patch

import requests

from phase5_6.lib.token_health import TokenHealth, TokenMetadataError, inspect_token, renewal_summary
from phase5_6.scripts import refresh_token


class TokenHealthTests(unittest.TestCase):
    def test_inspect_selects_only_safe_metadata(self):
        response = Mock(status_code=200)
        response.json.return_value = {"data": {
            "app_id": "123", "is_valid": True, "expires_at": 200,
            "data_access_expires_at": 180, "scopes": ["instagram_content_publish"],
            "private_meta": "fake-token-text",
        }}
        with patch("phase5_6.lib.token_health.requests.get", return_value=response) as get:
            info = inspect_token("123", "fake-app-secret", "fake-token-text")
        self.assertEqual(info.effective_expiry, 180)
        self.assertNotIn("fake-token-text", info.summary())
        self.assertTrue(get.call_args.args[0].endswith("/debug_token"))

    def test_network_error_is_sanitized(self):
        with patch("phase5_6.lib.token_health.requests.get", side_effect=requests.ConnectionError("fake-app-secret")):
            with self.assertRaises(TokenMetadataError) as raised:
                inspect_token("123", "fake-app-secret", "fake-token-text")
        self.assertNotIn("fake-app-secret", str(raised.exception))

    def test_wrong_app_rejected(self):
        response = Mock(status_code=200)
        response.json.return_value = {"data": {"app_id": "999", "is_valid": True}}
        with patch("phase5_6.lib.token_health.requests.get", return_value=response):
            with self.assertRaisesRegex(TokenMetadataError, "different app"):
                inspect_token("123", "fake-app-secret", "fake-token-text")

    def test_later_token_expiry_alone_is_not_extension(self):
        before = TokenHealth(True, 500, 300, True)
        after = TokenHealth(True, 600, 300, True)
        self.assertIn("لم يتغيّر", renewal_summary(before, after, 100))
        self.assertIn("خلال 14", renewal_summary(before, after, 100))

    def test_later_effective_expiry_is_distinguished(self):
        before = TokenHealth(True, 500, 300, True)
        after = TokenHealth(True, 600, 350, True)
        self.assertIn("أكّد تمديد", renewal_summary(before, after, 100))

    def test_unknown_or_invalid_metadata_cannot_prove_extension(self):
        before = TokenHealth(True, 400, 300, True)
        self.assertIn("لم يُتح التحقق", renewal_summary(before, None, 100))
        self.assertIn("لم يُتح التحقق", renewal_summary(before, TokenHealth(True, 500, None, None), 100))
        self.assertIn("غير صالح", renewal_summary(before, TokenHealth(False, 600, 500, True), 100))

    def test_14_day_alert_requires_a_reported_nearby_date(self):
        old = TokenHealth(True, 1000, 0, True)
        self.assertNotIn("خلال 14", renewal_summary(old, TokenHealth(True, 1300000, 0, True), 100))
        self.assertIn("خلال 14", renewal_summary(old, TokenHealth(True, 1200000, None, None), 100))
        self.assertNotIn("خلال 14", renewal_summary(old, TokenHealth(True, 0, 0, True), 100))

    def test_metadata_failure_still_updates_secret_and_never_logs_raw_error(self):
        values = {k: "fake-" + k for k in refresh_token.REQUIRED_VARS}
        with patch.object(refresh_token.config, "check_required_env_vars"),                 patch.object(refresh_token.config, "require_env", side_effect=values.__getitem__),                 patch.object(refresh_token, "inspect_token", side_effect=requests.ConnectionError("DO-NOT-EXPOSE-URL")) as audit,                 patch.object(refresh_token, "update_github_secret") as write,                 patch.object(refresh_token, "InstagramClient") as ig,                 patch.object(refresh_token, "TelegramNotifier") as notify,                 patch("builtins.print") as logs:
            ig.exchange_token.return_value = "fake-candidate"
            ig.return_value.verify_token.return_value = True
            refresh_token.main()
        ig.exchange_token.assert_called_once_with(values["FB_APP_ID"], values["FB_APP_SECRET"], values["IG_ACCESS_TOKEN"])
        ig.return_value.verify_token.assert_called_once_with()
        write.assert_called_once_with(values["GH_PAT"], values["GH_REPO"], "IG_ACCESS_TOKEN", "fake-candidate")
        self.assertEqual(audit.call_count, 2)
        self.assertIn("لم يُتح التحقق", notify.return_value.send.call_args.args[0])
        self.assertNotIn("DO-NOT-EXPOSE-URL", str(logs.call_args_list))
        notify.return_value.alert_critical.assert_not_called()

    def test_exchange_exception_retains_no_raw_provider_message_in_alert(self):
        values = {k: "fake-" + k for k in refresh_token.REQUIRED_VARS}
        with patch.object(refresh_token.config, "check_required_env_vars"),                 patch.object(refresh_token.config, "require_env", side_effect=values.__getitem__),                 patch.object(refresh_token, "_try_token_audit", return_value=None),                 patch.object(refresh_token.InstagramClient, "exchange_token", side_effect=refresh_token.InstagramAPIError("TOKEN-HERE")),                 patch.object(refresh_token, "TelegramNotifier") as notify,                 patch.object(refresh_token, "update_github_secret") as write,                 self.assertRaises(SystemExit):
            refresh_token.main()
        self.assertNotIn("TOKEN-HERE", str(notify.return_value.alert_critical.call_args))
        write.assert_not_called()
