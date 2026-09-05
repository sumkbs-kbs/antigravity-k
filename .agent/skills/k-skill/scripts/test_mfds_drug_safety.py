import importlib
import unittest
import urllib.request
from collections.abc import Callable
from typing import Protocol, cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class _DrugSafetyModule(Protocol):
    def build_drug_interview(self, question: str | None = None, symptoms: str | None = None) -> JsonObject: ...

    def lookup_drugs(
        self,
        item_names: list[str],
        *,
        limit: int = 5,
        base_url: str | None = None,
        request_json: Callable[[urllib.request.Request | str], JsonObject],
    ) -> JsonObject: ...

    def normalize_easy_drug_item(self, item: dict[str, JsonValue]) -> JsonObject: ...

    def normalize_safe_stad_item(self, item: dict[str, JsonValue]) -> JsonObject: ...

    def resolve_proxy_base_url(self, explicit_base_url: str | None = None, env: dict[str, str] | None = None) -> str: ...


mfds_drug_safety = cast(_DrugSafetyModule, cast(object, importlib.import_module("scripts.mfds_drug_safety")))
build_drug_interview = mfds_drug_safety.build_drug_interview
lookup_drugs = mfds_drug_safety.lookup_drugs
normalize_easy_drug_item = mfds_drug_safety.normalize_easy_drug_item
normalize_safe_stad_item = mfds_drug_safety.normalize_safe_stad_item
resolve_proxy_base_url = mfds_drug_safety.resolve_proxy_base_url


def _text(value: JsonValue) -> str:
    return value if isinstance(value, str) else str(value)


def _text_list(payload: JsonObject, key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


class DrugInterviewTest(unittest.TestCase):
    def test_build_drug_interview_requires_followup_questions_and_red_flags(self):
        interview = build_drug_interview(
            question="타이레놀이랑 판콜 같이 먹어도 되나요?",
            symptoms="두드러기와 어지러움",
        )

        self.assertEqual(interview["domain"], "drug")
        must_ask = _text_list(interview, "must_ask")
        red_flags = _text_list(interview, "red_flags")
        self.assertIn("누가 복용하려는지", must_ask[0])
        self.assertTrue(any("얼마나" in item for item in must_ask))
        self.assertTrue(any("복용 중인 약" in item for item in must_ask))
        self.assertTrue(any("알레르기" in item for item in must_ask))
        self.assertTrue(any("호흡곤란" in item for item in red_flags))
        self.assertTrue(any("의식" in item for item in red_flags))
        self.assertIn("즉시 119", _text(interview["urgent_action"]))


class DrugNormalizationTest(unittest.TestCase):
    def test_normalize_easy_drug_item_extracts_public_safety_summary(self):
        item = normalize_easy_drug_item(
            {
                "item_name": "타이레놀정160밀리그램",
                "company_name": "한국얀센",
                "efficacy": "감기로 인한 발열 및 동통에 사용합니다.",
                "how_to_use": "만 12세 이상은 필요시 복용합니다.",
                "warnings": "매일 세 잔 이상 술을 마시는 사람은 전문가와 상의하십시오.",
                "cautions": "간질환 환자는 주의하십시오.",
                "interactions": "다른 해열진통제와 함께 복용하지 마십시오.",
                "side_effects": "발진, 구역이 나타날 수 있습니다.",
                "storage": "실온 보관하십시오.",
            }
        )

        self.assertEqual(item["source"], "drug_easy_info")
        self.assertEqual(_text(item["item_name"]), "타이레놀정160밀리그램")
        self.assertEqual(_text(item["company_name"]), "한국얀센")
        self.assertIn("발열", _text(item["efficacy"]))
        self.assertIn("해열진통제", _text(item["interactions"]))
        self.assertIn("실온", _text(item["storage"]))

    def test_normalize_safe_stad_item_extracts_store_medicine_fields(self):
        item = normalize_safe_stad_item(
            {
                "item_name": "어린이타이레놀현탁액",
                "company_name": "한국존슨앤드존슨판매(유)",
                "efficacy": "해열 및 진통",
                "how_to_use": "용법에 따라 복용",
                "warnings": "과량복용 주의",
                "interactions": "다른 아세트아미노펜 제제와 병용 주의",
                "side_effects": "드물게 발진",
            }
        )

        self.assertEqual(item["source"], "safe_standby_medicine")
        self.assertEqual(_text(item["item_name"]), "어린이타이레놀현탁액")
        self.assertIn("아세트아미노펜", _text(item["interactions"]))


class ProxyResolutionTest(unittest.TestCase):
    def test_resolve_proxy_base_url_defaults_to_hosted_proxy(self):
        self.assertEqual(resolve_proxy_base_url(None, env={}), "https://k-skill-proxy.nomadamas.org")
        self.assertEqual(
            resolve_proxy_base_url(None, env={"KSKILL_PROXY_BASE_URL": "https://proxy.example.com/"}),
            "https://proxy.example.com",
        )
        with self.assertRaisesRegex(ValueError, "KSKILL_PROXY_BASE_URL"):
            _ = resolve_proxy_base_url(None, env={"KSKILL_PROXY_BASE_URL": "off"})

    def test_lookup_drugs_uses_proxy_route(self):
        captured: dict[str, str] = {}

        def fake_request_json(request: urllib.request.Request | str) -> JsonObject:
            captured["url"] = request.full_url if isinstance(request, urllib.request.Request) else request
            return {"items": []}

        payload = lookup_drugs(
            ["타이레놀", "판콜"],
            limit=3,
            base_url="https://proxy.example.com",
            request_json=fake_request_json,
        )

        self.assertEqual(payload, {"items": []})
        self.assertIn("https://proxy.example.com/v1/mfds/drug-safety/lookup", captured["url"])
        self.assertIn("itemName=%ED%83%80%EC%9D%B4%EB%A0%88%EB%86%80", captured["url"])
        self.assertIn("itemName=%ED%8C%90%EC%BD%9C", captured["url"])
        self.assertIn("limit=3", captured["url"])


if __name__ == "__main__":
    _ = unittest.main()
