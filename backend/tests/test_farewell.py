# tests/test_farewell.py — 送別関連レビューの判定（Issue #17）と、チャットがその判定を使っていることのテスト
# 実行（backend フォルダで）：python -m pytest tests

import pytest

import chat
from farewell import FAREWELL_WORDS, is_farewell_related


@pytest.mark.parametrize(
    "text",
    [
        "お世話になった同僚の送別に購入しました。",
        "送別会の記念品に。",
        "部署異動のあいさつに。",
        "退職される上司に、部署のみんなで贈りました。",
        "転勤する後輩に渡しました。",
        "定年を迎える上司へ。",
        "産休に入る同僚へ。",
    ],
)
def test_farewell_related(text):
    assert is_farewell_related(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "取引先へのお礼に。職場で渡すのにちょうどよかったです。",  # 「職場」だけでは送別関連にしない
        "餞別",  # 「餞別」はリストから外した
        "誕生日のプレゼントに。",
        "",
    ],
)
def test_not_farewell_related(text):
    assert is_farewell_related(text) is False


def test_prompt_lists_the_same_words():
    """AI への指示（ルール13）に、件数を数える言葉と同じ一覧が書かれている"""
    assert "（送別・異動・退職・転勤・定年・産休）" in chat.SYSTEM_PROMPT
    assert "・".join(FAREWELL_WORDS) in chat.SYSTEM_PROMPT
    assert "{farewell_words}" not in chat.SYSTEM_PROMPT  # 差し込み忘れがない
    assert "職場・異動" not in chat.SYSTEM_PROMPT  # 古い一覧が残っていない


def _review(source_id, text, negative=False):
    return {"source_id": source_id, "kind": "review", "label": "購入者レビュー", "text": text, "negative": negative}


def test_review_stats_counts_with_shared_words():
    product = {"product_id": "G0001", "product_name": "焼き菓子", "price": 3000}
    items = [
        _review("review:R1", "取引先へのお礼に。職場で渡しやすかった。"),  # 数えない
        _review("review:R2", "定年を迎える上司へ。"),  # 数える
        _review("review:R3", "産休に入る同僚へ。"),  # 数える
    ]
    stats = chat.review_stats_item(product, items)
    assert stats["farewell_review_count"] == 2
    assert stats["text"] == "レビューは全部で3件。そのうち送別に関係する言葉を含むレビューは2件。"


def test_few_reviews_ignores_workplace_only():
    """「職場」だけのレビューしかない商品は、送別関連のレビューがない（few_reviews）扱いになる"""
    assert chat.has_few_reviews([_review("review:R1", "職場で渡しやすかった。")]) is True
    assert chat.has_few_reviews([_review("review:R2", "退職される方へ。")]) is False


def test_select_evidence_bonus_uses_shared_words():
    """送別関連の加点は共通の判定に従う。質問と重なる言葉がない場合、定年のレビューが職場のレビューより先に来る"""
    items = [
        _review("review:R1", "職場で渡しやすかった。"),
        _review("review:R2", "定年を迎える上司へ。"),
    ]
    selected = chat.select_evidence(items, "香りは？")
    assert [i["source_id"] for i in selected] == ["review:R2", "review:R1"]
