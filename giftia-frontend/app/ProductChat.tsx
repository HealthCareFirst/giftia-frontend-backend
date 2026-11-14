// app/ProductChat.tsx — FR-03 商品1件について質問するチャットパネル
// 親（page.tsx）は商品が変わるたびに key を変えて作り直す。作り直すと質問欄と回答がリセットされ、
// 前の商品への通信は止まる（遅れて届いた応答は表示しない）。
"use client";

import { useEffect, useRef, useState } from "react";
import { askProduct, type ChatAnswer, type Gift } from "@/lib/api";
import styles from "./page.module.css";

// 質問例。初版は商品1件について聞く質問だけにする
const EXAMPLE_QUESTIONS = [
  "職場で配りやすい？",
  "送別品として選ぶ根拠は？",
  "レビューを要約",
];

const MAX_QUESTION_LENGTH = 200; // backend/chat.py と同じ上限

type Phase = "idle" | "loading" | "done" | "error";

export default function ProductChat({
  gift,
  sceneTag,
  onClose,
}: {
  gift: Gift;
  sceneTag: string;
  onClose: () => void;
}) {
  const [question, setQuestion] = useState(""); // 入力中の質問
  const [asked, setAsked] = useState(""); // 送信した質問
  const [phase, setPhase] = useState<Phase>("idle");
  const [answer, setAnswer] = useState<ChatAnswer | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 開いたら質問欄にフォーカス。閉じる（＝この部品が消える）ときは通信を止める
  useEffect(() => {
    inputRef.current?.focus();
    return () => controllerRef.current?.abort();
  }, []);

  // Esc キーで閉じる
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || phase === "loading") return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setAsked(q);
    setQuestion("");
    setAnswer(null);
    setPhase("loading");
    try {
      const result = await askProduct(gift.id, q, sceneTag, controller.signal);
      setAnswer(result);
      setPhase("done");
    } catch (err) {
      if ((err as Error).name === "AbortError") return; // 閉じた・切り替えた：何も表示しない
      setPhase("error");
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(question);
  }

  return (
    <aside className={styles.chatPanel} aria-label="この商品についてのチャット">
      <div className={styles.chatHead}>
        <div className={styles.chatTitle}>
          <small>この商品について質問</small>
          <strong>{gift.name}</strong>
        </div>
        <button
          type="button"
          className={styles.chatClose}
          onClick={onClose}
          aria-label="チャットを閉じる"
        >
          ✕
        </button>
      </div>

      <div className={styles.chatBody} aria-live="polite">
        <p className={styles.bubble}>
          この商品について、気になることを1つ聞いてください。商品説明とレビューをもとにお答えします。
        </p>

        {asked && <p className={styles.bubbleUser}>{asked}</p>}

        {phase === "loading" && (
          <p className={styles.chatLoading}>回答を作成しています…</p>
        )}

        {phase === "done" && answer && (
          <div className={styles.bubble}>
            <p>{answer.answer}</p>
            {answer.sources.length > 0 && (
              <div className={styles.sources}>
                <b>出典</b>
                <ul>
                  {answer.sources.map((s) => (
                    <li key={s.id}>{s.label}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {phase === "error" && (
          <div className={styles.chatError} role="alert">
            <strong>回答を取得できませんでした</strong>
            <p>
              時間をおいてもう一度お試しください。商品の詳しい情報は、商品説明で確認できます。
            </p>
            <button type="button" onClick={() => send(asked)}>
              再試行
            </button>
          </div>
        )}
      </div>

      <form className={styles.chatFoot} onSubmit={onSubmit}>
        <div className={styles.chips}>
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => {
                setQuestion(q);
                inputRef.current?.focus();
              }}
              disabled={phase === "loading"}
            >
              {q}
            </button>
          ))}
        </div>
        <div className={styles.chatInput}>
          <textarea
            ref={inputRef}
            id="product-chat-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="この商品について質問する"
            maxLength={MAX_QUESTION_LENGTH}
            rows={2}
            disabled={phase === "loading"}
            aria-label="質問"
          />
          <button
            type="submit"
            disabled={phase === "loading" || !question.trim()}
          >
            送信
          </button>
        </div>
      </form>
    </aside>
  );
}
