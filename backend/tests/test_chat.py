# tests/test_chat.py — FR-03 POST /api/chat のテスト（第1段階：固定の応答）
#
# DB にはつながず、main.fetch_all を差し替えて商品の有無を再現する。
# 実行（backend フォルダで）：python -m pytest tests

import pytest
from fastapi.testclient import TestClient

import main

PRODUCTS = {"G0001": {"product_id": "G0001", "product_name": "花の店 ブーケ お花とお菓子のセット（焼き菓子）"}}


@pytest.fixture
def client(monkeypatch):
    def fake_fetch_all(query, params=()):
        product = PRODUCTS.get(params[0]) if params else None
        return [product] if product else []

    monkeypatch.setattr(main, "fetch_all", fake_fetch_all)
    return TestClient(main.app)


def post_chat(client, **overrides):
    body = {"product_id": "G0001", "question": "職場で配りやすい？", "scene_tag": "送別"}
    body.update(overrides)
    return client.post("/api/chat", json=body)


def test_returns_stub_answer_for_farewell_scene(client):
    res = post_chat(client)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["answer"]
    assert data["sources"] == [{"id": "G0001:description", "label": "商品説明"}]


@pytest.mark.parametrize("scene_tag", ["", "取引先へのお礼", "farewell"])
def test_rejects_other_scenes(client, scene_tag):
    res = post_chat(client, scene_tag=scene_tag)
    assert res.status_code == 400


def test_returns_404_for_unknown_product(client):
    res = post_chat(client, product_id="G9999")
    assert res.status_code == 404


@pytest.mark.parametrize("question", ["", "   ", "あ" * 201])
def test_rejects_empty_or_too_long_question(client, question):
    res = post_chat(client, question=question)
    assert res.status_code == 422


def test_accepts_question_at_max_length(client):
    res = post_chat(client, question="あ" * 200)
    assert res.status_code == 200
