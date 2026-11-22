# tests/test_farewell_search.py — 送別検索の重み付け（Issue #26）のテスト
# 実行（backend フォルダで）：python -m pytest tests
#
# DB にはつながない。build_score_sql が作る点数の式を、メモリ上の SQLite で動かして順位を確かめる。
# SQLite でも CASE・LIKE・足し算は MySQL と同じように動く（%s だけ SQLite の ? に置き換える）。

import sqlite3

import pytest

import farewell_search
from farewell_search import BRAND_POINT, DESCRIPTION_POINT, NAME_POINT, build_score_sql, expand_word

# テスト用の架空の商品（送別タグ付き・在庫ありの候補だけを想定）
PRODUCTS = [
    # product_id, product_name, brand, description, rating, review_count
    ("G1", "播州の手焼きお煎餅", "米菓の里", "香ばしいお煎餅です。お酒に合います。", 4.9, 100),
    ("G2", "純米大吟醸 飲み比べセット", "酒蔵A", "職場の送別に。", 4.0, 10),
    ("G3", "赤ワイン 2本セット", "ワイナリーB", "上司への贈り物に。", 3.8, 5),
    ("G4", "焼き菓子アソート 個包装", "洋菓子C", "上司へのお礼に。個包装で配りやすい。", 4.5, 50),
    ("G5", "ドリップコーヒー詰め合わせ", "珈琲D", "朝のひとときに。", 4.2, 20),
    ("G6", "バタークッキー缶", "洋菓子C", "コーヒーに合うクッキーです。", 4.8, 80),
]


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE products (product_id, product_name, brand, description, rating, review_count)")
    con.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", PRODUCTS)
    return con


def rank(q: str) -> list[str]:
    """main.search_farewell と同じ並べ方（点数 → 評価 → レビュー件数 → 商品ID）で、上位5件の商品IDを返す"""
    score_sql, params = build_score_sql(list(dict.fromkeys(q.split())))
    sql = f"""SELECT p.product_id, ({score_sql}) AS match_count FROM products p
              ORDER BY match_count DESC, p.rating IS NULL, p.rating DESC, p.review_count DESC, p.product_id
              LIMIT 5""".replace("%s", "?")
    return [row[0] for row in _db().execute(sql, params)]


def score_of(q: str, product_id: str) -> int:
    score_sql, params = build_score_sql(list(dict.fromkeys(q.split())))
    sql = f"SELECT ({score_sql}) FROM products p WHERE p.product_id = ?".replace("%s", "?")
    return _db().execute(sql, (*params, product_id)).fetchone()[0]


# ── 点数の式そのもの ─────────────────────────────


@pytest.mark.parametrize("q", ["", "上司", "お酒", "上司 お酒", "お菓子 個包装 コーヒー"])
def test_placeholders_match_params(q):
    """SQL の %s の数と、渡す値の数がそろっている（ずれると順位がおかしくなる）"""
    sql, params = build_score_sql(q.split())
    assert sql.count("%s") == len(params)


def test_empty_keyword_is_zero():
    assert build_score_sql([]) == ("0", [])


def test_unknown_word_is_not_expanded():
    assert expand_word("タオル") == ("タオル",)


def test_synonyms_have_no_single_character_word():
    """1文字の語は誤って一致しやすいので辞書に入れない（例：「酒」→「酒粕」）"""
    for terms in farewell_search.SYNONYMS.values():
        assert all(len(t) >= 2 for t in terms)


def test_points_by_place():
    assert score_of("煎餅", "G1") == NAME_POINT  # 商品名
    assert score_of("洋菓子C", "G4") == BRAND_POINT  # ブランドだけ
    assert score_of("上司", "G3") == DESCRIPTION_POINT  # 説明文だけ
    assert score_of("タオル", "G1") == 0


def test_one_word_counts_once():
    """商品名と説明文の両方にあっても、言い換えが複数一致しても、1語ぶんの点だけ"""
    assert score_of("お煎餅", "G1") == NAME_POINT  # 商品名にも説明文にもある
    assert score_of("お菓子", "G4") == NAME_POINT  # 「菓子」「焼き菓子」…いくつ一致しても3点


# ── 確認表（Issue #26）──────────────────────────


def test_sake_ranks_above_senbei_that_goes_with_sake():
    """「上司 お酒」：お酒そのもの（G2・G3）が、「お酒に合います」のお煎餅（G1）より上"""
    order = rank("上司 お酒")
    assert order.index("G2") < order.index("G1")
    assert order.index("G3") < order.index("G1")


def test_coffee_ranks_above_cookie_that_goes_with_coffee():
    """「コーヒー」：コーヒーそのもの（G5）が、「コーヒーに合う」クッキー（G6）より上"""
    order = rank("コーヒー")
    assert order.index("G5") < order.index("G6")


def test_individually_wrapped_sweets_first():
    """「お菓子 個包装」：個包装の焼き菓子（G4）が1位"""
    assert rank("お菓子 個包装")[0] == "G4"


@pytest.mark.parametrize("q", ["上司 お酒", "お菓子 個包装", "コーヒー", ""])
def test_same_result_every_time(q):
    assert rank(q) == rank(q) == rank(q)
