// app/ResultCard.tsx — 結果カード（部品）。2週目の変更は import の1行だけ（Gift 型の置き場所が lib/api.ts に変わった）
// FR-03：「この商品について聞く」ボタンと「選択中」の表示を追加
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
      <p className="meta">
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
    </div>
  );
}
