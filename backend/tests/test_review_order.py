# tests/test_review_order.py — FR-02（Issue #28）：送別で検索したとき、カードのレビューを送別関連から順に並べるテスト
#
# DB にはつながず、main.fetch_all を差し替えて、商品とレビューのデータを再現する。
# 実行（backend フォルダで）：python -m pytest tests

import pytest

import main

PRODUCT = {
    "product_id": "G0001",
    "category": "スイーツ",
    "brand": "花の店",
    "product_name": "焼き菓子セット",
    "price": 3240,
    "rating": 4.5,
    "review_count": 5,
    "match_count": 1,
}

# DB が返す順（わざとバラバラにしておく）
REVIEWS = [
    {"review_id": "R0001", "product_id": "G0001", "rating": 5, "comment": "誕生日のプレゼントに。", "age_group": "30代", "gender": "女性"},
    {"review_id": "R0002", "product_id": "G0001", "rating": 3, "comment": "退職される上司へ。", "age_group": "40代", "gender": "男性"},
    {"review_id": "R0003", "product_id": "G0001", "rating": 5, "comment": "送別会の記念品に。", "age_group": None, "gender": None},
    {"review_id": "R0004", "product_id": "G0001", "rating": None, "comment": "転勤する後輩に。", "age_group": "20代", "gender": "女性"},
    {"review_id": "R0005", "product_id": "G0001", "rating": 4, "comment": "お歳暮に。", "age_group": "50代", "gender": "男性"},
    {"review_id": "R0006", "product_id": "G0001", "rating": 5, "comment": "異動のあいさつに。", "age_group": "30代", "gender": "男性"},
]


@pytest.fixture
def fake_db(monkeypatch):
    """products / reviews への SELECT を、上のデータで答える偽の fetch_all に差し替える"""
    state = {"products": [dict(PRODUCT)], "reviews": [dict(r) for r in REVIEWS]}

    def fake_fetch_all(query, params=()):
        if "FROM reviews" in query:
            return [dict(r) for r in state["reviews"]]
        if "COUNT(*)" in query:
            return [{"n": len(state["products"])}]
        if "FROM products" in query:
            return [dict(p) for p in state["products"]]
        raise AssertionError(f"想定していない SQL: {query}")

    monkeypatch.setattr(main, "fetch_all", fake_fetch_all)
    return state


def _comments(result):
    return [r["comment"] for r in result["results"][0]["reviews"]]


def test_farewell_search_puts_farewell_reviews_first(fake_db):
    """送別で検索すると、送別関連が先。グループの中は評価の高い順 → review_id の順、評価なしは後ろ"""
    result = main.search_farewell("お菓子", "")
    assert _comments(result) == [
        "送別会の記念品に。",  # 送別関連・★5・R0003
        "異動のあいさつに。",  # 送別関連・★5・R0006
        "退職される上司へ。",  # 送別関連・★3
        "転勤する後輩に。",  # 送別関連・評価なし
        "誕生日のプレゼントに。",  # それ以外・★5
        "お歳暮に。",  # それ以外・★4
    ]


def test_farewell_search_keeps_review_shape(fake_db):
    """並べ替えても、画面に返すレビューの形（authorLabel / comment）は変わらない"""
    reviews = main.search_farewell("", "")["results"][0]["reviews"]
    assert reviews[0] == {"authorLabel": "未回答", "comment": "送別会の記念品に。"}
    assert all(set(r) == {"authorLabel", "comment"} for r in reviews)


def test_farewell_search_without_farewell_reviews(fake_db):
    """送別関連のレビューがない商品でも、今までどおり全件表示される（評価の高い順）"""
    fake_db["reviews"] = [r for r in fake_db["reviews"] if r["review_id"] in ("R0001", "R0005")]
    fake_db["reviews"].reverse()  # DB が ★4 → ★5 の順で返したとする
    assert _comments(main.search_farewell("", "")) == ["誕生日のプレゼントに。", "お歳暮に。"]


def test_farewell_search_without_any_reviews(fake_db):
    """レビューが1件もない商品は、空の配列のまま"""
    fake_db["reviews"] = []
    assert main.search_farewell("", "")["results"][0]["reviews"] == []


def test_other_scene_keeps_db_order(fake_db):
    """送別以外のシーンでは並べ替えない（DB が返した順のまま）"""
    result = main.search(
        q="", category="", scene="誕生日", indiv_wrap=False, room_temp=False,
        price_min=None, price_max=None, limit=20,
    )
    assert _comments(result) == [r["comment"] for r in REVIEWS]
