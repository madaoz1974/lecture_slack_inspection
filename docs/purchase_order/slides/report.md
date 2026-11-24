---
marp: true
theme: default
size: 16:9
paginate: true
title: 'Slack監視App 違反検知の精度向上と多言語対応（PJT04 説明資料）'
footer: 'PJT04 Slack監視App｜AIエンジニアリング実践講座 2026 最終課題'
style: |
  /* 色と文字の大きさは tools/md2pptx.py の定数と揃える（編集可能な PPTX も同じ見た目にするため） */
  :root {
    --navy: #1F3A5F; --accent: #C2410C; --ink: #1F2937; --muted: #6B7280;
    --light: #F1F5F9; --code-bg: #F3F4F6; --link: #1D4ED8;
  }
  section {
    display: block;
    padding: 32px 64px 70px;
    background: #fff;
    color: var(--ink);
    font-family: 'Hiragino Sans', 'Yu Gothic', 'YuGothic', 'Noto Sans JP', sans-serif;
    font-size: 24px;
    line-height: 1.4;
  }
  section h1, section h2, section h3 { color: var(--navy); font-weight: 700; margin: 0; padding: 0; border: none; }
  section h2 { font-size: 36px; line-height: 1.25; padding-bottom: 10px; border-bottom: 3px solid var(--navy); margin-bottom: 20px; }
  section h3 { font-size: 26px; line-height: 1.3; margin: 12px 0 4px; }
  section p { margin: 0 0 12px; }
  section ul, section ol { margin: 0 0 12px; padding-left: 1.2em; }
  section li { margin: 0 0 4px; }
  section li li { font-size: 0.92em; }
  section li::marker { color: var(--navy); }
  section strong { color: var(--accent); }
  section a { color: var(--link); }
  section :not(pre) > code { font-family: Consolas, Menlo, monospace; font-size: 0.92em; color: var(--navy); background: none; padding: 0; }
  section pre { margin: 0 0 12px; padding: 12px 16px; background: var(--code-bg); border-radius: 0; }
  section pre code { font-family: Consolas, Menlo, monospace; font-size: 17px; line-height: 1.35; color: var(--ink); }
  section table { display: table; width: 100%; border-collapse: collapse; font-size: 19px; line-height: 1.3; margin: 0 0 12px; }
  section th, section td { padding: 6px 10px; border: 1px solid #fff; }
  section th { background: var(--navy); color: #fff; }
  section tbody tr:nth-child(odd) { background: var(--light); }
  section tbody tr:nth-child(even) { background: #fff; }
  section blockquote { margin: 0 0 12px; padding: 12px 18px; background: var(--light); border-left: 6px solid var(--navy); color: var(--ink); font-size: 22px; }
  section blockquote::before, section blockquote::after { content: none; }
  section blockquote p { margin: 0; }
  section img { display: block; margin: 0 auto 12px; }
  .columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; }
  section footer { left: 64px; right: auto; bottom: 22px; font-size: 14px; color: var(--muted); }
  section::after { right: 64px; bottom: 22px; font-size: 14px; color: var(--muted); }

  /* 表紙 */
  section.title { display: flex; flex-direction: column; justify-content: center; padding: 0 96px; background: var(--navy); }
  section.title h1 { color: #fff; font-size: 52px; line-height: 1.25; margin-bottom: 20px; }
  section.title h1::before { content: ''; display: block; width: 120px; height: 8px; margin-bottom: 24px; background: var(--accent); }
  section.title h2 { color: #CBD5E1; font-size: 28px; font-weight: 400; border: none; margin: 0 0 48px; }
  section.title p { color: #CBD5E1; font-size: 20px; line-height: 1.5; margin: 0; }
  section.title a { color: #CBD5E1; text-decoration: none; }
  section.title footer, section.title::after { color: #CBD5E1; }

  /* 章の扉 */
  section.section { display: flex; flex-direction: column; justify-content: center; background: var(--light); }
  section.section h2 { font-size: 44px; line-height: 1.3; border: none; border-left: 10px solid var(--accent); padding: 0 0 0 24px; margin: 0 0 24px; }
  section.section p { padding-left: 34px; color: var(--muted); }
---

<!-- _class: title -->
<!-- _paginate: false -->

# Slack監視App 違反検知の精度向上と多言語対応

## AIエンジニアリング実践講座 2026 最終課題 PJT04 説明資料

氏名：（記入）

リポジトリ：https://github.com/madaoz1974/lecture_slack_inspection

提出日：2027年2月（記入）

<!--
記入ガイド：表紙。氏名・提出日を入れる。リポジトリの URL は提出するものと同じにする。
-->

---

## 目次

1. 取り組んだ課題と、重点を置いた点とその理由
2. ベースラインの取りこぼし・誤検知の分析（言語別）
3. 改善した判定方式の設計と、その考え方
4. ベースラインと改善版の比較、目標水準とその根拠
5. 過学習を避けるための工夫
6. 動作の確認
7. 残った課題と、本番に取り込むための改善案

<!--
発注書 7 章の説明資料の必須項目 ①〜⑥ を、この順に 1〜5・7 で扱う。6 は「説明資料だけで動作を確認できる」ための章。
-->

---

## 要約

> **見逃しを増やさずに**誤検知を（記入）件減らし、言語間の再現率の差を（記入）→（記入）に縮めた。費用は 1 投稿あたり $（記入）。

| 指標（全 354 件・3 回の平均） | Bedrock 版ベースライン | 改善版 | 目標 |
|---|--:|--:|--:|
| 取りこぼし（件） | — | — | ベースライン以下 |
| 誤検知（件） | — | — | 30% 以上削減 |
| 再現率 / 適合率 | — / — | — / — | 0.941 / 0.750 以上 |
| 言語間の再現率の差 | — | — | 0.10 以内 |
| 1 投稿あたりの費用 | — | — | $0.000475 以下 |

<!--
記入ガイド：結論を最初に示す。数値は 4 章の表から転記する。率と件数は必ず併記する。
-->

---

<!-- _class: section -->

## 1. 取り組んだ課題と重点

発注書の課題 1・2（必須）と、重点を置いた理由

---

## 取り組んだ課題

<div class="columns">
<div>

### 必須

- 課題 1：判定の精度（**特に誤検知**）
- 課題 2：**言語による精度の差**

### 併せて取り組んだもの

- 課題 3：判定にかかる費用
- 課題 5：レート制限・一時的なエラー（記入）

</div>
<div>

### 重点を置いた点とその理由

- 運営が最も重視するのは**見逃さないこと**。誤検知は目で除けるが、見逃しには気づけない
- そこで「再現率を守る」を**制約**、「誤検知を減らす」を**目的**とした
- 6 言語の対訳データなので、言語だけが違う条件で差を比べられる

</div>
</div>

<!--
記入ガイド：説明資料の必須項目 ①。取り組まなかった課題（4 など）があれば、取り組まなかった理由も一言添える。
-->

---

## 目標水準とその根拠

| 観点 | 指標 | 目標 | 根拠 |
|---|---|---|---|
| 取りこぼし（最優先） | 再現率・件数 | ベースライン以下の件数 | 運営は見逃しに気づけない（発注書 4・8 章） |
| 誤検知 | 適合率・件数 | 件数を 30% 以上削減 | 通知の約 4 割が対応不要。確認の手間を減らす |
| 言語間の差 | 言語別の再現率の差 | 0.10 以内 | 対訳なので内容は同じ。1 件で約 0.04 動く |
| 安定性 | 3 回判定の一致率 | 95% 以上 | 同じ投稿に違う判定が出ないこと |
| 費用・時間 | 1 投稿の費用・p95 | $0.000475 以下・3 秒以内 | OpenAI 版の参考値・Lambda と Slack の制約 |

<!--
記入ガイド：説明資料の必須項目 ④ の「目標水準とその根拠」。ベースライン計測後に数値を確定し、変えた場合は理由を書く。
-->

---

<!-- _class: section -->

## 2. ベースラインの分析

OpenAI 版から Bedrock 版へ差し替えて、どこが変わったか

---

## Bedrock 版ベースラインの作り方

- 現在の判定方式（新方式）の**経路 B**（通常の呼び出しで「警告すべきか」と候補の条文を出す方式）を Amazon Bedrock へ移植
- モデル：Amazon Nova（記入：Micro / Lite）、リージョン：（記入）
- 評価：`evals/promptfoo` で、提供データセット 354 件 × 3 回。本番の判定のコードをそのまま呼ぶ
- 指標：取りこぼし・誤検知・再現率・適合率・判定時間（中央値・p95）・1 投稿あたりの費用

```text
投稿 → 段1: warn / safe と候補の条文（Nova） → warn のときだけ 段2: 条文を 1 つ選ぶ
```

<!--
記入ガイド：M-3。モデル ID・温度・プロンプトのコミットを付録に書く。
-->

---

## ベースラインの結果（言語別）

| 言語 | 件数 | 取りこぼし | 誤検知 | 再現率 | 適合率 | 時間 p95 |
|---|--:|--:|--:|--:|--:|--:|
| 日本語（ja） | 58 | — | — | — | — | — |
| 英語（en） | 58 | — | — | — | — | — |
| 中国語（zh） | 58 | — | — | — | — | — |
| アラビア語（ar） | 58 | — | — | — | — | — |
| フランス語（fr） | 58 | — | — | — | — | — |
| スワヒリ語（sw） | 58 | — | — | — | — | — |
| 言語混在 | 6 | — | — | — | — | — |
| **全体** | 354 | — | — | — | — | — |

<!--
記入ガイド：summarize.py の出力（summary.csv）から転記する。3 回の平均と範囲を示す。
-->

---

## OpenAI 版との比較（モデルの差し替えによる差）

| 方式 | 取りこぼし | 誤検知 | 再現率 | 適合率 | 1 投稿あたりの費用 |
|---|--:|--:|--:|--:|--:|
| 新方式（OpenAI 版・運営の計測） | 9 件 | 48 件 | 0.941 | 0.750 | $0.000475 |
| Bedrock 版ベースライン（Nova 記入） | — | — | — | — | — |
| 差 | — | — | — | — | — |

- 差が大きかった言語：（記入）
- 差が大きかった投稿の種類：（記入）

<!--
記入ガイド：M-3 の「モデルを替えたことによる差」。OpenAI 版の値は発注書 4 章の参考値。
-->

---

## 取りこぼし・誤検知の分析

<div class="columns">
<div>

### 取りこぼし（見逃し）

| 種類 | ja | en | 他 |
|---|--:|--:|--:|
| 外部グループへの勧誘 | — | — | — |
| 出会い目的 | — | — | — |
| （記入） | — | — | — |

- 原因の仮説：（記入）

</div>
<div>

### 誤検知

| 種類 | ja | en | 他 |
|---|--:|--:|--:|
| 公式の案内 | — | — | — |
| ルールの注意 | — | — | — |
| （記入） | — | — | — |

- 原因の仮説：（記入）

</div>
</div>

<!--
記入ガイド：説明資料の必須項目 ②。category・degree・language の列で集計し、代表例（架空の投稿）を 1〜2 件ずつ付録に載せる。
-->

---

<!-- _class: section -->

## 3. 改善した判定方式

設計と、その考え方

---

## 改善した判定方式の設計

```text
Slack の投稿
  └→ ViolationDetector（DETECTION_MODE=bedrock）
       ├ 段1: 警告すべきか ＋ 候補の条文（Converse API・tool use で JSON を固定）
       ├ 段2: warn のときだけ条文を 1 つ選ぶ
       ├ 再試行: adaptive ＋ タイムアウト（課題 5）
       └ 失敗時: 「判定できなかった」として運営に通知（見逃しにしない）
```

- 変更点 1：（記入）
- 変更点 2：（記入）
- 変更点 3：（記入）

<!--
記入ガイド：説明資料の必須項目 ③、README の ②「判定方式の変更点」と揃える。図に差し替えてもよい（assets/ に置く）。
-->

---

## なぜ効いたのか（考察）

| 変更 | 狙った誤り | 結果 | 考察 |
|---|---|---|---|
| （記入） | 英語などの取りこぼし | — | （記入） |
| （記入） | 紛らわしい投稿の誤検知 | — | （記入） |
| （記入） | 判定の失敗・揺れ | — | （記入） |

- 試したが採用しなかった案：（記入。効かなかった理由も書く）

<!--
記入ガイド：M-5「なぜ、その変更が精度を改善したか考察」。案ごとの結果は docs/purchase_order/experiments/ の記録から引く。
-->

---

<!-- _class: section -->

## 4. ベースラインと改善版の比較

同じデータ・同じ指標で

---

## 比較（全体）

| 指標 | Bedrock 版ベースライン | 改善版 | 差 | 目標 | 達成 |
|---|--:|--:|--:|--:|:-:|
| 取りこぼし（件） | — | — | — | ベースライン以下 | — |
| 誤検知（件） | — | — | — | 30% 以上削減 | — |
| 再現率 | — | — | — | 0.941 以上 | — |
| 適合率 | — | — | — | 0.750 以上 | — |
| 3 回の一致率 | — | — | — | 95% 以上 | — |
| 判定時間 中央値 / p95 | — | — | — | p95 3 秒以内 | — |
| 1 投稿あたりの費用 | — | — | — | $0.000475 以下 | — |

<!--
記入ガイド：M-4。悪化した指標があれば、その理由と対策を次のスライドに書く。
-->

---

## 比較（言語別）

| 言語 | 再現率（前 → 後） | 適合率（前 → 後） | 取りこぼし（前 → 後） | 誤検知（前 → 後） |
|---|--:|--:|--:|--:|
| ja | — → — | — → — | — → — | — → — |
| en | — → — | — → — | — → — | — → — |
| zh | — → — | — → — | — → — | — → — |
| ar | — → — | — → — | — → — | — → — |
| fr | — → — | — → — | — → — | — → — |
| sw | — → — | — → — | — → — | — → — |
| 言語混在 | — → — | — → — | — → — | — → — |
| **最大 − 最小** | — → — | — → — | | |

<!--
記入ガイド：発注者が特に重視する「改善の効果が言語別に示されていること」。
-->

---

<!-- _class: section -->

## 5. 過学習を避けるための工夫

---

## データの分け方と追加したデータ

<div class="columns">
<div>

### シナリオ単位で分割

- 同じシナリオの対訳が両方に入ると答えが漏れるため、`scenario_id` 単位で分けた
- dev（改善の試行）：（記入）シナリオ
- test（最後に 1 回だけ）：（記入）シナリオ
- 種を固定し、ID の一覧だけをリポジトリに置いた

</div>
<div>

### 未知の投稿での確認

- 追加データ（16 件）：最後まで見ないホールドアウト
- 自作データ（O-1）：（記入）件。提供データに無い言語・種類
- 正解は運営の判断方針（`judge_decision.txt`）に従って付けた

</div>
</div>

| データ | 件数 | ベースライン 再現率 / 適合率 | 改善版 再現率 / 適合率 |
|---|--:|--:|--:|
| test | — | — / — | — / — |
| ホールドアウト・自作 | — | — / — | — / — |

<!--
記入ガイド：説明資料の必須項目 ⑤。自作データの作り方と正解の付け方を書く（O-1 の補足）。
-->

---

<!-- _class: section -->

## 6. 動作の確認

説明資料だけで動作を確認できるように

---

## 評価の実行と自動テスト

- 評価の実行画面（promptfoo）：（スクリーンショットを assets/ に置き、ここに貼る）
- 自動テスト：`pytest tests/` が全件成功（記入：件数）。判定の処理にテストを追加
- 評価の自動化（O-5）：GitHub Actions の実行結果（記入）

> 画像は `![w:900](assets/ファイル名.png)` の形で貼る。PDF と PPTX の両方に入る。

<!--
記入ガイド：発注者は環境を構築しての動作確認をしない。スクリーンショットで実際に動いたことを示す。
-->

---

## 判定できなかったときの扱い・本番での動作

- LLM の呼び出しが失敗したときは「判定できなかった」として運営に通知（O-4）
- 検証用の Slack・Notion での通知の画面（O-6）：（記入）
- AWS へのデプロイ（O-7）：（記入）

<!--
記入ガイド：任意要件に取り組んだ場合だけ残す。取り組まなかった項目は消す。
-->

---

<!-- _class: section -->

## 7. 残った課題と本番への取り込み案

---

## 残った課題と、本番に取り込むための改善案

| 残った課題 | 影響 | 改善案 |
|---|---|---|
| （記入） | — | （記入） |
| レート制限・同時投稿への耐性（課題 5・O-8） | 判定の遅れ・失敗 | 受付と判定の非同期化（SQS）、再試行と DLQ |
| 運営の実データでの確認 | 架空データとの差 | 本番では両方式を並べて記録し、通知の対応不要率で比べる |

### 本番に取り込む手順（案）

1. `DETECTION_MODE=bedrock` を検証用のワークスペースで有効にし、通知を比べる
2. 問題がなければ本番に切り替え、OpenAI 版を予備として残す

<!--
記入ガイド：説明資料の必須項目 ⑥。
-->

---

## 付録：実行環境・再現の手順

| 項目 | 内容 |
|---|---|
| リポジトリ | https://github.com/madaoz1974/lecture_slack_inspection |
| 評価の手順 | README「最終課題での取り組み」③ |
| モデル・設定 | （記入：モデル ID、温度、リージョン） |
| プロンプトの版 | （記入：コミット） |
| データ | 提供 354 件・追加 16 件・自作（記入）件 |
| 利用した外部サービス | Amazon Bedrock、promptfoo（MIT）ほか README に記載 |
