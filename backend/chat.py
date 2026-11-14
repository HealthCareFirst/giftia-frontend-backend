# chat.py — FR-03 AI チャット（第1段階：固定の応答）
#
# 商品カードから「この商品について聞く」で呼ばれる処理をまとめる。
# 第1段階では AI には問い合わせず、決まった答えを返す（画面と API のつながりを確かめるため）。
# 第2段階で build_stub_answer() を、根拠の選択・AI への問い合わせ・出典の照合に置き換える。

from typing import Annotated

from pydantic import BaseModel, StringConstraints

# チャットを使えるシーン。FR-01（シーン選択）の画面から送られる値とそろえる
FAREWELL_SCENE = "送別"

# 質問の長さの上限（文字数）。長すぎる入力でモデルの費用や応答時間が膨らまないようにする
MAX_QUESTION_LENGTH = 200


class ChatRequest(BaseModel):
    """POST /api/chat の入力。前後の空白は取り除いてから長さを確かめる"""

    product_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH)
    ]
    scene_tag: str


def is_chat_available(scene_tag: str) -> bool:
    """送別シーンが選ばれているときだけチャットを使える（BR-01）"""
    return scene_tag == FAREWELL_SCENE


def build_stub_answer(product: dict) -> dict:
    """第1段階の固定の応答。出典はサーバーが組み立てる（画面から送られた値は使わない）"""
    return {
        "answer": (
            "（仮の回答）これは画面の動きを確かめるための固定の応答です。"
            "AI による回答は第2段階で接続します。"
        ),
        "sources": [
            {"id": f"{product['product_id']}:description", "label": "商品説明"},
        ],
        "status": "ok",
    }
