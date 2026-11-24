# 08 自作の評価データで確かめる（未知のデータでの確認）

提供データに無い言語・書き方の投稿を自分で作り、**改善の判断に一度も使わないまま**、最後に 1 回だけ測るガイドです（任意 O-1・説明資料 ⑤）。改善が提供データに過学習していないか、本番で来うる投稿にも効くかを示します。

## ゴール

- 架空の投稿 40〜60 件の自作データ（`evals/promptfoo/custom_data/pjt04_custom.csv`）と、その説明（`custom_data/README.md`）がある
- データを**評価の結果を見る前に**固定し、固定したことをタグで示せる
- 最後に、ベースラインと最終版の両方で 1 回ずつ測り、比較の表がある

## 前提

- [01 環境の準備](./01_setup.md) が終わっている
- **作るのは早いほどよい**。理想は 03（ベースライン）の結果を見る前。遅くとも 05 で改善の案を試し始める前に作り終える
- 測るのは、05 の手順 9（test・全件の 1 回だけの測定）と同じ時期

## なぜ早く作るのか

改善の結果を見てから作ると、無意識に「今のプロンプトで正解できる投稿」や「直した誤りに似た投稿」を作ってしまいます。そうなると、自作データの結果は良く見えても、未知のデータでの確認になりません。**作る → 固定する → 最後まで見ない**の順を守ります。

---

## 手順

### 1. ブランチを切る

```bash
git switch develop && git pull
git switch -c data/custom-dataset
mkdir -p evals/promptfoo/custom_data
```

### 2. 何を作るかを決める（設計表）

件数の目安は 48 件（警告すべき 20・警告しない 28）。本番の投稿は違反が少ないので、警告しない投稿をやや多めにする。

| 軸 | 入れるもの | 件数の目安 | 狙い |
|---|---|---|---|
| A. 提供データに無い言語 | 韓国語（ko）・スペイン語（es）・ベトナム語（vi）・ポルトガル語（pt） | 4 言語 × 6 件 = 24 | 言語の広がり（課題 2） |
| B. 書き方の揺れ（日本語・英語） | 絵文字だらけ・URL 短縮（`bit.ly` 等）・全角と半角の混在・単語に空白や記号を挟む（`L I N E`）・ローマ字の日本語 | 12 | 表記の揺れへの強さ |
| C. 言語の混在 | 1 投稿の中で 2 言語（例：日本語＋英語、スペイン語＋英語） | 6 | 言語の混在（提供データは 6 件だけ） |
| D. 紛らわしい安全な投稿 | 講座の公式の案内・ルールの注意・受け取った勧誘の報告・自分のプロフィールの共有だけ | 6（A〜C と重ねてもよい） | 誤検知 |

違反の種類は、`article_guide.txt` の対応表から 5〜6 種類を選ぶ（外部グループへの勧誘 `11-xiii`・出会い目的 `11-xiv`・宿題の解答の要求 `course-8-iv`・金銭 `11-x`・個人情報を探る `11-ix`・教材の外部公開 `edu-3-ii` など）。**1 つの種類に偏らない**ようにする。

A の 4 言語は、6 件を「同じ 3 シナリオ × 違反 1・安全 1」のように揃えると、言語の間で比べやすい（提供データと同じ考え方）。

### 3. 投稿を書く

1 件ずつ、次の順に書く。

1. **シナリオを日本語で 1 行**にする（例：「同じ講座の受講生に、自分の作った外部のチャットグループへの参加を呼びかける。リンクあり」）
2. 正解を決める：`judge_decision.txt` の「警告する (warn)」「警告しない (safe)」のどれに当たるか。warn なら `article_guide.txt` で条文を 1 つ選ぶ
3. その言語で本文を書く。自分で書けない言語は、翻訳の道具（DeepL・Google 翻訳など）で訳し、**別の道具で日本語に訳し戻して**意味が変わっていないかを確かめる
4. `note` に、正解の根拠（どの方針のどの項目に当たるか）を書く

守ること：

| 守ること | 理由 |
|---|---|
| 架空の内容だけ。実在の人名・電話番号・メールアドレス・招待リンクを使わない。URL は `https://example.com/...` や `EXAMPLE` を含む形にする | 個人情報・公開リポジトリ |
| 評価データ（354 件）・CI 用のデータ（ガイド 07）の投稿を写さない・言い換えない | 未知のデータにならない |
| 講座の AWS（Bedrock）で投稿を作らない・訳さない | 判定に使うモデルで作ると、判定しやすい投稿に偏る |
| 正解に迷う投稿は、迷った理由を `note` に書き、`degree` を `境界事例` にする。どうしても決められない投稿は入れない | 正解の誤りで結果がぶれる |

列（`eval_posts.csv` と同じ）：

| 列 | 書き方 |
|---|---|
| `id` | `C01-ko` のように（シナリオの番号＋言語） |
| `scenario_id` | `C01` |
| `language` | `ko`・`es`・`vi`・`pt`・`ja`・`en`。言語の混在は `mixed` |
| `text` | 本文。改行・`,`・`"` を含むときは欄全体を `"` で囲み、中の `"` は `""` |
| `is_violation` | `true` / `false` |
| `violating_article` | 警告すべきときだけ条文 ID。警告しないときは空 |
| `category` | 例：`外部グループへの勧誘（リンクあり）`・`講座の質問`。提供データの区分に合わせる |
| `length` | `短文(-50)`・`中文(51-150)`・`長文(151-)` |
| `intent` | `善意`・`悪意`・`中立` |
| `degree` | `明確な違反`・`境界事例`・`紛らわしい（安全）`・`安全` |
| `noise` | `なし`・`絵文字`・`URL短縮`・`全半角混在`・`記号挟み`・`ローマ字`・`言語混在` |
| `note` | 正解の根拠。作り方（例：`DeepL で訳し、Google で訳し戻して確認`） |

書き出しの例（2 件。**このまま使わず、自分で作る**）：

```csv
id,scenario_id,language,text,is_violation,violating_article,category,length,intent,degree,noise,note
C01-ko,C01,ko,우리 스터디 카카오톡 오픈채팅방 만들었어요! 같이 공부해요 https://open.kakao.com/o/EXAMPLE,true,11-xiii,外部グループへの勧誘（リンクあり）,短文(-50),善意,明確な違反,なし,外部のチャットグループへの誘い（judge_decision の warn の 1 項目め）。自分で日本語から訳し、Google で訳し戻して確認
C02-ko,C02,ko,3주차 과제 제출 마감이 다음 주 월요일 맞나요?,false,,講座の質問,短文(-50),善意,安全,なし,宿題の提出についての質問（safe の 3 項目め）
```

### 4. 形を確かめる

```bash
cd evals/promptfoo
source ../../.venv/bin/activate
python load_dataset.py custom_data/pjt04_custom.csv --output /tmp/custom_check.yaml && rm /tmp/custom_check.yaml
python check_prompt_leak.py --extra custom_data/pjt04_custom.csv
python - <<'PY'
import csv, collections
rows = list(csv.DictReader(open("custom_data/pjt04_custom.csv", encoding="utf-8")))
print(len(rows), "件")
for col in ("language", "is_violation", "violating_article", "degree", "noise"):
    print(col, dict(collections.Counter(r[col] for r in rows)))
PY
```

✅ 確認：

- `load_dataset.py` が止まらない（列・条文 ID・正解と条文の組み合わせが正しい）
- 写し込みの確認が「一致なし」（自作データの言い回しを、プロンプトに書いていない）
- 言語・正解・条文・難しさ・書き方の内訳が、手順 2 の設計表に近い

**この時点で、自作データを判定にかけない**（スモークも含めて）。形の確認だけにする。

### 5. データの説明を書く

新しいファイル `evals/promptfoo/custom_data/README.md`（データカード）：

```markdown
# 自作の評価データ（PJT04 最終課題）

## 目的
提供データ（6 言語・354 件）に無い言語・書き方で、改善が過学習していないかを確かめる。改善の判断には使わず、最後に 1 回だけ測る。

## 中身
- 件数: N 件（警告すべき X・警告しない Y）
- 言語: ko a 件・es b 件・vi c 件・pt d 件・ja e 件・en f 件・mixed g 件
- 違反の種類: （条文 ID ごとの件数）
- 書き方: （noise ごとの件数）

## 作り方
- すべて架空の投稿。実在の人物・連絡先・リンクは含まない
- シナリオを日本語で決め、正解を judge_decision.txt・article_guide.txt の方針で付けてから本文を書いた
- 自分で書けない言語は翻訳の道具で訳し、別の道具で訳し戻して確認した（各行の note）
- 講座の Bedrock は作成に使っていない

## 固定
- 固定したコミット: タグ `custom-data-frozen`（YYYY-MM-DD）
- SHA-256: （手順 6 の値）
- 固定した後は内容を変えない。誤りに気づいたら、変えずに報告に書く

## 限界
- 1 人で作った・1 人で正解を付けた（正解の付け方の偏り）
- 機械翻訳を使った言語は、自然な書き方でない可能性がある
- 件数が少ないので、1 件で率が大きく動く（1 言語 6 件なら 1 件 ≒ 0.17）
```

### 6. 固定する（結果を見る前に）

```bash
cd ../..
shasum -a 256 evals/promptfoo/custom_data/pjt04_custom.csv
# 出た値を custom_data/README.md の「SHA-256」に書く
git add evals/promptfoo/custom_data/
git commit -m "data: 自作の評価データ N 件を追加して固定（O-1。結果を見る前に固定）"
git tag custom-data-frozen
git push -u origin data/custom-dataset --tags
gh pr create --base develop --title "自作の評価データを追加（O-1）" --body "評価の結果を見る前に固定。タグ custom-data-frozen"
```

✅ 確認：`git show custom-data-frozen --stat` に CSV と README が出る。タグの日付が、05 の改善の試行より前。

> ここから最後の測定まで、**このデータで判定しない**。うっかり `testcases.yaml` にしないように、`run_trial.sh` は `datasets/eval_posts.csv` しか読まない作りにしてある。

### 7. 最後に 1 回だけ測る（05 の手順 9 と同じ時期）

ベースライン（03 で測った時の判定）と、最終版（採用した改善を入れた develop）の両方で測る。

#### 7-1. ベースラインの版を別の作業ツリーに出す

`experiments/README.md` の EXP-000 の行の「プロンプトのコミット」を使う。

```bash
cd <リポジトリのルート>
git tag eval-baseline <EXP-000 のコミット>
git worktree add ../pjt04-baseline eval-baseline
cp evals/promptfoo/custom_data/pjt04_custom.csv ../pjt04-baseline/evals/promptfoo/ 
ln -s "$PWD/evals/node_modules" ../pjt04-baseline/evals/node_modules   # npm install を省く
```

#### 7-2. ベースラインで測る

```bash
REPO=$PWD
cd ../pjt04-baseline/evals/promptfoo
export PROMPTFOO_PYTHON=$REPO/.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1
$PROMPTFOO_PYTHON load_dataset.py pjt04_custom.csv
npx promptfoo eval --filter-providers bedrock-lite --repeat 3 --no-cache -j 4 -o $REPO/evals/promptfoo/output/custom_baseline.json
cd $REPO
```

> ハーネスは自分の置かれた場所から `lambda/` を読むので、作業ツリーのベースラインの判定（コードとプロンプト）で測られる。Python の環境は本体の `.venv` を使ってよい（依存は同じ）。

#### 7-3. 最終版で測る

```bash
cd evals/promptfoo
source ../../.venv/bin/activate
env | grep '^BEDROCK_'                     # 何も出ないこと（既定値＝採用した設定で測る）
python load_dataset.py custom_data/pjt04_custom.csv
npx promptfoo eval --filter-providers bedrock-lite --repeat 3 --no-cache -j 4 -o output/custom_final.json
python load_dataset.py datasets/eval_posts.csv
```

#### 7-4. 集計して記録する

`summarize.py` の言語別の表に、自作データの言語（ko・es など）が別の行で出るよう、`summarize.py` の先頭を変える（`mixed` にまとめられないように）：

```python
MAIN_LANGS = ["ja", "en", "zh", "ar", "fr", "sw"]
# 自作データ (ガイド 08) で足した言語。言語別の表に別の行として出す (mixed にまとめない)
EXTRA_LANGS = ["ko", "es", "vi", "pt", "id", "hi"]
LANGS = MAIN_LANGS + EXTRA_LANGS
```

```python
def lang_group(lang: str) -> str:
    return lang if lang in LANGS else "mixed"
```

`main()` の言語別の表のループも変える：

```python
    for key in LANGS + ["mixed", "全体"]:
```

（言語間の一致の集計は、6 言語の対訳を前提にしているので `MAIN_LANGS` のままにする。`compare_runs.py` は出てきた言語を自動で並べるので変えなくてよい）

```bash
D=../../docs/purchase_order/experiments
python summarize.py output/custom_baseline.json --csv $D/custom_baseline.csv > $D/custom_baseline.md
python summarize.py output/custom_final.json    --csv $D/custom_final.csv    > $D/custom_final.md
python compare_runs.py output/custom_baseline.json output/custom_final.json | tee $D/custom_compare.md
grep -c "example.com\|EXAMPLE" $D/custom_*.md     # 0 であること（集計に本文が出ていない）
```

> 自作データの本文は commit 済みなので、本文が集計に混ざっても問題はないが、他の記録と同じ形（件数・率・ID）にそろえる。

✅ 確認：ベースライン → 最終版で、取りこぼしが増えていない。増えた・言語によって悪くなった場合も、**データを直したり除いたりせず**、そのまま報告する（それ自体が「過学習していないかを確かめた」結果）。

#### 7-5. 後片付け

```bash
git worktree remove ../pjt04-baseline
git worktree prune
```

💾 コミット：`docs(experiments): 自作データでのベースラインと最終版の比較を記録（O-1）`（`summarize.py` の変更は別のコミット：`feat(evals): 自作データの言語を言語別の表に出す`）

### 8. 誤りを読む（ここで初めて中身を見る）

最終の測定が済んだので、自作データの誤りを読んでよい（ここでの気づきで判定を直すことはしない）。

- 提供データでは直ったのに、自作データで残った誤りは何か（例：韓国語の勧誘だけ取りこぼす → 言語の広がりの限界）
- 書き方の揺れ（`noise`）ごとの取りこぼし
- 説明資料 ⑤ に「未知のデータでの結果」と「分かった限界・次の改善の候補」として書く

---

## ⚠️ つまずきやすい点

- 作っている途中で「この投稿は今の判定で当たるか」を試したくなる。試さない（試した時点で未知のデータでなくなる）
- 自作データの言語は少数なので、言語別の率は大きくぶれる。率よりも「何件中何件」で書く
- `git worktree add` の先に `node_modules` が無いと `npx promptfoo` が別の版を取りに行く。7-1 のリンクを忘れない
- ベースラインの作業ツリーの `harness.py` が `bedrock` 方式に対応していない（03 より前のコミットを指定した）と、全件が失敗する。EXP-000 のコミットを使う

## 完了の条件

- [ ] `custom_data/pjt04_custom.csv`（40〜60 件）と `custom_data/README.md` を commit し、タグ `custom-data-frozen` を付けた
- [ ] タグの日付が改善の試行より前
- [ ] ベースラインと最終版で 1 回ずつ測り、比較の表がある
- [ ] 説明資料 ⑤ に結果と限界を書いた
