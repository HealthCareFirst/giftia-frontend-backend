// app/page.tsx — Giftia 検索画面（2週目・穴埋め版）
// 【穴7】【穴8】を、対応表と公式ドキュメントを頼りに自分で埋める。
// 答えは 配布コード/答え合わせ/frontend/page.tsx（自分で埋めてから見る）。
// 1週目との違い：①searchGifts が FastAPI を呼ぶ（async/await）②入力した条件を渡す ③つながらないときの表示
"use client"; // ← ブラウザで動く合図。useState や onClick を使う画面に必要

import { useState } from "react";
import ResultCard from "./ResultCard";
import ProductChat from "./ProductChat";
import styles from "./page.module.css";
import { searchGifts, type Gift } from "@/lib/api";

// FR-03：チャットを使えるシーン（backend/chat.py の FAREWELL_SCENE とそろえる）
const FAREWELL_SCENE = "送別";

const SCENES = [
  "誕生日",
  "送別",
  "お礼",
  "母の日",
  "父の日",
  "お歳暮",
  "お中元",
  "結婚祝い",
  "出産祝い",
] as const;
type Scene = (typeof SCENES)[number];

function isScene(v: string): v is Scene {
  return (SCENES as readonly string[]).includes(v);
}

export default function Home() {
  // ① 状態（変化するデータ）を覚える箱
  const [scene, setScene] = useState<Scene | "">("");
  const [mode, setMode] = useState<"standard" | "business">("standard"); // どのタブか
  const [keyword, setKeyword] = useState(""); // 入力した言葉
  const [category, setCategory] = useState(""); // 選んだカテゴリー
  const [indivWrap, setIndivWrap] =
    useState(false); /* 【穴7】初期値はチェックなし（真偽値） */ // 個包装だけ（取引先へのお礼）
  const [roomTemp, setRoomTemp] = useState(false); // 常温だけ（取引先へのお礼）追加
  const [priceBand, setPriceBand] = useState(""); // 価格帯（取引先へのお礼）
  const [results, setResults] = useState<Gift[] | null>(null); // 検索結果
  const [error, setError] = useState(""); // つながらないときの文言
  const [loading, setLoading] = useState(false); // ← 追加：検索中かどうか
  const [chatGift, setChatGift] = useState<Gift | null>(null); // チャットで質問中の商品（FR-03）
  // チャットを使えるのは「いまの検索」タブで、送別シーンが選ばれているときだけ
  const chatEnabled = mode === "standard" && scene === FAREWELL_SCENE;

  // チャットを閉じて、元のカードの「この商品について聞く」にフォーカスを戻す
  function closeChat() {
    const id = chatGift?.id;
    setChatGift(null);
    if (id) {
      requestAnimationFrame(() =>
        document.getElementById(`ask-${id}`)?.focus(),
      );
    }
  }

  // タブを切り替える（結果・チャット・エラー表示をリセット）
  function switchMode(next: "standard" | "business") {
    setMode(next);
    setResults(null);
    setChatGift(null);
    setError("");
  }
  // ② 検索ボタンの処理（API に聞くので、結果が返るまで待つ＝async/await）
  async function onSearch(e: React.FormEvent) {
    e.preventDefault(); // ページの再読み込みを止める
    if (loading) return; // 検索中なら何もしない（連打対策）
    setLoading(true);
    setError("");
    setChatGift(null); // 結果が入れ替わるので、開いているチャットは閉じる
    // いま開いているタブの条件だけを送る（もう一方のタブの入力は送らない）
    const condition =
      mode === "standard"
        ? {
            scene,
            keyword,
            category,
            indivWrap: false,
            roomTemp: false,
            priceBand: "",
          }
        : {
            scene: "",
            keyword: "",
            category: "",
            indivWrap,
            roomTemp,
            priceBand,
          };
    try {
      setResults(await searchGifts(condition));
    } catch (err) {
      setResults(null);
      setError(
        `APIにつながりません：${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setLoading(false); // 成功しても失敗しても、検索中を解除する
    }
  }

  // ③ 画面
  return (
    <main className="page">
      <header className="header">
        <h1>Giftia</h1>
      </header>

      {/* タブ：state(mode)＋条件で出し分ける */}
      <nav className="modes">
        <button
          className={mode === "standard" ? "on" : ""}
          onClick={() => switchMode("standard")}
        >
          いまの検索
        </button>
        <button
          className={mode === "business" ? "on" : ""}
          onClick={() => switchMode("business")}
        >
          取引先へのお礼
        </button>
      </nav>

      <form className="form" onSubmit={onSearch}>
        {mode === "standard" ? (
          <>
            <select
              aria-label="シーン"
              value={scene}
              onChange={(e) => {
                const v = e.target.value;
                setScene(isScene(v) ? v : "");
                // シーンが変わると結果の意味が変わるので、検索結果・エラー・チャットを消す（FR-01）
                setResults(null);
                setError("");
                setChatGift(null);
              }}
            >
              <option value="">シーンを選ぶ</option>
              {SCENES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>

            <input
              className="q"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="キーワード（例：送別 お菓子）"
            />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">すべてのカテゴリー</option>
              <option value="コスメ">コスメ</option>
              <option value="食品">食品</option>
              <option value="生活雑貨">生活雑貨</option>
            </select>
          </>
        ) : (
          <>
            <label className="chk">
              <input
                type="checkbox"
                checked={indivWrap}
                onChange={(e) => setIndivWrap(e.target.checked)}
              />{" "}
              個包装
            </label>
            <label className="chk">
              {" "}
              {/* 常温チェックボックス追加 */}
              <input
                type="checkbox"
                checked={roomTemp}
                onChange={(e) => setRoomTemp(e.target.checked)}
              />{" "}
              常温
            </label>
            <select
              value={priceBand}
              onChange={(e) => setPriceBand(e.target.value)}
            >
              <option value="">すべての価格帯</option>
              <option value="3000">3,000〜5,000円</option>
              <option value="5000">5,000〜10,000円</option>
            </select>
          </>
        )}
        <button type="submit" disabled={loading}>
          {" "}
          {/* ← こう置き換える */}
          {loading ? "検索中…" : "検索"}
        </button>
      </form>

      {error && <p className="summary">{error}</p>}

      {/* 結果：同じ ResultCard を map で並べる（使い回し） */}
      {results && (
        <section>
          {results.length === 0 ? (
            // 0件のときの文言（FR-01）
            <p className="summary">
              条件に合う商品が見つかりませんでした。キーワードやカテゴリーを変えてお試しください。
            </p>
          ) : (
            <>
              <p className="summary">上位 {results.length} 件</p>
              {/* チャットを開いたら、一覧を左・チャットを右に並べる（狭い画面ではチャットを全画面） */}
              <div
                className={
                  chatEnabled && chatGift ? styles.withChat : undefined
                }
              >
                <div className="grid">
                  {results.map((g, i) => (
                    <ResultCard
                      key={g.id}
                      gift={g}
                      rank={i + 1}
                      onAsk={chatEnabled ? () => setChatGift(g) : undefined}
                      selected={chatEnabled && chatGift?.id === g.id}
                    />
                  ))}
                </div>
                {chatEnabled && chatGift && (
                  <ProductChat
                    key={chatGift.id} // 商品が変わったら作り直す（質問欄・回答のリセット）
                    gift={chatGift}
                    sceneTag={scene}
                    onClose={closeChat}
                  />
                )}
              </div>
            </>
          )}
        </section>
      )}
    </main>
  );
}
