# 02 判定を Amazon Bedrock へ移す

発注書 3 章「開発の進め方（最初のステップ）」の (1)。**今の判定方式の経路 B を、そのまま Bedrock のモデルで動かす**ところまでを行います。精度の改善はまだしません（ここで作ったものが、ガイド 03 のベースラインになります）。

## ゴール

- `DETECTION_MODE=bedrock` で、`ViolationDetector` が Amazon Nova を使って判定できる
- 本番のコード（`app_inspect`・`app_batch`）と CDK が、`bedrock` 方式で動く設定を持つ
- 追加したコードにテストがあり、`pytest tests/` が全件通る

## 前提

- [01 環境の準備](./01_setup.md) が終わっている
- 講座の AWS 環境を受け取っている（第 7 回・2026-11-30）

## 設計の要点（なぜこの形にするか）

経路 B（`ViolationDetector._judge_by_chat_pipeline` と `_choose_article`）は、LLM を次の **1 か所の呼び方** でしか使っていません。

```python
self.client.chat.completions.create(model=..., messages=[...], response_format={"type": "json_schema", ...})
```

そこで、Bedrock の Converse API を**この呼び方で受けるアダプター**（`BedrockChatClient`）を 1 つ作り、`openai_client` の代わりに渡します。

```text
ViolationDetector（変更は方式の名前を 1 つ足すだけ）
   └ client.chat.completions.create(model, messages, response_format)
        ├ OpenAI のクライアント（今まで）
        └ BedrockChatClient（新規）── Converse API
              response_format の JSON Schema → tool use（toolChoice で強制）に置き換えて、必ずその形の JSON を返させる
```

- 判定の流れ（2 段・候補の整え方・失敗時の扱い）を**1 行も変えずに**モデルだけを替えられる → 「モデルを替えたことによる差」（M-3）を純粋に測れる
- 評価のハーネス（`evals/promptfoo/harness.py`）も、クライアントを差し替えるだけで同じように記録できる
- Bedrock には OpenAI の `response_format: json_schema` が無い。代わりに **tool use の入力スキーマ**として渡し、`toolChoice` でそのツールを必ず使わせると、スキーマどおりの JSON が返る

---

## 手順

### 1. ブランチを切る

```bash
git switch develop && git pull
git switch -c feat/bedrock-client
source .venv/bin/activate
```

### 2. AWS CLI を入れて、講座の AWS 環境につなぐ

```bash
brew install awscli
aws --version
```

認証は第 7 回の講義で案内される方法に従う。よくある 2 通り：

```bash
# A. IAM Identity Center（SSO）の場合
aws configure sso --profile aie          # 案内された開始 URL・リージョン・アカウント・ロールを入れる
aws sso login --profile aie

# B. アクセスキーを渡された場合（キーはファイルに書かず、ここで入力するだけ）
aws configure --profile aie
```

以降のターミナルでは毎回これを設定する（`.zshrc` に書いてもよいが、キーそのものは書かない）。

```bash
export AWS_PROFILE=aie
export AWS_REGION=ap-northeast-1      # 講座の案内に合わせる
aws sts get-caller-identity
```

✅ 確認：`Account`・`Arn` が表示される。

### 3. 使える Nova のモデルを確かめる

```bash
# 基盤モデル（Amazon 提供）の ID
aws bedrock list-foundation-models --by-provider amazon \
  --query "modelSummaries[?contains(modelId, 'nova')].[modelId, inferenceTypesSupported]" --output table

# 推論プロファイル（リージョンをまたぐ呼び出し用）の ID
aws bedrock list-inference-profiles \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'nova')].inferenceProfileId" --output table
```

- 東京リージョンなどでは、Nova は**推論プロファイル経由**（例：`apac.amazon.nova-lite-v1:0`）でしか呼べないことが多い。`inferenceTypesSupported` が `INFERENCE_PROFILE` だけなら、プロファイルの ID を使う
- コンソールの「Bedrock → Model access」で Nova Micro / Lite が「Access granted」になっているかも見る。なっていなければ講座の案内に従う（自分で申請できない場合は質問フォームへ）

疎通を確かめる（Micro と Lite の両方）：

```bash
for M in apac.amazon.nova-micro-v1:0 apac.amazon.nova-lite-v1:0; do
  aws bedrock-runtime converse --model-id "$M" \
    --messages '[{"role":"user","content":[{"text":"「こんにちは」を英語にしてください。"}]}]' \
    --inference-config '{"maxTokens":50,"temperature":0}' \
    --query "output.message.content[0].text" --output text
done
```

✅ 確認：両方のモデルから返事が出る。`AccessDeniedException` → モデルのアクセス、`ValidationException ... on-demand throughput isn't supported` → 基盤モデルの ID ではなく推論プロファイルの ID を使う。

### 4. 環境の情報と単価を記録する

[`docs/purchase_order/experiments/env.md`](../experiments/README.md) を作り、次を書いて commit する（**アカウント ID・キーは書かない**）。

```markdown
# 評価・実行の環境（YYYY-MM-DD 確認）

| 項目 | 値 |
|---|---|
| リージョン | ap-northeast-1 |
| Nova Micro | apac.amazon.nova-micro-v1:0 |
| Nova Lite | apac.amazon.nova-lite-v1:0 |
| 単価（USD / 100 万トークン） | Micro 入力 x.xxx・出力 x.xxx ／ Lite 入力 x.xxx・出力 x.xxx（https://aws.amazon.com/bedrock/pricing/ 、YYYY-MM-DD 時点） |
| Converse の上限（1 分あたりの要求数・トークン数） | Service Quotas で確認した値 |
```

上限は「Service Quotas → Amazon Bedrock」で `nova` を検索して確認する。ガイド 03 の並列数と、ガイド 09 のレビュー（課題 5）で使う。

💾 コミット：`docs: Bedrock の評価環境（リージョン・モデル ID・単価・上限）を記録`

### 5. アダプター `BedrockChatClient` を作る

新しいファイル `lambda/common/bedrock_client.py`：

```python
"""Amazon Bedrock の Converse API を、OpenAI の chat.completions と同じ呼び方で使うためのアダプター。

ViolationDetector の経路 B は client.chat.completions.create(model=..., messages=..., response_format=...)
だけを使う。この呼び方をそのまま受け、response_format の JSON Schema を Bedrock の tool use に置き換えて、
必ずその形の JSON を返させる。戻り値は OpenAI の応答と同じ属性（choices[0].message.content・usage）を持つ。
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any, Optional

import boto3
from botocore.config import Config

# スロットリング（429 相当）と一時的なエラーは boto3 が待ちながら再試行する（adaptive は送る速さも自動で落とす）
DEFAULT_BOTO_CONFIG = Config(
    connect_timeout=3,
    read_timeout=20,
    retries={"max_attempts": 4, "mode": "adaptive"},
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


class BedrockChatClient:
    def __init__(
        self,
        region_name: Optional[str] = None,
        runtime: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ):
        self._runtime = runtime or boto3.client(
            "bedrock-runtime", region_name=region_name, config=DEFAULT_BOTO_CONFIG
        )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = None  # 評価のハーネス（RecordingClient）が参照する属性
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model: str, messages: list[dict], response_format: Optional[dict] = None, **_: Any):
        system = [{"text": m["content"]} for m in messages if m.get("role") == "system"]
        conversation = [
            {"role": m["role"], "content": [{"text": m["content"]}]}
            for m in messages
            if m.get("role") != "system"
        ]
        kwargs: dict[str, Any] = {
            "modelId": model,
            "messages": conversation,
            "inferenceConfig": {"temperature": self.temperature, "maxTokens": self.max_tokens},
        }
        if system:
            kwargs["system"] = system

        schema = _json_schema_of(response_format)
        if schema:
            kwargs["toolConfig"] = {
                "tools": [{
                    "toolSpec": {
                        "name": schema["name"],
                        "description": "判定の結果を、この形で返す",
                        "inputSchema": {"json": schema["schema"]},
                    }
                }],
                "toolChoice": {"tool": {"name": schema["name"]}},
            }

        resp = self._runtime.converse(**kwargs)
        usage = resp.get("usage", {}) or {}
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_content_of(resp, bool(schema))))],
            usage=SimpleNamespace(
                prompt_tokens=usage.get("inputTokens", 0) or 0,
                completion_tokens=usage.get("outputTokens", 0) or 0,
                prompt_tokens_details=SimpleNamespace(cached_tokens=usage.get("cacheReadInputTokens", 0) or 0),
            ),
        )


def _json_schema_of(response_format: Optional[dict]) -> Optional[dict]:
    if isinstance(response_format, dict) and response_format.get("type") == "json_schema":
        return response_format.get("json_schema")
    return None


def _content_of(resp: dict, want_tool: bool) -> str:
    blocks = (((resp.get("output") or {}).get("message") or {}).get("content")) or []
    if want_tool:
        for b in blocks:
            if "toolUse" in b:
                return json.dumps(b["toolUse"].get("input", {}), ensure_ascii=False)
    text = "".join(b.get("text", "") for b in blocks)
    return _FENCE_RE.sub("", text.strip())
```

ポイント：

- `toolChoice: {"tool": ...}` で、そのツール（＝スキーマどおりの JSON）を**必ず**返させる。モデルがツールを使わずに文章を返したときは、文章を（コードブロックの囲みを外して）そのまま返す。`json.loads` に失敗すれば、経路 B が「LLM判定エラー」として扱う（今のコードと同じ動き）
- `temperature=0`：同じ投稿に同じ判定を返しやすくする（「判定の安定性」の指標）。**OpenAI 版では温度を指定していない**ので、この違いは説明資料の「ベースラインの作り方」に書く
- 再試行は boto3 に任せる（`adaptive`）。タイムアウトも付けるので、Lambda の 30 秒を使い切って投稿ごと失われる（ISS-02）ことを防ぐ

### 6. アダプターのテストを書く

新しいファイル `tests/unit/test_bedrock_client.py`：

```python
import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from common.bedrock_client import BedrockChatClient

SCHEMA_RF = {
    "type": "json_schema",
    "json_schema": {
        "name": "warn_decision_cands",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"decision": {"type": "string", "enum": ["warn", "safe"]}},
            "required": ["decision"],
            "additionalProperties": False,
        },
    },
}


def _resp(content: list, in_tok: int = 100, out_tok: int = 20) -> dict:
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "usage": {"inputTokens": in_tok, "outputTokens": out_tok, "totalTokens": in_tok + out_tok},
    }


def _client(resp: dict | Exception) -> tuple[BedrockChatClient, MagicMock]:
    runtime = MagicMock()
    if isinstance(resp, Exception):
        runtime.converse.side_effect = resp
    else:
        runtime.converse.return_value = resp
    return BedrockChatClient(runtime=runtime), runtime


def test_json_schema_is_sent_as_forced_tool_and_tool_input_is_returned():
    client, runtime = _client(_resp([{"toolUse": {"toolUseId": "t1", "name": "warn_decision_cands",
                                                  "input": {"decision": "warn"}}}]))

    resp = client.chat.completions.create(
        model="apac.amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": "投稿"}],
        response_format=SCHEMA_RF,
    )

    assert json.loads(resp.choices[0].message.content) == {"decision": "warn"}
    kw = runtime.converse.call_args.kwargs
    assert kw["modelId"] == "apac.amazon.nova-lite-v1:0"
    assert kw["messages"] == [{"role": "user", "content": [{"text": "投稿"}]}]
    assert kw["toolConfig"]["toolChoice"] == {"tool": {"name": "warn_decision_cands"}}
    spec = kw["toolConfig"]["tools"][0]["toolSpec"]
    assert spec["inputSchema"]["json"] == SCHEMA_RF["json_schema"]["schema"]
    assert kw["inferenceConfig"]["temperature"] == 0.0


def test_usage_is_mapped_to_openai_names():
    client, _ = _client(_resp([{"text": "ok"}], in_tok=321, out_tok=7))
    resp = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert resp.usage.prompt_tokens == 321
    assert resp.usage.completion_tokens == 7
    assert resp.usage.prompt_tokens_details.cached_tokens == 0


def test_without_schema_returns_text_and_strips_code_fence():
    client, runtime = _client(_resp([{"text": '```json\n{"a": 1}\n```'}]))
    resp = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert json.loads(resp.choices[0].message.content) == {"a": 1}
    assert "toolConfig" not in runtime.converse.call_args.kwargs


def test_text_is_returned_when_model_does_not_use_the_tool():
    client, _ = _client(_resp([{"text": '{"decision": "safe"}'}]))
    resp = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}],
                                          response_format=SCHEMA_RF)
    assert json.loads(resp.choices[0].message.content) == {"decision": "safe"}


def test_system_messages_go_to_system_field():
    client, runtime = _client(_resp([{"text": "ok"}]))
    client.chat.completions.create(model="m", messages=[{"role": "system", "content": "規則"},
                                                        {"role": "user", "content": "投稿"}])
    kw = runtime.converse.call_args.kwargs
    assert kw["system"] == [{"text": "規則"}]
    assert kw["messages"] == [{"role": "user", "content": [{"text": "投稿"}]}]


def test_api_error_propagates_to_caller():
    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse")
    client, _ = _client(err)
    with pytest.raises(ClientError):
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
```

```bash
pytest tests/unit/test_bedrock_client.py -q
```

✅ 確認：6 件とも成功。

💾 コミット：`feat: Bedrock の Converse API を chat.completions の形で呼ぶアダプターを追加`

### 7. `ViolationDetector` に `bedrock` 方式を足す

`lambda/app_inspect/services/violation_detector.py` を 3 か所だけ変える。

(a) `__init__` の方式の一覧に `bedrock` を足す：

```python
        elif mode not in ("auto", "llm_score", "decisions", "luna", "bedrock"):
```

(b) `auto` のとき、Nova のモデル名なら `bedrock` にする（設定の間違いで Decisions API を呼びに行かないように）：

```python
        if mode == "auto":
            judge_model_norm = (self.judge_model or "").strip().lower()
            if judge_model_norm.startswith("gpt-4o-mini"):
                resolved_mode = "llm_score"
            elif "nova" in judge_model_norm:
                resolved_mode = "bedrock"
            else:
                resolved_mode = "decisions"
```

(c) `detect` の分岐に `bedrock` を足す（中身は経路 B と同じ。`method` だけ分ける）：

```python
        elif self.detection_mode == "luna":
            result = self._judge_by_chat_pipeline(text, articles)
            method = "Luna"
        elif self.detection_mode == "bedrock":
            result = self._judge_by_chat_pipeline(text, articles)
            method = "Bedrock"
```

モジュールの先頭の docstring にも 1 行足す（`CLAUDE.md` が「変更前に読む」としている場所）：

```text
DETECTION_MODE=bedrock は経路 B（_judge_by_chat_pipeline）を Amazon Bedrock で動かす。
クライアントは common.bedrock_client.BedrockChatClient（chat.completions と同じ呼び方のアダプター）。
```

### 8. `ViolationDetector` のテストを足す

`tests/unit/test_violation_detector.py`：

(a) `test_detection_mode_resolution` の `parametrize` の一覧に足す：

```python
        # bedrock
        (None, "bedrock", "apac.amazon.nova-lite-v1:0", "bedrock"),
        (" BEDROCK ", None, "apac.amazon.nova-micro-v1:0", "bedrock"),
        ("auto", None, "apac.amazon.nova-lite-v1:0", "bedrock"),
        (None, None, "amazon.nova-micro-v1:0", "bedrock"),
```

(b) `test_luna_mode_warn_pipeline` をまねて、`bedrock` の 2 段の流れのテストを足す：

```python
def test_bedrock_mode_runs_chat_pipeline_without_decisions_api(
    mocker, tmp_articles_file, mock_openai_client, monkeypatch
):
    monkeypatch.setenv("DETECTION_MODE", "bedrock")
    mock_post = mocker.patch("app_inspect.services.violation_detector.requests.post")
    mock_openai_client.chat.completions.create.side_effect = [
        _make_chat_response({"decision": "warn", "candidates": ["11-v", "11-xiii"], "reason": "勧誘疑い"}),
        _make_chat_response({"article_id": "11-v", "reason": "マルチ勧誘行為"}),
    ]

    detector = ViolationDetector(
        openai_client=mock_openai_client,
        judge_model="apac.amazon.nova-lite-v1:0",
        articles_path=tmp_articles_file,
    )
    result = detector.detect("ビジネスに興味ある人DMください")

    assert result.is_violation is True
    assert result.article_id == "11-v"
    assert result.method == "Bedrock"
    mock_post.assert_not_called()
    assert mock_openai_client.chat.completions.create.call_count == 2
```

⚠️ `tmp_articles_file` の条文に `11-v` が無い場合は、同じファイルの `test_luna_mode_warn_pipeline` が使っている ID に合わせる。

```bash
pytest tests/unit/test_violation_detector.py -q
pytest tests/ -q
```

✅ 確認：全件成功し、件数が「01 で控えた N ＋ 追加した分」になっている。

💾 コミット：`feat: 判定方式に bedrock（経路 B を Bedrock で動かす）を追加`

### 9. 本番のコードからクライアントを切り替えられるようにする

`app_inspect` と `app_batch` は、今は `OpenAI(api_key=...)` を直接作っている。これを 1 か所にまとめる。

新しいファイル `lambda/common/llm_client.py`：

```python
"""判定に使う LLM のクライアントとモデル名を、環境変数 DETECTION_MODE に応じて作る。"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from common.bedrock_client import BedrockChatClient


def build_llm_client(openai_api_key: str, openai_model: str) -> tuple[Any, str]:
    mode = (os.environ.get("DETECTION_MODE") or "").strip().lower()
    if mode == "bedrock":
        model_id = (os.environ.get("BEDROCK_MODEL_ID") or "").strip()
        if not model_id:
            raise RuntimeError("DETECTION_MODE=bedrock なのに BEDROCK_MODEL_ID がありません")
        return BedrockChatClient(region_name=os.environ.get("BEDROCK_REGION") or None), model_id
    return OpenAI(api_key=openai_api_key), openai_model
```

`OpenAI` と `BedrockChatClient` はモジュールの先頭で import する（テストが `common.llm_client.OpenAI` を差し替えられるようにするため）。

`lambda/app_inspect/handler.py` の `_build_moderation_executor` の中：

```python
            # 変更前
            openai_client = OpenAI(api_key=cfg.openai_api_key)
            ...
            result = run_moderation(
                openai_client,
                cfg.openai_model,
                text,
                extra_articles=extra_articles,
            )

            # 変更後
            llm_client, model = build_llm_client(cfg.openai_api_key, cfg.openai_model)
            ...
            result = run_moderation(
                llm_client,
                model,
                text,
                extra_articles=extra_articles,
            )
```

- 先頭の import に `from common.llm_client import build_llm_client` を足し、`from openai import OpenAI` を消す
- **`tests/conftest.py` の `mock_external_services` が `app_inspect.handler.OpenAI` を差し替えている**ので、その 1 行を次に変える（消すと、handler のテストが本物の OpenAI のクライアントを作ってしまう）：

```python
    mocker.patch("common.llm_client.OpenAI", return_value=mock_openai_client)
```

`lambda/app_batch/handler.py` も同じ形にする。既存のテスト（`tests/unit/test_app_batch.py` の `_moderate(cfg, MagicMock(), "sample")`）を壊さないように、`_moderate` には**省略できる** `model` 引数を足す：

```python
        # lambda_handler の中（変更前）
        openai_client = None if cfg.use_mock_openai else OpenAI(api_key=cfg.openai_api_key)
        ...
            result = _moderate(cfg, openai_client, text)

        # 変更後
        if cfg.use_mock_openai:
            llm_client, model = None, cfg.openai_model
        else:
            llm_client, model = build_llm_client(cfg.openai_api_key, cfg.openai_model)
        ...
            result = _moderate(cfg, llm_client, text, model=model)


# _moderate（変更後）
def _moderate(cfg, llm_client, text: str, model: str | None = None) -> ModerationResult:
    ...
    result = run_moderation(
        llm_client,
        model or cfg.openai_model,
        text,
    )
```

⚠️ `app_batch` は今まで旧方式（gpt-4o-mini）のままだった（ISS-07）。`DETECTION_MODE=bedrock` を渡せば、バッチも同じ判定になる。`tests/repro/test_iss07_batch_uses_old_model.py` は「`OPENAI_MODEL` が無いと gpt-4o-mini になる」ことを固定しているテストで、この変更では壊れない（設定の既定値は変えないため）。

テスト `tests/unit/test_llm_client.py`：

```python
import pytest

from common.bedrock_client import BedrockChatClient
from common.llm_client import build_llm_client


def test_bedrock_mode_returns_bedrock_client_and_model_id(monkeypatch):
    monkeypatch.setenv("DETECTION_MODE", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "apac.amazon.nova-lite-v1:0")
    client, model = build_llm_client("sk-unused", "gpt-6-luna")
    assert isinstance(client, BedrockChatClient)
    assert model == "apac.amazon.nova-lite-v1:0"


def test_bedrock_mode_without_model_id_fails_fast(monkeypatch):
    monkeypatch.setenv("DETECTION_MODE", "bedrock")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    with pytest.raises(RuntimeError):
        build_llm_client("sk-unused", "gpt-6-luna")


def test_other_modes_keep_openai(monkeypatch):
    monkeypatch.setenv("DETECTION_MODE", "decisions")
    client, model = build_llm_client("sk-test", "gpt-6-luna")
    assert type(client).__name__ == "OpenAI"
    assert model == "gpt-6-luna"
```

```bash
pytest tests/ -q
```

✅ 確認：全件成功。失敗したら、**テストの期待値は変えず**、差し替える場所（`mocker.patch(...)` の文字列）だけを直す。

💾 コミット：`feat: DETECTION_MODE に応じて判定の LLM クライアントを作る build_llm_client を追加し、inspect と batch で使う`

### 10. CDK に Bedrock の設定と権限を足す

`infra/stacks/infra_stack.py`：

(a) `DetectionMode` の許す値に `bedrock` を足し、パラメーターを 2 つ足す：

```python
        detection_mode = CfnParameter(
            self,
            "DetectionMode",
            type="String",
            default="auto",
            allowed_values=["auto", "llm_score", "decisions", "luna", "bedrock"],
            description="Violation detection mode (auto, llm_score, decisions, luna, bedrock).",
        )

        bedrock_model_id = CfnParameter(
            self,
            "BedrockModelId",
            type="String",
            default="apac.amazon.nova-lite-v1:0",
            description="Bedrock model ID or inference profile ID used when DetectionMode=bedrock.",
        )

        bedrock_region = CfnParameter(
            self,
            "BedrockRegion",
            type="String",
            default="",
            description="Region of the Bedrock runtime. Empty means the Lambda's region.",
        )
```

(b) `LambdaA_AppInspect` と、`DETECTION_MODE` を持つもう 1 つの Lambda（`app_batch`、`timeout=Duration.seconds(900)` のもの）の `environment` に足す：

```python
                "BEDROCK_MODEL_ID": bedrock_model_id.value_as_string,
                "BEDROCK_REGION": bedrock_region.value_as_string,
```

(c) 「7. IAM権限付与」の近くに、Bedrock を呼ぶ権限を足す（Converse は `bedrock:InvokeModel` の権限で呼べる）：

```python
        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
            ],
        )
        lambda_a.add_to_role_policy(bedrock_policy)
        lambda_e.add_to_role_policy(bedrock_policy)
```

推論プロファイルはリージョンをまたいで基盤モデルを呼ぶので、基盤モデルの ARN のリージョンを `*` にしている。

```bash
cd infra
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npx aws-cdk@2 synth > /tmp/synth.yaml && echo OK
grep -n "BEDROCK_MODEL_ID\|bedrock:InvokeModel" /tmp/synth.yaml | head
deactivate && cd .. && source .venv/bin/activate
```

✅ 確認：`OK` が出て、テンプレートに環境変数と権限が入っている。

💾 コミット：`feat(infra): DetectionMode に bedrock を追加し、Bedrock のモデル ID と呼び出し権限を設定`

### 11. 手元で本物の Bedrock を呼んで確かめる（スモーク）

架空の投稿 2 件で、Micro と Lite の両方を試す（commit しない、その場のスクリプト）。

```bash
export AWS_PROFILE=aie AWS_REGION=ap-northeast-1
python - <<'EOF'
import sys
sys.path.insert(0, "lambda")
from common.bedrock_client import BedrockChatClient
from app_inspect.services.violation_detector import ViolationDetector

posts = [
    "明日の講義の資料はどこにありますか？",
    "Join our WhatsApp group for AI jobs! Send me your number and I will add you.",
]
for model in ["apac.amazon.nova-micro-v1:0", "apac.amazon.nova-lite-v1:0"]:
    det = ViolationDetector(openai_client=BedrockChatClient(), judge_model=model, detection_mode="bedrock")
    for t in posts:
        r = det.detect(t)
        print(model.split(".")[2], r.is_violation, r.article_id, r.method, r.reason[:60])
EOF
```

✅ 確認：1 件目が `False`、2 件目が `True`（条文は `11-…` のどれか）。どちらかの `reason` が `LLM判定エラー` で始まっていたら、その後ろのエラー文を読む：

| エラー | 対処 |
|---|---|
| `ValidationException ... toolChoice` | そのモデルが `toolChoice: tool` に対応していない。アダプターの `"toolChoice"` を `{"any": {}}` に変えて試す |
| `ValidationException ... inputSchema` | スキーマの書き方が受け付けられていない。エラー文の場所を見て、アダプター側でその項目（例：`strict`）を取り除く |
| `JSONDecodeError` | ツールを使わずに文章で返している。手順 5 の `_content_of` が文章を返している。プロンプトの「JSON だけを出力する」を確認 |
| `AccessDeniedException` | 手順 3 のモデルのアクセス |

### 12. PR を作る

```bash
git push -u origin feat/bedrock-client
gh pr create --base develop --title "feat: 判定を Amazon Bedrock（経路 B）で動かす" \
  --body "ガイド 02。BedrockChatClient・DETECTION_MODE=bedrock・build_llm_client・CDK の設定と権限・テスト"
```

✅ 確認：CI が緑になってからマージする。

---

## ⚠️ つまずきやすい点

- **推論プロファイル ID と基盤モデル ID の取り違え**が一番多い。`apac.` / `us.` / `global.` で始まるのがプロファイル
- `temperature` などの設定値を変えたら、その時点でベースラインとは別物になる。ベースラインを測る前に決めて、[env.md](../experiments/README.md) に書いておく
- `BedrockChatClient` は呼び出しのたびに boto3 のクライアントを作らない（作るのは初期化のときだけ）。Lambda では、ハンドラーの外で作って使い回すと速くなる（ガイド 06 で扱う）
- `pytest` は AWS に接続しない。`BedrockChatClient()` を引数なしで作るテストは、`boto3.client` を作るだけで通信はしない（`tests/conftest.py` がリージョンを設定している）

## 完了の条件

- [ ] Nova Micro / Lite を CLI から呼べた。モデル ID・単価・上限を `experiments/env.md` に記録した
- [ ] `BedrockChatClient` とそのテスト（6 件）
- [ ] `DETECTION_MODE=bedrock` とそのテスト
- [ ] `build_llm_client` を `app_inspect`・`app_batch` で使い、テストが通る
- [ ] CDK の `synth` が通り、Bedrock の環境変数と権限が入った
- [ ] 手元のスモークで、2 件とも期待どおりの判定になった
- [ ] PR をマージした
