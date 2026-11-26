from datetime import datetime, timedelta, timezone
import json
from unittest import TestCase, mock

from requests import Timeout

from phase5_6.scripts import fetch_insights as collector
from phase5_6.scripts.fetch_insights import InstagramAPIError
from lib import instagram_client


class ReelsRetentionTests(TestCase):
    def setUp(self):
        self.deadline = datetime.now(timezone.utc) + timedelta(minutes=20)
        self.ig = mock.Mock()
        self.watch, self.skip = collector.REELS_RETENTION_METRICS

    def result(self, name, value):
        return {"data": [{"name": name, "values": [{"value": value}]}]}

    def test_both_metrics_native_units_and_explicit_zero(self):
        self.ig._request.side_effect = [self.result(self.watch, 4279), self.result(self.skip, 0)]
        assert collector.fetch_optional_reels_retention(self.ig, "123", "REELS", self.deadline) == {
            self.watch: 4279, self.skip: 0,
        }
        assert [c.kwargs["params"]["metric"] for c in self.ig._request.call_args_list] == [self.watch, self.skip]

    def test_unsupported_or_timeout_does_not_drop_core_or_supported_metric(self):
        self.ig._request.side_effect = [
            {"media_product_type": "REELS", "media_type": "VIDEO"},
            self.result("reach", 98),
            self.result(self.watch, 3000),
            InstagramAPIError("unsupported metric"),
        ]
        core, product_type = collector.fetch_media_insights(self.ig, "123")
        extras = collector.fetch_optional_reels_retention(self.ig, "123", product_type, self.deadline)
        assert {**core, **extras} == {"reach": 98, self.watch: 3000, self.skip: None}
        self.ig._request.side_effect = [Timeout(), self.result(self.skip, 0.753)]
        assert collector.fetch_optional_reels_retention(self.ig, "123", "REELS", self.deadline) == {
            self.watch: None, self.skip: 0.753,
        }

    def test_missing_and_invalid_values_remain_null(self):
        self.ig._request.side_effect = [self.result(self.watch, None), self.result(self.skip, True)]
        assert collector.fetch_optional_reels_retention(self.ig, "123", "REELS", self.deadline) == {
            self.watch: None, self.skip: None,
        }

    def test_no_extra_requests_for_other_media_or_insufficient_time(self):
        assert collector.fetch_optional_reels_retention(self.ig, "123", "FEED", self.deadline) == {}
        assert collector.fetch_optional_reels_retention(self.ig, "123", "REELS", datetime.now(timezone.utc)) == {
            self.watch: None, self.skip: None,
        }
        self.ig._request.assert_not_called()

    def test_retention_stays_in_existing_json_and_out_of_scalar_columns(self):
        session = mock.Mock()
        session.execute.return_value.rowcount = 1
        row = {"media_id": "123", "published_at": self.deadline.isoformat()}
        metrics = {"reach": 98, self.watch: 4279, self.skip: None}
        assert collector._save_snapshot(session, row, "24h", self.deadline, self.deadline, metrics)
        values = session.execute.call_args.args[1]
        assert json.loads(values["metrics_json"]) == metrics
        assert values["reach"] == 98
        assert self.watch not in values and self.skip not in values

    @mock.patch.object(instagram_client.requests, "request")
    def test_generic_client_preserves_existing_timeout_and_accepts_short_override(self, request):
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"ok": True}
        ig = instagram_client.InstagramClient("mock-token", "mock-id")
        ig._request("GET", "123/insights")
        assert request.call_args.kwargs["timeout"] == 30
        ig._request("GET", "123/insights", timeout=4)
        assert request.call_args.kwargs["timeout"] == 4
