# main.py — Giftia 検索API（2週目・穴埋め版）
# 【穴1】〜【穴4】を、対応表と公式ドキュメント・データ定義.md を頼りに自分で埋める。
# 埋めるまでは ___ が残っていて動かない（/api/search を呼ぶと 500 になり、ターミナルに NameError と行番号が出る）。
# 答えは 配布コード/答え合わせ/backend/main.py（自分で埋めてから見る）。
#
# 画面（Next.js）から呼ばれる「窓口」。条件を受け取り、班のDBを検索して、結果を JSON で返す。
# 起動：uvicorn main:app --reload
# 確認：http://localhost:8000/docs（Swagger UI。ブラウザから API を試せる）

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from chat import (
    FAREWELL_SCENE,
    ChatRequest,
    ChatUnavailable,
    InvalidModelResponse,
    ModelError,
    ModelTimeout,
    answer_question,
    is_chat_available,
)
from database import fetch_all
from farewell import is_farewell_related
from farewell_search import build_score_sql  # Issue #26：送別検索の重み付け
from product_evidence import get_product_evidence

load_dotenv()  # .env を読む（DB の接続情報・CORS の許可）

app = FastAPI(title="Giftia Search API（2週目）")

FAREWELL_LIMIT = 5  # FR-01：送別シーンで返す最大件数

# ── CORS ───────────────────────────────────────
# 画面（http://localhost:3000）と API（http://localhost:8000）は別のアプリ＝オリジンが違う。
# ブラウザは既定で「別オリジンへの通信」を止めるので、API 側が「この画面からは受け付ける」と宣言する。
# 許可する画面の URL は .env の CORS_ORIGINS に書く（カンマ区切りで複数可）。空なら何も許可しない。
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
# POST は FR-03 のチャット（/api/chat）で使う
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/api/health")
def health():
    """つながっているかの確認。どの DB に何件の商品があるか"""
    row = fetch_all("SELECT DATABASE() AS db, COUNT(*) AS products FROM products")[0]
    return {"status": "ok", "db": row["db"], "products": row["products"]}


@app.get("/api/search")
def search(
    q: str = Query(default="", description="キーワード（空白区切りで複数。すべてを含む商品）"),
    category: str = Query(default="", description="カテゴリー（空ならすべて）"),
    scene: str = Query(default="", description="シーン。送別のときは送別タグ付き商品を一致数順に最大5件（FR-01）"),
    indiv_wrap: bool = Query(default=False, description="true なら、説明文に「個包装」とある商品だけ"),
    room_temp: bool = Query(default=False, description="true なら、説明文に「常温」とある商品だけ"),  # 常温追加
    price_min: int | None = Query(default=None, ge=0, description="価格の下限（以上）"),
    price_max: int | None = Query(default=None, ge=0, description="価格の上限（以下）"),
    limit: int = Query(default=20, ge=1, le=100, description="返す件数"),
):
    """条件に合う商品を、人気順（直近1年の販売数）で上位 limit 件返す"""
    # FR-01：送別シーンは別の並べ方（送別タグ＋検索語の一致数順・最大5件）。それ以外のシーンはこれまでどおり
    if scene == FAREWELL_SCENE:
        return search_farewell(q, category)

    # ① 条件を WHERE に1つずつ足す（値は %s で渡し、SQL の文字列に直接つなげない）
    where, params = ["stock > 0"], []  # 在庫切れは出さない
    for word in q.split():  # 【穴1】q を空白で区切って1語ずつにする（文字列のメソッド）
        where.append("(product_name LIKE %s OR brand LIKE %s OR description LIKE %s)")
        params += [f"%{word}%"] * 3
    if category:
        where.append("category = %s")
        params.append(category)  # 【穴2】%s に入れる値（受け取ったカテゴリー）
    if indiv_wrap:
        where.append("description LIKE %s")  # 「個包装」は列がないので、説明文に書いてあるかで見る
        params.append("%個包装%")  # 【穴3】「個包装」をどこかに含む、という LIKE のパターン
    if room_temp: # 常温だけの場合の条件追加
        where.append("description LIKE %s")  # 「常温」は列がないので、説明文に書いてあるかで見る
        params.append("%常温%")  # 「常温」をどこかに含む、という LIKE のパターン
    if price_min is not None:
        where.append("price >= %s")
        params.append(price_min)
    if price_max is not None:
        where.append("price <= %s")
        params.append(price_max)
    condition = " AND ".join(where)

    # ② 件数と、人気順の上位 limit 件を取る
    total = fetch_all(f"SELECT COUNT(*) AS n FROM products WHERE {condition}", tuple(params))[0]["n"]
    rows = fetch_all(
        f"""SELECT product_id, category, brand, product_name, price, rating, review_count
            FROM products WHERE {condition}
            # 人気順は一旦無効化
            # ORDER BY sales_count DESC, product_id
            ORDER BY rating DESC, product_id
            LIMIT %s""",
        (*params, limit),
    )
    # ③ レビューを一括取得して、画面の Gift 型に詰め替えて返す
    return {"total": total, "results": to_gifts_with_reviews(rows)}


def search_farewell(q: str, category: str) -> dict:
    """FR-01：送別タグ付き・在庫ありの商品を、検索語の一致数 → 評価 → レビュー件数 → 商品ID の順で最大5件返す"""
    # 同じ語が重複していても1語として数える（例：「お酒 お酒」は「お酒」と同じ）※未決事項：チームで確認
    words = list(dict.fromkeys(q.split()))

    # ① 点数：1語ごとに、一致した場所で点を付ける（商品名3 > ブランド2 > 説明文1）。同義語にも一致させる（Issue #26）
    score_sql, score_params = build_score_sql(words)

    # ② 候補は送別タグで取る（キーワードだけでは候補が足りないため）
    where = [
        "p.stock > 0",
        "EXISTS (SELECT 1 FROM product_scenes ps WHERE ps.product_id = p.product_id AND ps.scene_tag = %s)",
    ]
    where_params = [FAREWELL_SCENE]
    if category:
        where.append("p.category = %s")
        where_params.append(category)
    # Issue #31：キーワードがあるときは、どの語にも一致しない（0点の）商品を出さない。空なら送別商品を評価順に出す
    # 点数の式は WHERE の最後に置き、その %s の値も where_params の最後に足す（COUNT と本体の両方で順番がそろう）
    if words:
        where.append(f"({score_sql}) > 0")
        where_params += score_params
    condition = " AND ".join(where)

    total = fetch_all(f"SELECT COUNT(*) AS n FROM products p WHERE {condition}", tuple(where_params))[0]["n"]
    rows = fetch_all(
        f"""SELECT p.product_id, p.category, p.brand, p.product_name, p.price, p.rating, p.review_count,
                   ({score_sql}) AS match_count
            FROM products p
            WHERE {condition}
            ORDER BY match_count DESC,
                     p.rating IS NULL, p.rating DESC,
                     p.review_count DESC,
                     p.product_id
            LIMIT %s""",
        # SELECT 内の %s（一致数）が先、WHERE の %s（Issue #31 の点数の条件を含む）が後。順番を入れ替えると順位がおかしくなる
        (*score_params, *where_params, FAREWELL_LIMIT),
    )
    # rating が NULL の商品は後ろに回す（p.rating IS NULL が 0→1 の順）※未決事項：チームで確認
    # FR-02（Issue #28）：送別のときだけ、カードのレビューを送別関連から順に並べる
    return {"total": total, "results": to_gifts_with_reviews(rows, farewell_first=True)}


    #reviews テーブル（エイリアス r）に users テーブル（エイリアス u）を LEFT JOIN で結合し、
    # age_group と gender を1回のSQLでまとめて取得します。
    # 性別は "女性" または "男性" のみそのまま返し、それ以外（None・空文字・その他の値）は "未回答" にします。

def _format_author_label(age_group: str | None, gender: str | None) -> str:
    """年齢層と性別から表示用ラベル（例: '30代・女性'、'30代・未回答'）を作る"""
    clean_age = (age_group or "").strip()
    clean_gender = (gender or "").strip()
    gender_label = clean_gender if clean_gender in ("女性", "男性") else "未回答"

    if clean_age:
        return f"{clean_age}・{gender_label}"
    return gender_label


def _farewell_review_order(rev: dict) -> tuple:
    """FR-02（Issue #28）：送別関連 → それ以外。同じグループの中は評価の高い順（評価なしは後ろ）→ review_id の順"""
    rating = rev.get("rating")
    return (
        not is_farewell_related(rev.get("comment") or ""),  # False（送別関連）が先
        rating is None,  # 評価なしは後ろ
        -(rating or 0),  # 評価の高い順
        rev.get("review_id") or "",  # 同じ評価なら review_id の順（毎回同じ並びにする）
    )


def to_gifts_with_reviews(rows: list[dict], farewell_first: bool = False) -> list[dict]:
    """商品の行にレビュー（属性ラベル+コメント）を付けて、Gift 型のリストにする（レビューは IN 句で1回のSQLでまとめて取る）
    farewell_first=True（送別で検索したとき）は、商品ごとのレビューを送別関連から順に並べる（FR-02）"""
    if not rows:
        return []

    # 1. 取得した商品すべての product_id をリストにする
    product_ids = [r["product_id"] for r in rows]

    # 2. IN句を使って、該当する商品のレビューを「1回のSQL」でまとめて取得する
    format_strings = ','.join(['%s'] * len(product_ids))
    # r.user_id と u.user_id を紐づけて一括取得（ユーザー情報が欠損していてもレビューは残すため LEFT JOIN）
    all_reviews = fetch_all(
        f"""SELECT
                r.review_id,
                r.product_id,
                r.rating,
                r.comment,
                u.age_group,
                u.gender
            FROM reviews r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.product_id IN ({format_strings}) 
              AND r.comment IS NOT NULL 
              AND TRIM(r.comment) != ''""",
        tuple(product_ids)
    )

    # 送別のときだけ並べ替える。それ以外のシーンは今までどおり（DB が返した順）
    if farewell_first:
        all_reviews = sorted(all_reviews, key=_farewell_review_order)

    # 3. 取得した全レビューを product_id ごとに辞書（マップ）に整理する
    reviews_map: dict[str, list[dict]] = {}
    for rev in all_reviews:
        clean_comment = rev["comment"].strip()
        if not clean_comment:
            continue

        reviews_map.setdefault(rev["product_id"], []).append(
            {
                "authorLabel": _format_author_label(rev.get("age_group"), rev.get("gender")),
                "comment": clean_comment,
            }
        )

    # 4. 各商品データに、整理したレビューの配列を割り当てる（DBへの追加クエリは0回！）
    #results = []
    #if rows:
        # 1. 取得した商品すべての product_id をリストにする
    #    product_ids = [r["product_id"] for r in rows]

        # 2. IN句を使って、該当する商品のレビューを「1回のSQL」でまとめて取得する
    #    format_strings = ','.join(['%s'] * len(product_ids))
    #    all_reviews = fetch_all(
    #        f"""SELECT product_id, comment 
    #            FROM reviews 
    #            WHERE product_id IN ({format_strings}) 
    #              AND comment IS NOT NULL 
    #              AND comment != ''""",
    #        tuple(product_ids)
    #    )

        # 3. 取得した全レビューを product_id ごとに辞書（マップ）に整理する
    #    reviews_map = {}
    #    for rev in all_reviews:
    #        pid = rev["product_id"]
    #        if pid not in reviews_map:
    #            reviews_map[pid] = []
    #        reviews_map[pid].append(rev["comment"])

        # 4. 各商品データに、整理したレビューの配列を割り当てる（DBへの追加クエリは0回！）
    results = []
    for r in rows:
        r["reviews"] = reviews_map.get(r["product_id"], [])
        results.append(to_gift(r))
    # ④ 画面の Gift 型に詰め替えたリストを返す
    return results #{"total": total, "results": results}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """FR-03：商品1件について1問ずつ、商品説明とレビューを根拠に AI が答える"""
    # ① 送別シーンが選ばれているかを API 側でも確かめる（画面の表示だけに頼らない）
    if not is_chat_available(req.scene_tag):
        raise HTTPException(status_code=400, detail="送別シーンが選ばれていないため、チャットは使えません")

    # ② 商品 ID をサーバーで照合し、根拠（商品説明・商品仕様・レビュー）を集める
    evidence = get_product_evidence(req.product_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    # ③ AI に聞いて、出典を照合した回答を返す。失敗したら画面が「再試行」を出せるようにエラーで返す
    try:
        return answer_question(evidence, req.question)
    except ChatUnavailable:
        raise HTTPException(status_code=503, detail="AI チャットの設定が済んでいません")
    except ModelTimeout:
        raise HTTPException(status_code=504, detail="AI の応答が時間内に返りませんでした")
    except (ModelError, InvalidModelResponse):
        raise HTTPException(status_code=502, detail="AI の回答を取得できませんでした")


def to_gift(r: dict) -> dict:
    """DB の列名 → 画面（lib/api.ts の Gift 型）の項目名。画面側は1週目のまま変えない"""
    return {
        "id": r["product_id"],
        "category": r["category"],
        "brand": r["brand"],
        "name": r["product_name"],  # 【穴4】商品名の列名（データ定義.md の products を見る）
        "price": r["price"],
        "rating": float(r["rating"]) if r["rating"] is not None else 0,  # レビューなしは 0
        "reviewCount": r["review_count"],
        "reviews": r.get("reviews", []),  # 【追加】レビューコメントの配列
    }
