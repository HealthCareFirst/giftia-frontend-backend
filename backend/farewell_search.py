# farewell_search.py — 送別検索の重み付け（Issue #26）
# 検索語が「どこに」一致したかで点を変え（商品名 > ブランド > 説明文）、同義語にも一致させる。
# main.py の search_farewell から、点数の SQL の式を作るために使う。

# 一致した場所ごとの点数。1語につき、いちばん高い点だけ数える
# 商品名にあればその商品そのもの、説明文だけなら「お酒に合います」のような脇の話のことがあるため
NAME_POINT = 3  # 商品名
BRAND_POINT = 2  # ブランド
DESCRIPTION_POINT = 1  # 説明文だけ

# 同義語の辞書：左の語で検索されたら、右のどれかに一致すれば「その語に一致」とみなす
# 言い換えがいくつ一致しても1語ぶんの点だけ。1文字の語は入れない（「酒」→「酒粕」などに一致するため）
# ※暫定の一覧。DB の商品名を確認して見直す（Issue #26 の未決事項）
SYNONYMS = {
    "お酒": ("お酒", "日本酒", "吟醸", "ワイン", "ビール", "焼酎", "ウイスキー", "梅酒"),
    "お菓子": ("お菓子", "菓子", "クッキー", "せんべい", "煎餅", "チョコ"),
    "コーヒー": ("コーヒー", "珈琲"),
}


def expand_word(word: str) -> tuple[str, ...]:
    """検索語を、同義語の辞書で言い換えの一覧にする。辞書にない語はその語だけ"""
    return SYNONYMS.get(word, (word,))


def build_score_sql(words: list[str]) -> tuple[str, list[str]]:
    """検索語ごとの点数を足し合わせる SQL の式と、%s に入れる値を返す

    1語ぶんの式：CASE WHEN 商品名が一致 THEN 3 WHEN ブランドが一致 THEN 2 WHEN 説明文が一致 THEN 1 ELSE 0 END
    「一致」は、その語の言い換えのどれか1つでも含めば一致。
    CASE は最初に当てはまった点だけを返すので、商品名と説明文の両方にあっても3点（足し算しない）
    """
    parts, params = [], []
    for word in words:
        patterns = [f"%{term}%" for term in expand_word(word)]

        def any_like(column: str) -> str:
            return "(" + " OR ".join([f"{column} LIKE %s"] * len(patterns)) + ")"

        parts.append(
            f"(CASE WHEN {any_like('p.product_name')} THEN {NAME_POINT}"
            f" WHEN {any_like('p.brand')} THEN {BRAND_POINT}"
            f" WHEN {any_like('p.description')} THEN {DESCRIPTION_POINT}"
            " ELSE 0 END)"
        )
        params += patterns * 3  # 商品名・ブランド・説明文の順に、同じパターンを渡す
    return (" + ".join(parts) if parts else "0"), params
