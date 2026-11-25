# 09 既存システムのレビュー・デプロイ・通し動作

精度以外の任意要件を 3 つ扱うガイドです。上から優先度の順に並べています。時間が足りなければ、A だけで完了としてかまいません。

| 部 | 要件 | 内容 | 成果物 | 目安 |
|---|---|---|---|---|
| A | O-8 | 既存システムのレビュー（Bedrock に移った後のレート制限・同時投稿・失敗時の扱い） | `docs/purchase_order/system_review.md` | 1 日 |
| B | O-7 | 講座の AWS へのデプロイ | デプロイの記録・`cdk deploy` の出力 | 0.5〜1 日 |
| C | O-6・O-9 | 検証用の Slack・Notion で通し動作（＋デモ動画） | スクリーンショット・動画 | 1〜1.5 日 |

## 前提

- [06 本体を堅くする](./06_production_hardening.md) が終わっている（C で「判定できなかった」の通知も見せるため）
- B・C は、講座の AWS にデプロイしてよいか（範囲・リージョン・費用・後片付け）を確認してから行う

---

## A. 既存システムのレビュー（O-8）

### A-1. 何を書くか

`docs/requirements/issues.md`（ISS-01〜34）は、OpenAI 版の時点の既知の課題の一覧です。これを土台に、**Bedrock に移った後の状態**で見直し、「どこが、どのくらいの規模で、何が起きるか」と「改善の案」を示します。新しく全部を調べ直す必要はありません。

### A-2. 材料を集める

(1) **Bedrock の上限**（講座の AWS のアカウント・リージョンの実際の値）：

```bash
export AWS_PROFILE=aie AWS_REGION=ap-northeast-1
aws service-quotas list-service-quotas --service-code bedrock \
  --query "Quotas[?contains(QuotaName, 'Nova')].[QuotaName,Value,Unit]" --output table
```

`Nova Lite`・`Nova Micro` の「1 分あたりのリクエスト数（RPM）」「1 分あたりのトークン数（TPM）」を、推論プロファイル（`apac.` で始まる、地域をまたぐもの）と、そうでないものに分けて書き写す。数値は `experiments/env.md` にも書く。

(2) **1 投稿あたりの呼び出し**（05 の採用した設定で）：

- 呼び出しの回数（警告しない投稿・警告する投稿それぞれ）
- 入力・出力のトークン数（`summarize.py` の費用の行、または結果の JSON の `calls`）
- 判定時間の中央値・p95

(3) **投稿の数**：発注書・`issues.md` の値（例：月 3 万投稿、8 月は 1 時間に約 11 件）。集中のときの倍率を仮定する（例：講義の直後に平均の 10 倍）。

### A-3. 上限に届く規模を計算する

| 項目 | 式 | 例 |
|---|---|---|
| 平均の投稿数（1 分） | 月の投稿数 ÷ (30 × 24 × 60) | 30,000 ÷ 43,200 ≒ 0.7 |
| 集中のときの投稿数（1 分） | 平均 × 倍率 | 0.7 × 10 = 7 |
| 必要な RPM | 集中のときの投稿数 × 1 投稿あたりの呼び出し回数 | 7 × 1.4 ≒ 10 |
| 必要な TPM | 集中のときの投稿数 × 1 投稿あたりのトークン数 | 7 × 5,000 = 35,000 |
| 余裕 | 上限 ÷ 必要な量 | — |
| 上限に届く投稿数（1 分） | 上限 ÷ 1 投稿あたりの量（RPM と TPM の小さい方） | — |

多数決（05 の案 6）や 2 段目のモデル（案 4）を採用していれば、呼び出し回数とトークン数が増えることを反映する。ワークスペースが増えたとき（導入先が 10 倍）も 1 行足す。

### A-4. 見直しの表を作る

`issues.md` の各項目を、次の 4 つに分ける。

| 分類 | 意味 | 例 |
|---|---|---|
| 対応済み | この課題で直した | ISS-01（判定できなかった投稿の通知。ガイド 06）・ISS-02（時間切れ）・ISS-29（注入。O-3）・ISS-07（`app_batch` の方式。ガイド 02） |
| Bedrock で変わった | 前提が変わった（良くも悪くも） | ISS-33（OpenAI のレート制限 → Bedrock の上限と再試行。adaptive の再試行が入った） |
| 残っている（重要） | 見逃し・止まる・漏れるにつながる | ISS-03（3 秒の応答）・ISS-32（送り直しを捨てる）・ISS-15（失敗に気づけない）・ISS-30（本文がログに残る。`app_inspect` の `info_text` も投稿の先頭 20 文字を出している） |
| 残っている（軽い） | 運用で回避できる・起きる規模が遠い | ISS-34（Notion の上限）など |

各項目について、「何が起きるか・どのくらいの規模で・どう直すか・手間」を 1〜3 行で書く。

### A-5. 改善の案（非同期化）を示す

同時投稿・上限・3 秒の応答（ISS-03・ISS-32）をまとめて解く案として、**受け付けと判定を分ける**作りを示す（実装はしない。図と説明だけ）。

```text
Slack ──→ API Gateway ──→ Lambda A（署名の確認・重複の確認・SQS に入れて、すぐ 200）
                                   │
                                   ▼
                                  SQS（可視性タイムアウト・最大受信回数）──→ DLQ（何度も失敗したもの）
                                   │
                                   ▼
                     判定の Lambda（同時実行数を予約して上限を守る）
                       ├─ Bedrock（adaptive の再試行）
                       ├─ 判定できなかった → 通知（ガイド 06）
                       └─ Notion・Slack に記録・通知
```

書くこと：

- 何が良くなるか：3 秒以内に必ず応答できる（Slack の送り直しが来ない）、集中を SQS がならす、同時実行数の予約で Bedrock の上限を超えない、失敗は DLQ に残り気づける
- 代わりに増えるもの：部品（SQS・DLQ・Lambda 1 つ）、費用（小さい）、二重の処理への備え（`Message_TS` で重複を確かめる。今の `check_duplicate_violation` を使う）
- `issues.md` の ISS-03 が挙げる既存の検討（案 A：非同期の自己呼び出し。`docs/requirements/decisions.md` の D2）との比べ
- 優先順位：A-4 の「残っている（重要）」のうち、どれから直すか

### A-6. 文書にまとめる

新しいファイル `docs/purchase_order/system_review.md`：

```markdown
# 既存システムのレビュー（Bedrock 移行後）

## 1. 範囲と方法
## 2. Bedrock の上限と、上限に届く規模（A-2・A-3 の表）
## 3. 既知の課題の見直し（A-4 の表）
## 4. 改善の案：受け付けと判定を分ける（A-5 の図と説明）
## 5. 優先順位と手間
```

💾 コミット：`docs: Bedrock 移行後の既存システムのレビューを追加（O-8）`

説明資料には、2 章の表（上限に届く規模）と 4 章の図を 1 枚ずつ載せる。

---

## B. 講座の AWS へのデプロイ（O-7）

### B-1. 確認すること（先に）

ガイド 01 の手順 8 の質問（4 番）で確認している。回答に従う。回答が無い・足りない点だけを、改めて質問する。

- [ ] 講座の AWS に CloudFormation のスタックを作ってよいか（API Gateway・Lambda・IAM ロール・IAM ユーザー・EventBridge・CloudWatch Logs）
- [ ] リージョン（`ap-northeast-1` でよいか）と、Bedrock のモデルの利用可否（ガイド 02 の手順 2）
- [ ] `cdk bootstrap` が済んでいるか、自分で行ってよいか
- [ ] 終わった後に消す必要があるか（`cdk destroy`）

> スタックには、GAS 用の IAM ユーザーとアクセスキー（`OAuthAllowlistGasCallerUser`）が含まれる。講座の AWS で IAM ユーザーを作れない場合は、デプロイが失敗する。その場合は、この部分を外してデプロイしてよいかを質問フォームで相談する。

### B-2. CDK の環境を用意する

```bash
cd infra
/opt/homebrew/bin/python3.12 -m venv .venv      # ガイド 01 で入れた Python 3.12
source .venv/bin/activate
pip install -r requirements.txt
npx aws-cdk@2 --version
export AWS_PROFILE=aie AWS_REGION=ap-northeast-1
aws sts get-caller-identity --query Account --output text
npx aws-cdk@2 synth > /dev/null && echo "synth OK"
```

✅ 確認：`synth OK`。ガイド 02 で足した `BedrockModelId`・`BedrockRegion` のパラメータと、`bedrock:InvokeModel` の権限がテンプレートに入っている：

```bash
npx aws-cdk@2 synth | grep -n "BedrockModelId\|bedrock:InvokeModel" | head
```

### B-3. 秘密の値を SSM に入れる

Lambda はキーを SSM Parameter Store から読む（`common/secret_manager.py`）。名前は CDK のパラメータの既定値。値は**コマンドの履歴に残さない**ため、`read -s` で入れる。

| SSM の名前 | 中身 | どこで手に入るか |
|---|---|---|
| `/slack/signing/secret` | Slack アプリの Signing Secret | C-2 で作る Slack アプリの Basic Information |
| `/slack/client/id` | Client ID | 同上 |
| `/slack/client/secret` | Client Secret | 同上 |
| `/slack/oauth/state` | OAuth の state の署名に使う乱数 | `openssl rand -hex 32` |
| `/slack/oauth/allowed_team_ids` | インストールを許すワークスペースの ID（カンマ区切り） | C-1 のワークスペース（`T` で始まる） |
| `/notion/api/key` | Notion のインテグレーションのキー | C-3 |
| `/openai/api/key` | 使わない（`bedrock` 方式）。読めないと空になるだけだが、念のため `unused` を入れる | — |

```bash
put() { read -s -p "$1 の値: " v; echo; aws ssm put-parameter --name "$1" --type SecureString --value "$v" --overwrite >/dev/null && echo "$1 OK"; unset v; }
put /slack/signing/secret
put /slack/client/id
put /slack/client/secret
put /slack/oauth/state
put /slack/oauth/allowed_team_ids
put /notion/api/key
put /openai/api/key
```

> C を行わず、デプロイだけを示す場合も、`NotionDbId` は必須のパラメータなので、C-3 の違反 DB だけは作っておく。

### B-4. デプロイする

```bash
npx aws-cdk@2 bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/ap-northeast-1   # 未実施なら
npx aws-cdk@2 diff \
  --parameters DetectionMode=bedrock \
  --parameters BedrockModelId=apac.amazon.nova-lite-v1:0 \
  --parameters NotionDbId=<違反 DB の ID>
npx aws-cdk@2 deploy --require-approval broadening \
  --parameters DetectionMode=bedrock \
  --parameters BedrockModelId=apac.amazon.nova-lite-v1:0 \
  --parameters BedrockRegion=ap-northeast-1 \
  --parameters NotionDbId=<違反 DB の ID> \
  --parameters NotionArticlesDbId=<条文マスタ DB の ID> \
  --parameters NotionTemplateDbId=<テンプレート DB の ID> \
  --parameters NotionHealthDbId=<ヘルス DB の ID> \
  --parameters NotionWsListDbId=<ワークスペース一覧 DB の ID> \
  --parameters MinSeverityToAlert=medium \
  2>&1 | tee /tmp/cdk_deploy.log
```

- 主なモデルを 05 で変えたなら `BedrockModelId` を合わせる
- `MinSeverityToAlert` は運用の値に合わせる（既定は `low`）
- Docker のイメージを作るので、Docker Desktop を起動しておく（初回は 10 分ほどかかる）

✅ 確認：最後に `Outputs:` が出て、`SlackEventsRequestUrl` などの URL が並ぶ。

```bash
grep -A20 "Outputs:" /tmp/cdk_deploy.log | sed -E 's/[0-9]{12}/<アカウント>/g' > ../docs/purchase_order/experiments/deploy_outputs.txt
rm /tmp/cdk_deploy.log
```

（アカウント ID は伏せる。URL の API の ID は公開されても呼び出しには署名が要るが、気になるなら伏せる）

💾 コミット：`docs(experiments): 講座の AWS へのデプロイの記録（O-7）`

### B-5. 後片付け（課題の終了後・講座の指示に従う）

```bash
cd infra && npx aws-cdk@2 destroy
for p in /slack/signing/secret /slack/client/id /slack/client/secret /slack/oauth/state /slack/oauth/allowed_team_ids /notion/api/key /openai/api/key; do
  aws ssm delete-parameter --name "$p"; done
aws ssm get-parameters-by-path --path /slack/installation --recursive --query "Parameters[].Name" --output text   # インストール時に作られたもの。あれば消す
```

---

## C. 検証用の Slack・Notion で通し動作（O-6・O-9）

**本番（受講生がいる）ワークスペースには入れない**。自分で作った無料のワークスペースだけで行う。

### C-1. Slack のワークスペースとチャンネル

1. https://slack.com/get-started で新しいワークスペースを作る（無料）
2. チャンネルを 2 つ作る：監視する公開チャンネル（例 `#general-test`）と、管理者用の**非公開**チャンネル（例 `#mod-alerts`）
3. 投稿する役のアカウントを 1 つ招待する（別のメールアドレス）。**表示名に「松尾研」を含めない**（スタッフとして判定が飛ばされる）
4. ワークスペースの ID（`T...`）と、管理者チャンネルの ID（`C...`）を控える（チャンネル名を右クリック → リンクをコピー の末尾、またはチャンネルの詳細の最下部）

### C-2. Slack アプリを作る

https://api.slack.com/apps → **Create New App** → From scratch → C-1 のワークスペース。

| 設定の場所 | 設定 |
|---|---|
| OAuth & Permissions → Redirect URLs | `SlackOAuthRedirectUrl`（B-4 の出力） |
| OAuth & Permissions → Bot Token Scopes | `chat:write`・`channels:read`・`channels:history`・`users:read`・`team:read`（CDK の `SlackBotScopes` と同じにする） |
| Event Subscriptions | Enable。Request URL に `SlackEventsRequestUrl`（`Verified` になること）。Subscribe to bot events に `message.channels` |
| Interactivity & Shortcuts | On。Request URL に `SlackInteractionsRequestUrl` |
| Basic Information | Signing Secret・Client ID・Client Secret を B-3 の SSM に入れる |

> Request URL の確認（`Verified`）は、署名の秘密が SSM に入っていないと失敗する。B-3 の後で行う。

### C-3. Notion を用意する

1. 無料の Notion のワークスペースで、https://www.notion.so/my-integrations から **Internal** のインテグレーションを作り、キーを B-3 の `/notion/api/key` に入れる
2. データベースを作る。違反 DB は `docs/notion_db_schema.md` のとおり。ほかは、コードが読む列だけの最小の形でよい：

| DB | 列（名前と型） | 中身 |
|---|---|---|
| 違反（`NotionDbId`） | `docs/notion_db_schema.md` を参考に、コードが書く列：`投稿内容`（タイトル）・`投稿者`・`チャンネル`・`ワークスペース`・`違反理由`・`Message_TS`・`team_id`・`通知チャンネルID`・`通知メッセージTS`（テキスト）、`検出日時`・`再警告送信日時`（日付）、`判定結果`・`検出方法`・`対応ステータス`・`重大度`（セレクト）、`違反カテゴリ`（マルチセレクト）、`信頼度`（数値）、`投稿リンク`（URL）、`対象条文`（条文マスタ DB へのリレーション）、`初回警告テンプレート`（テンプレート DB へのリレーション） | 空でよい |
| 条文マスタ（`NotionArticlesDbId`） | `条文ID`（タイトル）・`条項番号`・`内容`（テキスト）・`カテゴリ`・`規約`（セレクト）・`有効`（チェックボックス）・`workspace`（ワークスペース一覧 DB へのリレーション） | 空でよい（ローカルルールを試すときだけ 1 行足す） |
| ワークスペース一覧（`NotionWsListDbId`） | 名前（タイトル）・`team_id`（テキスト） | C-1 のワークスペースを 1 行 |
| テンプレート（`NotionTemplateDbId`） | `テンプレート名`（タイトル）・`用途`（セレクト）・`本文`（テキスト）・`有効`（チェックボックス） | 空でよい（コードの中の既定の文面が使われる） |
| ヘルス（`NotionHealthDbId`） | `Lambda名`（タイトル）・`ステータス`（セレクト）・`最終実行日時`（日付） | 空でよい |

3. 各 DB の右上「…」→「接続」から、1 のインテグレーションを追加する（追加しないと API から見えない）
4. 各 DB の ID（URL の `notion.so/` の後ろ、`?v=` の前の 32 文字）を控え、B-4 の `--parameters` に入れる

> 列の名前が 1 文字でも違うと、記録が失敗する（ログに `notion` のエラーが出る）。迷ったら `lambda/common/notion_client.py` の `create_violation_log` の列名を見る。

### C-4. インストールする

```bash
# 許可リスト（B-3 で入れていれば不要）
aws ssm get-parameter --name /slack/oauth/allowed_team_ids --with-decryption --query Parameter.Value --output text
```

ブラウザで次を開き、ワークスペースに許可する：

```text
<SlackOAuthStartUrl>?team=<T で始まる ID>&channel=<管理者チャンネルの C で始まる ID>
```

✅ 確認：「インストールできた」旨のページが出る。SSM に `/slack/installation/<T...>/bot_token` と `/alert_channel_id` ができる：

```bash
aws ssm get-parameters-by-path --path /slack/installation --recursive --query "Parameters[].Name" --output table
```

監視するチャンネルと管理者チャンネルの両方で `/invite @<アプリ名>` する。

### C-5. 通しで動かす

`docs/regression_checklist.md` の手順に沿って、次を確かめ、それぞれスクリーンショットを撮る。

| # | 操作 | 期待 | チェックリストの章 |
|---|---|---|---|
| 1 | 投稿する役で、明らかな違反の投稿（外部グループへの誘い・自作の文面）をする | 管理者チャンネルに通知とボタン。Notion に `未対応` の行。`検出方法` が `Bedrock` | 1 |
| 2 | 安全な投稿（宿題の質問）をする | 何も起きない | 1 |
| 3 | 日本語以外（英語・スワヒリ語など）で違反の投稿をする | 1 と同じ（多言語で動くことの証拠） | 1 |
| 4 | 管理者役で「承認」→ 投稿者へのスレッドの警告、`警告済み` | 4 |
| 5 | 1 の投稿を安全な内容に編集する | 管理者のスレッドに「解消」の返信、`対応終了` | 3 |
| 6 | **判定できなかった**場合（ガイド 06）：Lambda の環境変数 `BEDROCK_MODEL_ID` を一時的に存在しない ID に変えて投稿する | 管理者チャンネルに `[判定できなかった]` の通知、`検出方法` が `Undetermined`。CloudWatch のメトリクス `DetectionUndetermined` | — |
| 7 | 6 の後、環境変数を元に戻し、1 をもう一度 | 通常どおり | — |

6 の環境変数の変え方（コンソールでも可）：

```bash
FN=$(aws lambda list-functions --query "Functions[?contains(FunctionName, 'LambdaAAppInspect')].FunctionName" --output text)
echo $FN    # 1 つだけ出ることを確かめる（CDK の名前 LambdaA_AppInspect から作られる）。出なければコンソールで app_inspect の関数名を確かめる
aws lambda get-function-configuration --function-name "$FN" --query Environment.Variables > /tmp/env_before.json
python3 - <<'PY'
import json; e = json.load(open("/tmp/env_before.json")); e["BEDROCK_MODEL_ID"] = "apac.amazon.nova-does-not-exist-v1:0"
json.dump({"Variables": e}, open("/tmp/env_broken.json", "w"))
PY
aws lambda update-function-configuration --function-name "$FN" --environment file:///tmp/env_broken.json >/dev/null
# … 投稿して確かめる …
python3 -c 'import json; json.dump({"Variables": json.load(open("/tmp/env_before.json"))}, open("/tmp/env_restore.json", "w"))'
aws lambda update-function-configuration --function-name "$FN" --environment file:///tmp/env_restore.json >/dev/null
rm /tmp/env_*.json
```

> 環境変数のファイルには秘密の値は入っていない（秘密は SSM）が、作業が終わったら消す。

### C-6. 証跡を残す

- スクリーンショットは `docs/purchase_order/e2e/` に `01_alert.png` のように番号を付けて置く。**写っているのは自分の検証用のワークスペースだけ**であることを確かめる。トークン・キー・アカウント ID が写っていたら塗りつぶす
- `docs/purchase_order/e2e/README.md` に、C-5 の表に結果（✅ / ❌・日時・スクリーンショットのファイル名）を書く
- デモ動画（O-9・任意）：C-5 の 1・3・4・6 を 2〜3 分で録画する（macOS は `Shift + Command + 5`）。動画はリポジトリに入れず、提出の方法は講座の指示に従う

💾 コミット：`docs: 検証用の Slack・Notion での通し動作の記録とスクリーンショット（O-6）`

---

## ⚠️ つまずきやすい点

- Event Subscriptions の Request URL が `Verified` にならない：SSM の `/slack/signing/secret` の値の誤り、または B-4 のデプロイ前。CloudWatch Logs の `app_inspect` のログを見る
- 投稿しても何も起きない：アプリがチャンネルに招待されていない（`/invite`）、表示名に「松尾研」が入っている、`MinSeverityToAlert` が `high` で重大度が足りない
- Notion に行ができない：DB にインテグレーションを接続していない、列の名前・型の違い
- `cdk deploy` が IAM ユーザーの作成で失敗する：B-1 の注を参照
- 料金：API Gateway・Lambda・CloudWatch はほぼ無料の範囲。Bedrock は投稿の数だけ。終わったら B-5 で消す

## 完了の条件

- [ ] A：`system_review.md` に、上限に届く規模の表・課題の見直し・非同期化の案がある
- [ ] B：（行った場合）デプロイの記録がある。課題の終了後の後片付けの予定を決めた
- [ ] C：（行った場合）C-5 の 1〜7 の結果とスクリーンショットがある
