"""核心逻辑单元测试：python -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.client import (  # noqa: E402
    ALREADY,
    AUTH_FAILED,
    FAILED,
    RISK,
    SUCCESS,
    CheckinClient,
    CheckinResult,
    _check_json_path,
    _dig,
    _extract_amount,
)
from src.config import Config  # noqa: E402
from src.logger import mask  # noqa: E402
from src.notifier import build_message  # noqa: E402


def make_client(**overrides) -> CheckinClient:
    config = Config(cookie="sessionid=abc; sid=def", url="https://example.com/checkin")
    for key, value in overrides.items():
        setattr(config, key, value)
    return CheckinClient(config)


class TestClassify(unittest.TestCase):
    def test_success_keyword(self):
        status, _ = make_client()._classify(200, '{"message":"签到成功，获得200额度"}')
        self.assertEqual(status, SUCCESS)

    def test_already_wins_over_success(self):
        # 响应里同时出现「签到」和「已签到」，必须判成 ALREADY
        status, _ = make_client()._classify(200, '{"message":"今日已签到，明天再来"}')
        self.assertEqual(status, ALREADY)

    def test_auth_failed(self):
        status, _ = make_client()._classify(200, '{"message":"未登录"}')
        self.assertEqual(status, AUTH_FAILED)

    def test_http_401(self):
        status, _ = make_client()._classify(401, "unauthorized")
        self.assertEqual(status, AUTH_FAILED)

    def test_risk(self):
        status, _ = make_client()._classify(200, '{"message":"请完成验证"}')
        self.assertEqual(status, RISK)

    def test_plain_2xx_is_success(self):
        status, _ = make_client()._classify(204, "")
        self.assertEqual(status, SUCCESS)

    def test_500_is_failed(self):
        status, _ = make_client()._classify(500, "internal error")
        self.assertEqual(status, FAILED)

    def test_custom_json_path(self):
        client = make_client(success_json_path=["data.checkin_status=1"])
        status, _ = client._classify(200, '{"data":{"checkin_status":1}}')
        self.assertEqual(status, SUCCESS)

    def test_json_path_not_match(self):
        client = make_client(success_json_path=["data.checkin_status=1"])
        status, _ = client._classify(200, '{"data":{"checkin_status":0},"msg":"ok"}')
        self.assertEqual(status, SUCCESS)  # 落到 2xx 兜底
        self.assertEqual(client._classify(400, '{"data":{"checkin_status":0}}')[0], FAILED)


class TestRetryPolicy(unittest.TestCase):
    def test_no_retry_on_success_or_already(self):
        client = make_client()
        self.assertFalse(client._should_retry(SUCCESS, 200))
        self.assertFalse(client._should_retry(ALREADY, 200))

    def test_retry_on_5xx_and_network(self):
        client = make_client()
        self.assertTrue(client._should_retry(FAILED, 500))
        self.assertTrue(client._should_retry(FAILED, 0))

    def test_no_retry_on_business_4xx(self):
        client = make_client()
        self.assertFalse(client._should_retry(FAILED, 400))
        self.assertFalse(client._should_retry(FAILED, 404))

    def test_retry_on_429(self):
        client = make_client()
        self.assertTrue(client._should_retry(RISK, 429))


class TestHelpers(unittest.TestCase):
    def test_dig(self):
        data = {"a": {"b": [{"c": 7}]}}
        self.assertEqual(_dig(data, "a.b.0.c"), 7)
        self.assertIsNone(_dig(data, "a.x.y"))

    def test_json_path_rules(self):
        self.assertTrue(_check_json_path({"code": 0}, ["code=0"]))
        self.assertFalse(_check_json_path({"code": 1}, ["code=0"]))
        self.assertIsNone(_check_json_path({"code": 1}, []))

    def test_extract_amount(self):
        self.assertEqual(_extract_amount("签到成功，+200 活动额度"), "200")
        self.assertEqual(_extract_amount('{"amount": 300}'), "300")
        self.assertEqual(_extract_amount("no number"), "")

    def test_mask(self):
        masked = mask("sessionid=abcdefghijklmn")
        self.assertNotIn("abcdefghij", masked)
        self.assertIn("len=", masked)


class TestNotifyMessage(unittest.TestCase):
    def test_success_title_contains_amount(self):
        result = CheckinResult(status=SUCCESS, message="签到成功", amount="200")
        title, body = build_message(result)
        self.assertIn("成功", title)
        self.assertIn("200", title)
        self.assertIn("SUCCESS", body)

    def test_failure_title(self):
        result = CheckinResult(status=FAILED, message="boom", http_status=500)
        title, _ = build_message(result)
        self.assertIn("失败", title)

    def test_ok_property(self):
        self.assertTrue(CheckinResult(status=ALREADY, message="").ok)
        self.assertFalse(CheckinResult(status=FAILED, message="").ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
