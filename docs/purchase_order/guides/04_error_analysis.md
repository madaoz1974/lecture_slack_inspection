# 04 誤りを分析する（ベースラインの取りこぼし・誤検知）

説明資料の必須項目 ②「ベースラインの取りこぼし・誤検知の分析（言語別）」と、発注者が特に重視する「何が原因でどこを改善すべきかが説明されていること」を作るガイドです。**ここで決めた原因と優先順位が、ガイド 05 で試す案の順番になります。**

## ゴール

- 取りこぼし・誤検知を、言語・シナリオ・投稿の種類・難しさ・揺れの観点で数え、原因の仮説を立てた
- 「どの誤りを、どの案で、どの順に減らすか」を表にした（`experiments/analysis_baseline.md`）
- 説明資料の 2 章（ベースラインの分析）の表が埋まった

## 前提

- [03 ベースラインを測る](./03_baseline_evaluation.md) が終わり、`evals/promptfoo/output/baseline_<主なモデル>.json` がある
- 以下、主なモデルを Lite とした例で書く（Micro にしたなら読み替える）

## 進め方の原則

- **dev の誤りだけを読む**。test の誤りの中身（投稿の本文・モデルの理由）は読まない。読むと、test に効く直し方を無意識に選んでしまう（過学習）。test は件数と率だけを見る
- 数える → 並べる → 仮説を立てる、の順。**1 件ずつ読む前に全体の形を見る**（目立つ 1 件に引っ張られないため）

---

## 手順

### 1. 分析用のスクリプトを置く

`summarize.py` は言語別の表と間違えた投稿の ID を出す。それに加えて、**同じシナリオの 6 言語を横に並べた表**があると「言語のせいの誤り」と「判断方針のせいの誤り」を見分けやすい。

新しいファイル `evals/promptfoo/error_matrix.py`：

```python
#!/usr/bin/env python3
"""promptfoo の結果から、シナリオ × 言語の正誤の表と、条文の取り違えの表を Markdown で出す（投稿の本文は出さない）。

    python error_matrix.py output/baseline_lite.json
    python error_matrix.py output/baseline_lite.json --split-file splits/pjt04_split.json --split dev

記号: ○ 正解 ／ 取 取りこぼし ／ 誤 誤検知 ／ ! 判定の失敗。
--repeat の結果なら、回によって判定が違ったマスに * を付ける（判定の揺れ）。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from summarize import MAIN_LANGS, load_runs

COLS = MAIN_LANGS + ["mixed"]


def mark(rec: dict) -> str:
    v, o = rec["vars"], rec["out"]
    if o.get("error"):
        return "!"
    exp, got = bool(v["expected_is_violation"]), bool(o.get("is_violation"))
    if exp == got:
        return "○"
    return "取" if exp else "誤"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--split-file", type=Path)
    ap.add_argument("--split", choices=["dev", "test"])
    ap.add_argument("--all", action="store_true", help="全言語で正解したシナリオも出す")
    a = ap.parse_args()

    runs = load_runs(a.results)
    if a.split_file and a.split:
        keep = set(json.loads(a.split_file.read_text(encoding="utf-8"))[a.split])
        runs = [{k: v for k, v in r.items() if v["vars"]["scenario_id"] in keep} for r in runs]
    first = runs[0]

    cells: dict[str, dict[str, str]] = defaultdict(dict)
    meta: dict[str, tuple] = {}
    for pid, rec in first.items():
        v = rec["vars"]
        sc = v["scenario_id"]
        lang = v["language"] if v["language"] in MAIN_LANGS else "mixed"
        marks = {mark(r[pid]) for r in runs if pid in r}
        cells[sc][lang] = mark(rec) + ("*" if len(marks) > 1 else "")
        meta[sc] = ("違反" if v["expected_is_violation"] else "違反なし", v.get("category", ""), v.get("degree", ""))

    def n_wrong(sc: str) -> int:
        return sum(1 for c in cells[sc].values() if not c.startswith("○"))

    print(f"## シナリオ × 言語の正誤（{len(runs)} 回分。マスは 1 回目、* は回によって違った）")
    print()
    print("| シナリオ | 正解 | 種類 | 難しさ | " + " | ".join(COLS) + " | 誤り |")
    print("|---|---|---|---|" + "---|" * len(COLS) + "--:|")
    for sc in sorted(cells, key=lambda s: (-n_wrong(s), s)):
        if not a.all and n_wrong(sc) == 0 and not any("*" in c for c in cells[sc].values()):
            continue
        exp, cat, deg = meta[sc]
        row = [cells[sc].get(c, "") for c in COLS]
        print(f"| {sc} | {exp} | {cat} | {deg} | " + " | ".join(row) + f" | {n_wrong(sc)} |")

    per_lang = Counter()
    for sc in cells:
        for lang, c in cells[sc].items():
            if not c.startswith("○"):
                per_lang[(lang, c[0])] += 1
    print()
    print("## 言語ごとの誤りの数（1 回目）")
    print()
    print("| 言語 | 取りこぼし | 誤検知 | 判定の失敗 |")
    print("|---|--:|--:|--:|")
    for lang in COLS:
        print(f"| {lang} | {per_lang[(lang, '取')]} | {per_lang[(lang, '誤')]} | {per_lang[(lang, '!')]} |")

    conf = Counter()
    for rec in first.values():
        v, o = rec["vars"], rec["out"]
        if not o.get("error") and v["expected_is_violation"] and o.get("is_violation") \
                and o.get("article_id") != v.get("expected_article"):
            conf[(v.get("expected_article") or "—", o.get("article_id") or "—")] += 1
    print()
    print("## 条文の取り違え（正しく警告した投稿のうち、条文が正解と違ったもの。1 回目）")
    print()
    print("| 正解の条文 | 付けた条文 | 件数 |")
    print("|---|---|--:|")
    for (exp, got), n in conf.most_common():
        print(f"| {exp} | {got} | {n} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```bash
cd evals/promptfoo
source ../../.venv/bin/activate
python error_matrix.py output/baseline_lite.json --split-file splits/pjt04_split.json --split dev
```

✅ 確認：表が出る。記号は ○ 正解・取 取りこぼし・誤 誤検知・! 判定の失敗、`*` は 3 回の中で判定が変わったマス。

💾 コミット：`feat(evals): シナリオ × 言語の正誤と条文の取り違えを出す error_matrix.py を追加`

### 2. 分析の記録ファイルを作る

`docs/purchase_order/experiments/analysis_baseline.md` を作り、手順 3〜8 の結果をこの順で書いていく。ひな形：

```markdown
# ベースラインの誤り分析（Nova Lite・dev・3 回）

## 1. 全体の形
## 2. 言語別
## 3. シナリオ × 言語（言語のせいか、方針のせいか）
## 4. 種類・難しさ別
## 5. 判定の揺れ・失敗
## 6. 条文の付け方
## 7. 費用・時間
## 8. 原因の仮説と、改善の優先順位
```

集計の出力（表）はそのまま貼ってよい（本文を含まない）。**投稿の本文は貼らない**。例を示したいときは、自分の言葉で要約する（「外部の勉強会への誘いを、学習の話題と取り違えた」など）。

### 3. 全体の形を見る（dev）

```bash
python summarize.py output/baseline_lite.json --split-file splits/pjt04_split.json --split dev
```

記録すること：

- 取りこぼし・誤検知・判定の失敗の件数（3 回それぞれと平均）
- 「再現率（失敗を取りこぼしに数えた場合）」との差 → 差が大きければ、**判定の失敗が見逃しの原因**になっている（ガイド 06 の O-4 の優先度が上がる）

### 4. 言語別に見る

`summarize.py` の言語別の表と、`error_matrix.py` の「言語ごとの誤りの数」から：

| 見ること | 読み取り方 |
|---|---|
| 再現率の最大 − 最小 | 課題 2 の大きさ。目標（0.10 以内）との距離 |
| 取りこぼしが多い言語 | その言語の理解・表現の問題の候補 |
| 誤検知が多い言語 | その言語で「強い言葉」「連絡先」などを過剰に違反と見ている候補 |
| 日本語と英語の差 | プロンプトが日本語で書かれていることの影響の候補 |

### 5. シナリオ × 言語の表から、誤りを 3 つに分ける

`error_matrix.py` の表の行（シナリオ）を、次の 3 つに分類して数える。**ここが分析の中心**。

| 分類 | 表での見え方 | 原因の仮説 | 効きそうな案（計画書 4.2） |
|---|---|---|---|
| A. 言語のせい | 一部の言語だけ ×（例：ja・en は ○、sw・ar は 取） | その言語の表現を理解できていない／方針の例が日本語・英語に偏っている | 1（多言語化）・5（翻訳して判定） |
| B. 方針のせい | ほぼ全言語で同じ ×（例：6 言語とも 誤） | 判断方針（`judge_decision.txt`）の線引きとずれている、または方針が曖昧 | 1（方針の書き直し）・4（2 段確認） |
| C. 揺れ | `*` が多い・回によって違う | 境界の投稿で判断が定まらない | 6（多数決）・温度・方針の明確化 |

それぞれのシナリオについて、**dev のものだけ**、投稿の本文（`datasets/eval_posts.csv`）とモデルの理由（`npx promptfoo view` で 1 件ずつ、または結果の JSON の `reason`）を読み、表に 1 行の要約を付ける。

```bash
# dev の 1 シナリオの 6 言語を並べて読む（例：W07）。画面で読むだけで、どこにも保存しない
python - <<'PY'
import csv
for r in csv.DictReader(open("datasets/eval_posts.csv", encoding="utf-8")):
    if r["scenario_id"] == "W07":
        print(r["id"], r["is_violation"], r["violating_article"], "|", r["text"][:120])
PY
```

### 6. 種類・難しさ・揺れ・失敗を見る

`summarize.py` の後半（区分ごとの内訳・判定の安定性・方法と応答コード）から：

- **種類（`category`）別**：取りこぼしが集中する種類（例：リンクの無い勧誘、出会い目的）と、誤検知が集中する種類（例：公式の案内、ルールの注意、受け取った勧誘の報告）
- **難しさ（`degree`）別**：`明確な違反` の取りこぼしは優先して直す（言い訳がきかない）。`境界事例`・`紛らわしい（安全）` は方針の明確化の対象
- **揺れ**：3 回とも同じ判定の割合（目標 95% 以上）。揺れたシナリオの分類（手順 5 の C）
- **失敗**：件数と原因（スロットリング・JSON 崩れ・時間切れ）。`npx promptfoo view` で失敗の理由を見る

### 7. 条文の付け方を見る（O-2・課題 4）

`error_matrix.py` の「条文の取り違え」と、`summarize.py` の「条文の一致」から：

- 正しく警告した投稿のうち、条文が正解と一致した割合（言語別にも）
- よく取り違える組（例：`11-xiii` を `11-xvi`（その他）にする）→ `article_guide.txt` の説明が足りない条文の候補
- **同じシナリオの 6 言語で同じ条文が付いたか**（一貫性）。`error_matrix.py` の表で、正しく警告した行の条文を見比べる（必要なら `summarize.py` の「間違えた投稿」の表の条文の列）

### 8. 費用・時間を見る

`summarize.py` の費用と時間の行から：

- 1 投稿あたりの費用（警告した投稿・しない投稿で分けて）と、本番の違反の割合（1%・5%）に直した値・月 3 万投稿の月額
- 判定時間の中央値・p95。目標（p95 3 秒）との距離
- 1 段目の入力トークンの大半は「規約 31 条文＋方針」。ここを減らす案（7：条文の絞り込み）が費用に効くかの見込み

### 9. 原因の仮説と、改善の優先順位を表にする

`analysis_baseline.md` の 8 章に、次の表を作る。**この表の上から順にガイド 05 で試す。**

| 優先 | 対象の誤り（件数） | 分類 | 原因の仮説 | 試す案 | 期待する効果 | 見逃しが増える恐れ |
|---|---|---|---|---|---|---|
| 1 | 例：sw・ar の勧誘の取りこぼし（dev で 6 件） | A | 方針の例が日・英だけ | 方針に多言語の典型表現を足す | 取りこぼし −4 | 小 |
| 2 | 例：ルールの注意・勧誘の報告の誤検知（12 件） | B | 「勧誘について話している」と「勧誘している」の区別が方針に無い | 方針に区別の基準を明記 | 誤検知 −6 | 中（言及と勧誘の境界） |
| 3 | … | | | | | |

優先順位の付け方：

1. **取りこぼしを減らす案を先に**（運営が最も重視する点）
2. 件数が多いもの
3. 安くて副作用の小さいもの（プロンプトの修正 → 構造の変更 → 呼び出しを増やす変更 の順）

### 10. 説明資料の 2 章を埋める

`docs/purchase_order/slides/report.md` の「ベースラインの結果（言語別）」「OpenAI 版との比較」「取りこぼし・誤検知の分析」に、全件の値と、手順 5・9 の要約を書く。

```bash
cd docs/purchase_order/slides && ./build.sh && cd -
```

✅ 確認：`dist/report.pdf` の 2 章に数値が入り、はみ出しの警告が出ない。

💾 コミット：`docs: ベースラインの誤り分析と改善の優先順位を記録し、説明資料の 2 章を埋める`

---

## ⚠️ つまずきやすい点

- 全件の結果で分析したくなるが、**中身を読むのは dev だけ**。test の誤りの ID が目に入るのは仕方ないが、本文と理由は開かない
- 「モデルが間違っている」のではなく「正解ラベルが方針と合っていない」と思える投稿があれば、勝手に正解を変えず、質問フォームで発注者に確認する（データセットの README にもそうある）。分析には「ラベルに疑問」として別に数える
- 1 シナリオの 6 言語は**独立した 6 件ではない**。「誤り 6 件」が 1 シナリオの全言語なら、原因は 1 つ

## 完了の条件

- [ ] `error_matrix.py` を commit した
- [ ] `experiments/analysis_baseline.md` の 1〜8 章を書いた
- [ ] 誤りを A（言語）・B（方針）・C（揺れ）に分けて数えた
- [ ] 改善の優先順位の表ができた
- [ ] 説明資料の 2 章が埋まった
