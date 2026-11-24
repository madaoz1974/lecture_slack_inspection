# 01 環境の準備

## ゴール

- 手元で `pytest tests/` が全件通り、promptfoo の評価を動かせる状態になっている
- 提供データセットが評価用の形式（`testcases.yaml`）に変換されている（commit はしない）
- リポジトリに `LICENSE`（Apache License 2.0）と、README 冒頭の「最終課題での取り組み」節の骨組みがある
- 発注者への質問を送ってある

## 前提

- macOS（Homebrew・Node.js 18 以上が入っている）。このガイドを書いた時点では `python3.12`・`aws`・`uv` は未導入
- 作業ブランチの起点は `develop`

---

## 手順

### 1. 作業ブランチを切る

```bash
git switch develop
git pull
git switch -c chore/setup-final-assignment
```

発注元のリポジトリも参照できるようにしておく（取り込みはしない。差分を見るときだけ使う）。

```bash
git remote add upstream https://github.com/matsuolab/lecture_slack_inspection.git
git fetch upstream
```

✅ 確認：`git remote -v` に `origin`（自分のフォーク）と `upstream`（matsuolab）の両方が出る。

### 2. Python 3.12 の仮想環境を作る

本番の Lambda は Python 3.12 なので、手元も 3.12 にそろえる（CI は 3.13 で動くので、3.12 と 3.13 の両方で通る書き方をする）。

```bash
brew install python@3.12
python3.12 --version          # Python 3.12.x

python3.12 -m venv .venv      # リポジトリ直下。.gitignore 済み
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt pyyaml
```

- `requirements.txt`（直下）には、Lambda の依存（boto3・openai・requests・slack_sdk）とテスト用（pytest・pytest-mock・jsonschema）がそろっている
- `pyyaml` は評価のデータ変換（`load_dataset.py`）で使う

✅ 確認：`python -c "import boto3, openai, pytest, yaml; print('ok')"` が `ok` を出す。

### 3. 既存のテストを流し、件数を記録する

```bash
pytest tests/ -q
```

✅ 確認：最後の行が `N passed`（失敗 0）。**この N を控えておく**（説明資料の「既存の自動テストが通る」の根拠になる。以降の変更でテストを足したら N が増える）。

失敗した場合：

- `ModuleNotFoundError` → 手順 2 の venv が有効になっていない（`source .venv/bin/activate`）
- `infra/tests` が失敗する → `pytest tests/` ではなく `pytest` だけで流している。`infra/tests` は古く、CI でも流していない（`tests/` を指定する）

### 4. promptfoo を入れる

```bash
cd evals
npm install                       # package.json で promptfoo 0.120.19 に固定
npx promptfoo --version           # 0.120.19
cd ..
```

✅ 確認：バージョンが表示される。`evals/node_modules/` は `.gitignore` 済み（`git status` に出ない）。

### 5. 評価データを置いて変換する

提供データは `docs/purchase_order/pjt04_eval_dataset/` にある（`.gitignore` 済み）。評価用のフォルダ `evals/promptfoo/datasets/`（これも `.gitignore` 済み）へコピーして変換する。

```bash
mkdir -p evals/promptfoo/datasets
cp docs/purchase_order/pjt04_eval_dataset/eval_posts.csv \
   docs/purchase_order/pjt04_eval_dataset/violating_article_legend.csv \
   evals/promptfoo/datasets/

cd evals/promptfoo
python load_dataset.py datasets/eval_posts.csv
cd ../..
```

✅ 確認：

- 変換の出力が `354 件（警告すべき 153・警告しない 201）を .../datasets/testcases.yaml に書いた`
- `git status --short` に `evals/promptfoo/datasets/` が**出ない**（出たら `.gitignore` を確認し、絶対に add しない）

⚠️ `PJT04_追加データ.json` の 16 件は、354 件の中に**同じ本文ですでに含まれている**（シナリオ ID が `JH〜` のもの）。別に変換する必要はなく、ホールドアウトにもならない。未知の投稿での確認は、ガイド 08 の自作データで行う。

### 6. LICENSE（Apache License 2.0）を置く

最終課題の提出条件（リポジトリを公開し、Apache License 2.0 を付ける）。

```bash
curl -sSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
head -3 LICENSE
```

✅ 確認：先頭が `Apache License` / `Version 2.0, January 2004` になっている。

💾 コミット：`chore: Apache License 2.0 の LICENSE を追加`

### 7. README 冒頭に「最終課題での取り組み」節の骨組みを置く（M-8）

`README.md` の**1 行目より前**に、次を貼る（元の記載は消さない）。中身はガイド 10 で埋める。最初に置くのは、書く場所を決めておき、作業の途中でも追記できるようにするため。

```markdown
# 最終課題での取り組み（AIエンジニアリング実践講座 2026 PJT04）

> 作成中。各項目は作業の進み具合に合わせて更新します。

## ① 取り組んだ課題と内容

（記入）

## ② 判定方式の変更点

（記入）

## ③ 評価の実行手順

（記入。evals/README.md の手順への差分を書く）

## ④ 追加した評価用データ

（記入）

## ⑤ 特に評価してほしいポイント

（記入）

## 利用した外部のライブラリ・サービスとライセンス

| 名前 | 用途 | ライセンス・利用規約 |
|---|---|---|
| Amazon Bedrock（Amazon Nova） | 違反の判定 | AWS のサービス条件 |
| promptfoo | 評価 | MIT |
| python-pptx | 説明資料の PPTX 生成 | MIT |
| Marp CLI | 説明資料の PDF 生成 | MIT |

---

```

✅ 確認：GitHub のプレビュー（または VS Code の Markdown プレビュー）で、README の最初にこの節が出る。

💾 コミット：`docs: README の冒頭に「最終課題での取り組み」節の骨組みを追加`

### 8. 発注者への質問を送る

1. まず回答一覧（スプレッドシート）を開き、同じ質問がすでに答えられていないかを確認する
2. 答えられていないものだけを質問フォームから送る。計画書 11 章の 3 点：
   - Nova Micro / Lite 以外のモデル（例：Nova Pro、多言語の埋め込みモデル）を比較のために使ってよいか
   - GitHub Actions から講座の AWS 環境の Bedrock を呼んでよいか（評価 CI 用。認証情報を GitHub の Secrets に置く形になる）
   - 提供データ・追加データを公開リポジトリにコミットしてよいか
3. 送った日と回答を、計画書の「改訂履歴」に 1 行ずつ書く

### 9. push と PR

```bash
git push -u origin chore/setup-final-assignment
gh pr create --base develop --title "chore: 最終課題の準備（LICENSE・README の節）" --body "ガイド 01 の作業"
```

✅ 確認：PR で `pytest` の CI が緑になる。マージしたら `develop` に戻る（`git switch develop && git pull`）。

---

## ⚠️ つまずきやすい点

- `CLAUDE.md` と `evals/README.md` の説明には、実装と食い違う部分がある（`CLAUDE.md` は単一の LLM 判定の説明、`evals/README.md` はデータが 258 件のまま）。**コードを正**として読む。文書の修正はガイド 10 でまとめて行う
- venv を有効にし忘れると、システムの Python（3.9 など）で動いて依存が見つからない。プロンプトの先頭に `(.venv)` が出ているかを見る
- `npm install` は `evals/` で行う（直下ではない）

## 完了の条件

- [ ] `pytest tests/ -q` が全件成功し、件数を控えた（N = ）
- [ ] `npx promptfoo --version` が動く
- [ ] `evals/promptfoo/datasets/testcases.yaml` が 354 件で作れた（commit していない）
- [ ] `LICENSE` と README の節の骨組みが `develop` に入った
- [ ] 質問を送り、計画書の改訂履歴に記録した
