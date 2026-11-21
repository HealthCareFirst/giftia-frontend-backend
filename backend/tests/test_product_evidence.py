# tests/test_product_evidence.py — FR-03 第2段階：根拠を集める処理のテスト
#
# DB にはつながず、product_evidence.fetch_all を差し替えて、商品とレビューのデータを再現する。
# 実行（backend フォルダで）：python -m pytest tests

import pytest

import product_evidence
from product_evidence import get_product_evidence

PRODUCT = {
    "product_id": "G0001",
    "product_name": "花の店 ブーケ お花とお菓子のセット（焼き菓子）",
    "price": 3240,
    "description": "  焼き菓子12個入り。個包装で配りやすいセットです。  ",
    "size": "幅20cm",
    "delivery_days": 3,
    "gift_wrap": 1,
    "message_card": 0,
}

# user_id は、SQL で取らなくても混ざっていないことを確かめるために、わざと入れておく
REVIEWS = [
    {"review_id": "R0003", "user_id": "U9999", "rating": 2, "comment": "量が少なく物足りなかった"},
    {"review_id": "R0001", "user_id": "U9999", "rating": 5, "comment": "職場で配りやすかった"},
    {"review_id": "R0002", "user_id": "U9999", "rating": 4, "comment": "   "},  # 空白だけ
    {"review_id": "R0004", "user_id": "U9999", "rating": 3, "comment": None},  # NULL
    {"review_id": "R0005", "user_id": "U9999", "rating": 3, "comment": ""},  # 空文字
]


@pytest.fixture
def fake_db(monkeypatch):
    """products / product_facts / reviews への SELECT を、上のデータで答える偽の fetch_all に差し替える
    facts は最初は空（product_facts に行がない商品）。テストごとに {fact: value} を入れる"""
    state = {"products": {"G0001": dict(PRODUCT)}, "facts": {}, "reviews": list(REVIEWS), "queries": []}

    def fake_fetch_all(query, params=()):
        state["queries"].append(query)
        if "FROM product_facts" in query:
            return [{"fact": fact, "value": value} for fact, value in state["facts"].items()]
        if "FROM products" in query:
            product = state["products"].get(params[0])
            return [product] if product else []
        if "FROM reviews" in query:
            return [dict(r) for r in state["reviews"]]
        raise AssertionError(f"想定していない SQL: {query}")

    monkeypatch.setattr(product_evidence, "fetch_all", fake_fetch_all)
    return state


def test_returns_none_for_unknown_product(fake_db):
    assert get_product_evidence("G9999") is None


def test_returns_description_spec_and_reviews(fake_db):
    evidence = get_product_evidence("G0001")

    assert evidence["product"] == {
        "product_id": "G0001",
        "product_name": PRODUCT["product_name"],
        "price": 3240,
    }
    by_id = {item["source_id"]: item for item in evidence["items"]}

    assert by_id["G0001:description"]["text"] == "焼き菓子12個入り。個包装で配りやすいセットです。"
    assert by_id["G0001:spec"]["text"] == (
        "価格：3,240円／サイズ：幅20cm／配送日数：3日／ラッピング：対応／メッセージカード：非対応"
    )
    assert by_id["review:R0001"]["text"] == "職場で配りやすかった"
    assert by_id["review:R0001"]["label"] == "購入者レビュー（★5）"


def test_skips_empty_null_and_blank_comments(fake_db):
    source_ids = [item["source_id"] for item in get_product_evidence("G0001")["items"]]

    assert "review:R0002" not in source_ids  # 空白だけ
    assert "review:R0004" not in source_ids  # NULL
    assert "review:R0005" not in source_ids  # 空文字


def test_marks_low_rated_reviews_as_negative(fake_db):
    by_id = {item["source_id"]: item for item in get_product_evidence("G0001")["items"]}

    assert by_id["review:R0003"]["negative"] is True  # ★2
    assert by_id["review:R0001"]["negative"] is False  # ★5


def test_does_not_include_user_id(fake_db):
    evidence = get_product_evidence("G0001")

    assert "U9999" not in repr(evidence)
    assert all("user_id" not in query for query in fake_db["queries"])


def test_order_is_stable(fake_db):
    first = get_product_evidence("G0001")
    fake_db["reviews"].reverse()  # DB から返る順番が変わっても
    second = get_product_evidence("G0001")

    expected = ["G0001:description", "G0001:spec", "review:R0001", "review:R0003"]
    assert [item["source_id"] for item in first["items"]] == expected
    assert [item["source_id"] for item in second["items"]] == expected


def test_no_description_item_when_description_is_empty(fake_db):
    fake_db["products"]["G0001"]["description"] = "  "

    kinds = [item["kind"] for item in get_product_evidence("G0001")["items"]]
    assert "description" not in kinds


def test_spec_omits_null_values(fake_db):
    fake_db["products"]["G0001"].update({"size": None, "delivery_days": None, "gift_wrap": None})

    by_id = {item["source_id"]: item for item in get_product_evidence("G0001")["items"]}
    assert by_id["G0001:spec"]["text"] == "価格：3,240円／メッセージカード：非対応"


def _spec_text(fake_db) -> str:
    by_id = {item["source_id"]: item for item in get_product_evidence("G0001")["items"]}
    return by_id["G0001:spec"]["text"]


BASE_SPEC = "価格：3,240円／サイズ：幅20cm／配送日数：3日／ラッピング：対応／メッセージカード：非対応"


def test_spec_adds_room_temp_and_indiv_wrap_when_true(fake_db):
    fake_db["facts"] = {"room_temp": 1, "indiv_wrap": 1}

    assert _spec_text(fake_db) == BASE_SPEC + "／常温保存：可／個包装：あり"


def test_spec_adds_room_temp_and_indiv_wrap_when_false(fake_db):
    # 0 は「判定できた結果が いいえ」なので書く（要冷蔵の商品、1箱にまとめて梱包の商品など）
    fake_db["facts"] = {"room_temp": 0, "indiv_wrap": 0}

    assert _spec_text(fake_db) == BASE_SPEC + "／常温保存：不可／個包装：なし"


def test_spec_omits_facts_without_rows(fake_db):
    # 行がない＝説明文に欄がなく判定できない。「なし」と書かない
    fake_db["facts"] = {"indiv_wrap": 1}

    assert _spec_text(fake_db) == BASE_SPEC + "／個包装：あり"


def test_spec_ignores_unused_and_unexpected_facts(fake_db):
    # SQL で絞っていても、使わない項目や想定外の値が来たら書かない
    fake_db["facts"] = {"shelf_life_days": 240, "office_orders": 12, "room_temp": 2}

    assert _spec_text(fake_db) == BASE_SPEC


def test_facts_query_reads_only_room_temp_and_indiv_wrap(fake_db):
    get_product_evidence("G0001")

    facts_queries = [q for q in fake_db["queries"] if "FROM product_facts" in q]
    assert len(facts_queries) == 1
    assert "'room_temp'" in facts_queries[0] and "'indiv_wrap'" in facts_queries[0]
    assert "shelf_life_days" not in facts_queries[0] and "office_orders" not in facts_queries[0]


def test_caps_number_of_reviews(fake_db):
    fake_db["reviews"] = [
        {"review_id": f"R{i:04d}", "rating": 5, "comment": f"コメント{i}"}
        for i in range(product_evidence.MAX_REVIEWS + 50)
    ]

    reviews = [item for item in get_product_evidence("G0001")["items"] if item["kind"] == "review"]
    assert len(reviews) == product_evidence.MAX_REVIEWS
