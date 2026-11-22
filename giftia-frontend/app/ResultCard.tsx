// app/ResultCard.tsx — 結果カード（部品）。2週目の変更は import の1行だけ（Gift 型の置き場所が lib/api.ts に変わった）
// FR-03：「この商品について聞く」ボタンと「選択中」の表示を追加
"use client"; // ① 状態管理や onClick を使うために必ず追加する

import { useState } from "react"; // ② useState をインポート
import type { Gift } from "@/lib/api";
import styles from "./page.module.css";

export default function ResultCard({
  gift,
  rank,
  onAsk,
  selected = false,
}: {
  gift: Gift;
  rank: number;
  onAsk?: () => void; // 渡されたときだけ「この商品について聞く」を出す（送別シーンのとき）
  selected?: boolean; // チャットで質問中の商品か
}) {
  // ③ レビューが開いているかどうかを覚える箱（初期値は閉じた状態 = false）
  const [isOpen, setIsOpen] = useState(false);

  // レビュー件数が存在し、かつ 1件以上あるかどうかを判定する変数
  const hasReviews = gift.reviewCount > 0 && gift.reviews && gift.reviews.length > 0;

  return (
    <div className={selected ? `card ${styles.cardSelected}` : "card"}>
      <p className="meta">
        {rank}位・{gift.category}・{gift.brand}
      </p>
      <h3 className="name">
        {gift.name}
        {selected && <span className={styles.selectedBadge}>選択中</span>}
      </h3>
      {/* <p className="price">{gift.price.toLocaleString()}円</p> */}
      <p
        className="price"
        style={gift.overBudget ? { color: "#d9480f" } : undefined}
      >
        {gift.price.toLocaleString()}円
      </p>

      {/* ④ 件数の部分をクリックできるようにし、カーソルをポインターに変える */}
      <p
        className="meta"
        onClick={() => setIsOpen(!isOpen)}
        style={{ cursor: "pointer", color: "#0066cc" }}
      >
        評価{gift.rating}（{gift.reviewCount}件）
      </p>

      {onAsk && (
        <button
          type="button"
          id={`ask-${gift.id}`}
          className={styles.askButton}
          onClick={onAsk}
          aria-pressed={selected}
        >
          {selected ? "質問中" : "この商品について聞く"}
        </button>
      )}
      {/* 【ポイント】hasReviews が true のとき（コメントがあるとき）だけ、下のトグルボタンを表示する */}
      {hasReviews && (
        <>
          <div
            onClick={() => setIsOpen(!isOpen)}
            style={{ cursor: "pointer", color: "#0066cc", fontSize: "0.9rem", marginTop: "6px" }}
          >
            レビューコメントを見る {isOpen ? "▲閉じる" : "▼開く"}
          </div>
      
      {/* 展開されているときだけコメント一覧を表示 */}
          {isOpen && (
            <ul
              className="review-list"
              style={{
                marginTop: "6px",
                paddingLeft: "1.2rem",
                fontSize: "0.9rem",
              }}
            >
              {gift.reviews!.map((review, index) => (
                <li key={index} style={{ marginBottom: "4px" }}>
                  {review.authorLabel && (
                    <span style={{ fontWeight: 600, marginRight: "6px" }}>
                      ({review.authorLabel})
                    </span>
                  )}
                  <span>{review.comment}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}