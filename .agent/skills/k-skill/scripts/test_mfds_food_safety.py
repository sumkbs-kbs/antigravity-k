import importlib
import unittest
from collections.abc import Callable
from typing import Protocol, TypedDict, cast

Payload = dict[str, object]


class FoodInterview(TypedDict):
    domain: str
    question: str
    symptoms: str
    must_ask: list[str]
    red_flags: list[str]
    urgent_action: str
    policy: str


class RequestLike(Protocol):
    full_url: str


class MfdsFoodSafetyModule(Protocol):
    def build_food_interview(self, question: str | None = None, symptoms: str | None = None) -> FoodInterview: ...

    def filter_food_items(self, items: list[Payload], query: str) -> list[Payload]: ...

    def normalize_food_recall_row(self, row: Payload) -> Payload: ...

    def normalize_improper_food_item(self, item: Payload) -> Payload: ...

    def resolve_proxy_base_url(self, explicit_base_url: str | None = None, env: dict[str, str] | None = None) -> str: ...

    def search_food_safety(
        self,
        query: str,
        *,
        limit: int = 10,
        base_url: str | None = None,
        request_json: Callable[[object], Payload],
    ) -> Payload: ...


mfds_food_safety = cast(MfdsFoodSafetyModule, cast(object, importlib.import_module("scripts.mfds_food_safety")))
build_food_interview = mfds_food_safety.build_food_interview
filter_food_items = mfds_food_safety.filter_food_items
normalize_food_recall_row = mfds_food_safety.normalize_food_recall_row
normalize_improper_food_item = mfds_food_safety.normalize_improper_food_item
resolve_proxy_base_url = mfds_food_safety.resolve_proxy_base_url
search_food_safety = mfds_food_safety.search_food_safety


class FoodInterviewTest(unittest.TestCase):
    def test_build_food_interview_requires_symptom_followup_and_red_flags(self):
        interview: FoodInterview = build_food_interview(
            question="이 김밥 먹어도 되나요?",
            symptoms="복통과 설사",
        )

        self.assertEqual(interview["domain"], "food")
        self.assertTrue(any("언제" in item for item in interview["must_ask"]))
        self.assertTrue(any("얼마나" in item for item in interview["must_ask"]))
        self.assertTrue(any("기저질환" in item for item in interview["must_ask"]))
        self.assertTrue(any("알레르기" in item for item in interview["must_ask"]))
        self.assertTrue(any("혈변" in item for item in interview["red_flags"]))
        self.assertTrue(any("탈수" in item for item in interview["red_flags"]))
        self.assertIn("응급실", interview["urgent_action"])


class FoodNormalizationTest(unittest.TestCase):
    def test_normalize_food_recall_row_keeps_official_recall_fields(self):
        item = normalize_food_recall_row(
            {
                "PRDLST_NM": "맛있는김밥",
                "BSSH_NM": "예시식품",
                "RTRVLPRVNS": "대장균 기준 규격 부적합",
                "CRET_DTM": "2026-04-07 18:03:56.058442",
                "DISTBTMLMT": "2027-12-18",
                "PRDLST_TYPE": "가공식품",
            }
        )

        self.assertEqual(item["source"], "foodsafetykorea_recall")
        self.assertEqual(item["product_name"], "맛있는김밥")
        self.assertEqual(item["company_name"], "예시식품")
        self.assertIn("대장균", cast(str, item["reason"]))
        self.assertEqual(item["category"], "가공식품")

    def test_normalize_improper_food_item_keeps_official_improper_food_fields(self):
        item = normalize_improper_food_item(
            {
                "PRDUCT": "예시 유부초밥",
                "ENTRPS": "예시푸드",
                "IMPROPT_ITM": "황색포도상구균",
                "INSPCT_RESULT": "기준 부적합",
                "FOOD_TY": "즉석조리식품",
                "REGIST_DT": "2026-04-08",
            }
        )

        self.assertEqual(item["source"], "mfds_improper_food")
        self.assertEqual(item["product_name"], "예시 유부초밥")
        self.assertEqual(item["company_name"], "예시푸드")
        self.assertIn("황색포도상구균", cast(str, item["reason"]))

    def test_filter_food_items_matches_product_and_company_names(self):
        items: list[Payload] = [
            {"product_name": "맛있는김밥", "company_name": "예시식품"},
            {"product_name": "사과주스", "company_name": "김밥나라"},
        ]

        by_product = filter_food_items(items, "김밥")
        by_company = filter_food_items(items, "나라")

        self.assertEqual(len(by_product), 1)
        self.assertEqual(by_product[0]["product_name"], "맛있는김밥")
        self.assertEqual(len(by_company), 1)
        self.assertEqual(by_company[0]["company_name"], "김밥나라")


class ProxyResolutionTest(unittest.TestCase):
    def test_resolve_proxy_base_url_defaults_to_hosted_proxy(self):
        self.assertEqual(resolve_proxy_base_url(None, env={}), "https://k-skill-proxy.nomadamas.org")
        self.assertEqual(
            resolve_proxy_base_url(None, env={"KSKILL_PROXY_BASE_URL": "https://proxy.example.com/"}),
            "https://proxy.example.com",
        )
        with self.assertRaisesRegex(ValueError, "KSKILL_PROXY_BASE_URL"):
            _ = resolve_proxy_base_url(None, env={"KSKILL_PROXY_BASE_URL": "off"})

    def test_search_food_safety_uses_proxy_route(self):
        captured: dict[str, str] = {}

        def fake_request_json(request: object) -> Payload:
            request_like = cast(RequestLike, request)
            captured["url"] = request_like.full_url
            return {"items": [], "warnings": []}

        payload: Payload = search_food_safety(
            "김밥",
            limit=4,
            base_url="https://proxy.example.com",
            request_json=fake_request_json,
        )

        self.assertEqual(payload, {"items": [], "warnings": []})
        self.assertIn("https://proxy.example.com/v1/mfds/food-safety/search", captured["url"])
        self.assertIn("query=%EA%B9%80%EB%B0%A5", captured["url"])
        self.assertIn("limit=4", captured["url"])


if __name__ == "__main__":
    _ = unittest.main()
