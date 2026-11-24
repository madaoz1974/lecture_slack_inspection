# 10 報告と提出

ここまでの結果を、説明資料（PDF）と README にまとめ、提出前の確認をして Omnicampus に提出するガイドです（必須 M-8・説明資料 ①〜⑥）。**提出は 2/28 までに済ませる**（締め切りは 3/1 12:00。前日は予備）。

## ゴール

- 説明資料（`slides/report.md` → `dist/report.pdf`）が ①〜⑥ のすべてを満たす
- README の冒頭の「最終課題での取り組み」が埋まっている
- 文書の食い違い（`CLAUDE.md`・`evals/README.md`）を直した
- 秘密・講座の配布物・評価データの本文が、リポジトリにも PDF にも入っていない
- `main` に入り、提出したコミットが分かる形で Omnicampus に提出した

## 前提

- 05（test・全件の結果）・06・08（自作データの結果）が終わっている。07・09 は行った範囲で
- 目安：1 週間（2/15〜2/26）

---

## 手順

### 1. ブランチを切り、材料の一覧を作る

```bash
git switch develop && git pull
git switch -c docs/final-report
ls docs/purchase_order/experiments/
```

説明資料の章と、材料（`experiments/` のファイル）の対応：

| 章（`report.md` の見出し） | 必須項目 | 材料 |
|---|---|---|
| 要約 | — | 全体から最後に書く |
| 1. 取り組んだ課題と重点・目標水準とその根拠 | ① | 計画書の 1・4・5 章、`baseline_vs_openai.md` |
| 2. ベースラインの分析 | ② | `env.md`・`baseline_lite_*.md`・`baseline_vs_openai.md`・`analysis_baseline.md` |
| 3. 改善した判定方式・なぜ効いたのか | ③ | `experiments/README.md` の表（採用・不採用）・ガイド 05 の手順 8 の表 |
| 4. ベースラインと改善版の比較（全体・言語別） | ④ | `final_vs_baseline_test.md`・`final_vs_baseline_all.md`・`metrics_*.json` |
| 5. 過学習を避けるための工夫 | ⑤ | `splits/pjt04_split.json`・`custom_compare.md`・`check_prompt_leak.py`・`custom_data/README.md` |
| 6. 動作の確認 | 動作の証跡 | CI の画面・`injection_compare.md`・`e2e/`・`system_review.md` |
| 7. 残った課題と本番への取り込み案 | ⑥ | `system_review.md`・`custom_compare.md`（自作データで残った誤り）・不採用の案 |
| 付録：実行環境・再現の手順 | — | `env.md`・README の ③ |

### 2. 説明資料を埋める

`docs/purchase_order/slides/report.md` の `（記入）` と `—` を、上の材料で埋める。各スライドの `<!-- ... -->`（発表者ノート）に、そのスライドで書くことの指示がある。

書くときの決まり：

- **数値は必ず材料のファイルから写す**。どのファイルの値かをノート（`<!-- 出典: experiments/final_vs_baseline_test.md -->`）に残す
- 言語別の比較は、件数と率の両方を書く（1 言語の警告すべき投稿は test で約 10 件。率だけだと差が大きく見える）
- 目標に届かなかった項目は、届かなかったと書き、理由と次の手を書く（発注者は「何が原因でどこを改善すべきか」を重視）
- **新しく足した指標**（例：判定の失敗を取りこぼしに数えた再現率・3 回の一致率・言語差）には、足した理由を 1 行で書く（チェックリストの項目）
- 投稿の本文を載せない。例を示すときは、自分の言葉で要約するか、自作データ・CI 用のデータの投稿を使う

スクリーンショット（`slides/assets/` に置く）：

| 画像 | 撮り方 | 注意 |
|---|---|---|
| 評価の実行の画面 | ターミナルで `./run_trial.sh` の最後の表、または `summarize.py` の出力 | `npx promptfoo view` の画面は提供データの本文が写るので使わない（使うなら自作データの結果だけ） |
| CI の画面 | GitHub の PR の Checks・`eval` の Summary | — |
| Slack の通知 | ガイド 09 の `e2e/` | 検証用のワークスペースだけが写っていること |
| 判定できなかったときの通知 | 同上（C-5 の 6） | — |

画像は `![w:900](assets/xxx.png)` の形で貼る（`slides/README.md`）。

### 3. 説明資料をビルドして確かめる

```bash
cd docs/purchase_order/slides
./build.sh
open dist/report.pdf
```

✅ 確認（1 枚ずつ見る）：

- [ ] はみ出しの警告が出ていない（出たら原稿を減らす。PDF は縮めない）
- [ ] すべての `（記入）`・`—` が埋まっている：`grep -n "（記入）\|| — |" report.md` が何も出さない（意図して空欄のものは除く）
- [ ] 表の数値が、材料のファイルと一致している（全体の行を 3 つ選んで照らし合わせる）
- [ ] 日本語の文字化け・欠けが無い
- [ ] ①〜⑥ の見出しが目次と一致している

PDF の中の文字に、秘密が入っていないかを確かめる：

```bash
.venv/bin/python -m pip install -q pymupdf
.venv/bin/python - <<'PY'
import re, fitz
text = "".join(page.get_text() for page in fitz.open("dist/report.pdf"))
pats = {"OpenAI のキー": r"sk-[A-Za-z0-9_-]{20,}", "Slack のトークン": r"xox[abpr]-[A-Za-z0-9-]{10,}",
        "AWS のキー": r"AKIA[0-9A-Z]{16}", "Notion のキー": r"(secret_|ntn_)[A-Za-z0-9]{20,}",
        "AWS のアカウント ID": r"(?<!\d)\d{12}(?!\d)"}
for name, p in pats.items():
    found = re.findall(p, text)
    print(("❌ " if found else "✅ ") + name + (f": {found[:3]}" if found else ""))
PY
```

✅ 確認：すべて ✅。12 桁の数字は、アカウント ID でなければ（例：タイムスタンプ）問題ない。

PPTX（`dist/report.pptx`）は編集用。PowerPoint で開いて手で直した場合は、**直した内容を `report.md` にも反映**して PDF を作り直す（正本は `report.md`）。

💾 コミット：`docs: 説明資料を埋める（①〜⑥）`（`report.md` と `assets/`。`dist/` は commit しない）

### 4. README の「最終課題での取り組み」を埋める

ガイド 01 で置いた骨組みの各節に書く。説明資料の要約を、リポジトリを読む人向けに短くしたものにする。

| 節 | 書くこと | 長さの目安 |
|---|---|---|
| ① 取り組んだ課題と内容 | 課題 1（Bedrock への移行）・2（多言語）を中心に、何をしたかを 3〜5 行。結果の数値を 1 行（例：取りこぼし X → Y、言語差 A → B） | 10 行 |
| ② 判定方式の変更点 | `bedrock` 方式（Converse API・tool use で JSON を強制）・採用した改善（`BEDROCK_DEFAULTS` の値）・判定できなかったときの扱い・注入対策。設定の環境変数の表（`DETECTION_MODE`・`BEDROCK_MODEL_ID`・`BEDROCK_REGION`・`BEDROCK_*`・`DETECTION_TIMEOUT_SEC`・`NOTIFY_UNDETERMINED`） | 20 行 |
| ③ 評価の実行手順 | データの置き方 → `load_dataset.py` → `run_trial.sh` → `compare_runs.py` の最短の手順。dev/test の分け方。CI（`eval.yml`）の使い方 | 20 行 |
| ④ 追加した評価用データ | 自作データ（件数・言語・作り方・固定のタグ）、注入のデータ、CI 用のデータ。`custom_data/README.md` へのリンク | 10 行 |
| ⑤ 特に評価してほしいポイント | 3 つまで。例：「誤りを言語のせい・方針のせい・揺れに分けてから案を選んだこと」「判定できなかった投稿を黙って通さない作り」「自作データを結果を見る前に固定したこと」 | 5 行 |
| 利用した外部のライブラリ・サービスとライセンス | 下の表を確かめて足す | — |

外部のライブラリ・サービスの表に入っているかを確かめるもの（ガイド 01 の表に足す）：

| 名前 | 使いどころ | ライセンス・規約 |
|---|---|---|
| Amazon Bedrock（Amazon Nova） | 判定 | AWS のサービス規約・Bedrock のモデルの利用条件 |
| boto3 / botocore | Bedrock の呼び出し | Apache License 2.0 |
| promptfoo | 評価 | MIT |
| python-pptx | 説明資料の PPTX | MIT |
| Marp CLI | 説明資料の PDF | MIT |
| PyMuPDF（確認にだけ使った場合は不要） | PDF の確認 | AGPL-3.0（配布しないので確認の用途のみ） |
| GitHub Actions（`aws-actions/configure-aws-credentials` など） | CI | 各アクションのライセンス（MIT など） |

運用の注意も 1 節足す：障害で「判定できなかった」の通知が多すぎるときに `NOTIFY_UNDETERMINED=false` にする方法と、元に戻す方法（ガイド 06）。

💾 コミット：`docs: README の「最終課題での取り組み」を埋める（M-8）`

### 5. 文書の食い違いを直す

| ファイル | 直すこと |
|---|---|
| `CLAUDE.md` | 「Violation detection」の節：単一の LLM 判定（`judge_violation.txt`・`violation_score`）の説明を、今の方式（`decisions`・`luna`・`bedrock` の 3 つ、2 段の判定、`judge_decision.txt`・`article_guide.txt`・`judge_article.txt`）に合わせる。`bedrock` 方式の環境変数と、`BEDROCK_DEFAULTS` を足す。「Secrets / config」に `DETECTION_MODE`・`BEDROCK_MODEL_ID`・`BEDROCK_REGION` を足す |
| `evals/README.md` | データの件数（258 → 354）、`bedrock-micro`・`bedrock-lite` のプロバイダー、`run_trial.sh`・`compare_runs.py`・`error_matrix.py`・`check_prompt_leak.py`・`ci_offline_check.py` の説明、dev/test の分け方、CI の節（ガイド 07 の手順 8） |
| `README.md`（元の部分） | `app_inspect` の説明に `bedrock` 方式を 1 行。「プロンプト更新」の節に、変えたら dev で測る（`run_trial.sh`）ことを 1 行 |
| `docs/requirements/issues.md` | 対応した項目（ISS-01・02・07・29 など）に「対応：PR #xx」（ガイド 06 で済んでいれば確認だけ） |
| `docs/purchase_order/final_assignment_plan.md` | 改訂履歴に「最終版」の行。目標の表に、実際の結果の列を足す（任意） |

```bash
grep -rn "258" evals/README.md
grep -n "violation_score\|judge_violation" CLAUDE.md
```

✅ 確認：上の 2 つが、意図したもの以外を出さない。

💾 コミット：`docs: CLAUDE.md・evals/README.md を今の実装に合わせる`

### 6. 提出前の確認

#### 6-1. テストと CI

```bash
cd <リポジトリのルート>
source .venv/bin/activate
pytest tests/ -q
```

✅ 確認：失敗 0 件。PR を出して、`pytest`・`eval`（offline）・`cdk-synth` が緑。

#### 6-2. 入れてはいけないものが入っていないか

```bash
# (1) 講座の配布物・評価データ・秘密のファイルの名前
git ls-files | grep -i -E "\.pdf$|発注|課題|eval_posts|PJT04_|\.env$|violation_data|team_logs|\.mp4$" || echo "OK: 該当するファイル名なし"

# (2) 秘密の値の形（全履歴）
git log -p --all | grep -n -E "sk-[A-Za-z0-9_-]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|(secret_|ntn_)[A-Za-z0-9]{20,}" | head || true
```

✅ 確認：(1) は `OK`（`docs/purchase_order/` の計画書などの名前に当たったら、中身が講座の配布物でないことを確かめる）。(2) は何も出ない。

(3) 評価データの本文が、commit したファイルに混ざっていないか（集計・記録・プロンプト・スライドの原稿を含めて全部）。`evals/promptfoo/datasets/eval_posts.csv` が手元にある状態で、リポジトリのルートで：

```bash
python - <<'PY'
import csv, re, subprocess, sys
from pathlib import Path

N = 20
data = Path("evals/promptfoo/datasets/eval_posts.csv")
norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
grams = set()
for r in csv.DictReader(open(data, encoding="utf-8")):
    t = norm(r["text"])
    grams.update(t[i:i + N] for i in range(max(0, len(t) - N + 1)))

hits = 0
for f in subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines():
    p = Path(f)
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pptx", ".ico", ".woff", ".woff2", ".zip"}:
        continue
    try:
        t = norm(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        continue
    for i in range(max(0, len(t) - N + 1)):
        if t[i:i + N] in grams:
            hits += 1
            print(f"{f}: 「{t[i:i + N]}」")
            break
print("評価データの本文の一致なし" if not hits else f"{hits} ファイルに一致")
sys.exit(1 if hits else 0)
PY
```

✅ 確認：`評価データの本文の一致なし`。一致したら、そのファイルから本文を消す（すでに push していれば、履歴に残ることを踏まえて扱いを講座に相談する）。

> 万一、秘密の値を push してしまったら：**まずキーを無効にする**（AWS・Slack・Notion の管理画面）。履歴から消すのはその後（`git filter-repo` など）。消しても、無効にしない限り安全ではない。

#### 6-3. リポジトリの設定

- [ ] リポジトリが Public（`gh repo view --json visibility -q .visibility` が `PUBLIC`）
- [ ] `LICENSE` がルートにあり、Apache License 2.0
- [ ] README の冒頭に「最終課題での取り組み」が出る（GitHub の画面で見る）
- [ ] デモ動画を出すなら、README からリンクしている

#### 6-4. 説明資料の最終の確認（計画書 10 章のチェックリスト）

- [ ] ① 取り組んだ課題と、重点を置いた点とその理由
- [ ] ② ベースラインの取りこぼし・誤検知の分析（言語別）
- [ ] ③ 改善した判定方式の設計と、その考え方
- [ ] ④ ベースラインと改善版の比較（言語別を含む）、目標水準とその根拠
- [ ] ⑤ 過学習を避けるための工夫（データの分け方、追加したデータなど）
- [ ] ⑥ 残った課題と、本番に取り込むための改善案
- [ ] 説明資料だけで動作が確認できる（評価の実行画面・Slack の通知のスクリーンショット等）
- [ ] 新たに追加した指標には、追加した理由を書いた

### 7. main に入れて、提出する版を固定する

```bash
git push -u origin docs/final-report
gh pr create --base develop --title "説明資料と README の最終版" --body "ガイド 10"
# develop に入れた後
gh pr create --base main --head develop --title "最終課題の提出版" --body "PJT04 最終課題の提出版"
# main に入れた後
git switch main && git pull
git tag -a final-submission -m "PJT04 最終課題 提出版"
git push origin final-submission
git rev-parse --short final-submission
```

出たコミットのハッシュを、説明資料の付録（再現の手順）に書き、PDF を作り直す（ハッシュを書いた変更は main に入れなくてよい。PDF だけ作り直す）。

### 8. Omnicampus に提出する

- [ ] 提出物：説明資料の PDF（`dist/report.pdf`）、リポジトリの URL（`https://github.com/madaoz1974/lecture_slack_inspection`）、提出版のタグ（`final-submission`）
- [ ] ファイル名・形式・容量は講座の指示に従う
- [ ] 提出した後、提出画面のスクリーンショットを手元に残す（commit しない）
- [ ] 提出後に main を変えない（変えたら、提出版はタグで示す）

### 9. 後片付け

- 講座の AWS：ガイド 09 の B-5（`cdk destroy`・SSM の削除）、ガイド 07 の CI 用のロール・キー（`pjt04-eval-ci`）の削除。講座の指示に従う
- 手元の評価データ（`evals/promptfoo/datasets/`・`output/`）：講座の指示に従って消す
- 検証用の Slack・Notion：不要なら消す

---

## ⚠️ つまずきやすい点

- 説明資料の数値を手で書き写すと、どこかで食い違う。ノートに出典を書き、最後に 3 か所を照らし合わせる
- `report.md` を直さずに PPTX だけを直すと、PDF に反映されない
- 締め切りの直前は Omnicampus が混む・ビルドの道具が動かないことがある。**2/28 までに一度提出**し、直すなら再提出する（講座が再提出を認めているかを先に確かめる）

## 完了の条件

- [ ] 説明資料の PDF が ①〜⑥ を満たし、確認のチェックがすべて済んだ
- [ ] README・`CLAUDE.md`・`evals/README.md` が今の実装と一致する
- [ ] 秘密・配布物・評価データの本文が入っていないことを、3 つの方法で確かめた
- [ ] `final-submission` のタグを付け、Omnicampus に提出した
