# product_evidence.py — FR-03 第2段階：商品1件の「根拠」を集める（AI には問い合わせない）
#
# 商品 ID を受け取り、AI に渡してよい根拠（商品説明・商品仕様・購入者レビュー）を、出典 ID を付けて返す。
# chat.py はこの中から質問に関係するものを選んで AI に渡し、AI が挙げた出典 ID がこの一覧にあるかを照合する。
# （証拠に番号を振っておき、書面ではその番号で引用するのと同じ考え方）
#
# 使わないデータ：
#   reviews.user_id・users・orders … 個人情報や注文情報を AI に送らないため
#   reviews.person・reviews.favorite … 要件定義書 5.4：公開・再利用条件が決まるまで出典に使わないため

from database import fetch_all

# この星の数以下のレビューを「否定的」とみなす（★3 はどちらでもない）。
# 否定的なレビューは除かずに印だけ付ける。おすすめの理由に使わないことは、chat.py のプロンプトで守らせる
NEGATIVE_RATING_MAX = 2

# 1商品あたりに集めるレビューの上限。AI に渡すのは、この中から chat.py が選んだ数件だけ
# 開発DBでコメント付きレビューが最も多い商品は163件（2026-11-20 確認）。全件を選択の対象にできるよう200件にする
MAX_REVIEWS = 200

# 商品仕様に加える product_facts の項目と、値（1 / 0）の書き方。
# 商品説明の【保存方法】【包装】【個包装】欄を 1 / 0 にそろえたもの。値がない商品はその項目を書かない
# 使わない項目：
#   shelf_life_days … 数字にすると起点（製造日から・お届け日から）と「以上・約」が消えるため。期限の文は商品説明で届く
#   office_orders   … 注文から集計した値で、「職場向けに選ばれた回数」と誤解されやすいため
SPEC_FACTS = {
    "room_temp": ("常温保存", {1: "可", 0: "不可"}),
    "indiv_wrap": ("個包装", {1: "あり", 0: "なし"}),
}


def get_product_evidence(product_id: str) -> dict | None:
    """商品1件の根拠を返す。商品が存在しなければ None。
    同じ商品なら、いつも同じ内容・同じ順番で返す（商品説明 → 商品仕様 → レビューを review_id 順）"""
    products = fetch_all(
        """SELECT product_id, product_name, price, description, size,
                  delivery_days, gift_wrap, message_card
           FROM products WHERE product_id = %s""",
        (product_id,),
    )
    if not products:
        return None
    p = products[0]

    items = []

    # ① 商品説明。空なら項目を出さない（架空の説明を作らない）
    description = _clean(p.get("description"))
    if description:
        items.append(
            {
                "source_id": f"{p['product_id']}:description",
                "kind": "description",
                "label": "商品説明",
                "text": description,
            }
        )

    # ② 商品仕様（価格・サイズ・配送日数・ラッピング・メッセージカード＋常温保存・個包装）。値がある項目だけ並べる
    facts = fetch_all(
        """SELECT fact, value
           FROM product_facts
           WHERE product_id = %s AND fact IN ('room_temp', 'indiv_wrap')""",
        (product_id,),
    )
    spec = _format_spec(p, {f["fact"]: f["value"] for f in facts})
    if spec:
        items.append(
            {
                "source_id": f"{p['product_id']}:spec",
                "kind": "spec",
                "label": "商品仕様",
                "text": spec,
            }
        )

    # ③ 購入者レビュー。user_id は取らない。コメントが空のものは SQL と Python の両方で除く
    reviews = fetch_all(
        """SELECT review_id, rating, comment
           FROM reviews
           WHERE product_id = %s AND comment IS NOT NULL AND comment != ''
           ORDER BY review_id
           LIMIT %s""",
        (product_id, MAX_REVIEWS),
    )
    for r in sorted(reviews, key=lambda r: r["review_id"])[:MAX_REVIEWS]:
        comment = _clean(r.get("comment"))
        if not comment:
            continue  # 空白だけのコメントも根拠にしない
        rating = r.get("rating")
        items.append(
            {
                "source_id": f"review:{r['review_id']}",
                "kind": "review",
                "label": f"購入者レビュー（★{rating}）" if rating is not None else "購入者レビュー",
                "text": comment,
                "rating": rating,
                "negative": rating is not None and rating <= NEGATIVE_RATING_MAX,
            }
        )

    return {
        "product": {
            "product_id": p["product_id"],
            "product_name": p["product_name"],
            "price": p["price"],
        },
        "items": items,
    }


def _clean(text) -> str:
    """前後の空白を取り除く。None は空文字にする"""
    return text.strip() if isinstance(text, str) else ""


def _format_spec(p: dict, facts: dict | None = None) -> str:
    """商品仕様を1行の文章にする。DB の値が NULL の項目は書かない（分からないことを「なし」と言わない）
    facts は product_facts の {fact: value}。行がない項目や、想定外の値の項目も書かない"""
    facts = facts or {}
    parts = []
    if p.get("price") is not None:
        parts.append(f"価格：{p['price']:,}円")
    size = _clean(p.get("size"))
    if size:
        parts.append(f"サイズ：{size}")
    if p.get("delivery_days") is not None:
        parts.append(f"配送日数：{p['delivery_days']}日")
    if p.get("gift_wrap") is not None:
        parts.append(f"ラッピング：{'対応' if p['gift_wrap'] else '非対応'}")
    if p.get("message_card") is not None:
        parts.append(f"メッセージカード：{'対応' if p['message_card'] else '非対応'}")
    for fact, (label, words) in SPEC_FACTS.items():
        word = words.get(facts.get(fact))
        if word:
            parts.append(f"{label}：{word}")
    return "／".join(parts)
