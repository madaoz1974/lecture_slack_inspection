# 03 ベースラインを測る（Bedrock 版ベースライン）

発注書 3 章の (2)(3) と必須要件 M-2・M-3。ガイド 02 で作った `bedrock` 方式を、提供データ 354 件で**言語別に**測り、以降の改善の基準（Bedrock 版ベースライン）にします。

## ゴール

- 評価のハーネス（`evals/promptfoo/harness.py`）が `bedrock` 方式で動き、トークン数・時間・費用が記録される
- シナリオ単位の dev / test 分割（ID の一覧）がリポジトリにある
- Nova Micro と Nova Lite の両方で、354 件 × 3 回のベースラインを測り、言語別の集計を記録した
- 以降の改善で使う**主なモデル**と、その理由を決めた
- OpenAI 版（運営の計測）との差を表にした

## 前提

- [02 判定を Bedrock へ移す](./02_bedrock_migration.md) が `develop` に入っている
- `evals/promptfoo/datasets/testcases.yaml`（354 件）がある（ガイド 01）

---

## 手順

### 1. ブランチを切る

```bash
git switch develop && git pull
git switch -c feat/eval-bedrock
source .venv/bin/activate
export AWS_PROFILE=aie AWS_REGION=ap-northeast-1
```

### 2. ハーネスを `bedrock` 方式に対応させる

`evals/promptfoo/harness.py` を 5 か所変える。

(a) 既定のモデルに `bedrock` を足す：

```python
MODELS = {
    "decisions": "gpt-6-luna",
    "luna": "gpt-6-luna",
    "llm_score": "gpt-4o-mini",
    "bedrock": "apac.amazon.nova-lite-v1:0",
}
```

(b) 単価に Nova を足す。値は**ガイド 02 の手順 4 で `experiments/env.md` に記録した値**を入れる（下は書式の例。数値は必ず差し替える）：

```python
# Bedrock（Nova）は https://aws.amazon.com/bedrock/pricing/ の値（experiments/env.md に確認日を記録）
PRICES.update({
    ("chat", "apac.amazon.nova-micro-v1:0"): {"in": 0.0, "cached": 0.0, "out": 0.0},  # ← 差し替える
    ("chat", "apac.amazon.nova-lite-v1:0"): {"in": 0.0, "cached": 0.0, "out": 0.0},   # ← 差し替える
})
```

(c) クライアントを方式ごとに作る（OpenAI と Bedrock を 1 回の評価の中で並べても混ざらないように）。`_client = None` から `get_client` までを置き換える：

```python
_clients: dict[str, RecordingClient] = {}
_client_lock = threading.Lock()


def get_client(prompts_from_head: bool = False, mode: str = "decisions") -> RecordingClient:
    kind = "bedrock" if mode == "bedrock" else "openai"
    with _client_lock:
        if kind not in _clients:
            install_patches(prompts_from_head)
            if kind == "bedrock":
                from common.bedrock_client import BedrockChatClient

                real = BedrockChatClient(region_name=os.environ.get("BEDROCK_REGION") or None)
            else:
                real = OpenAI(api_key=load_api_key(), max_retries=2, timeout=60)
            _clients[kind] = RecordingClient(real)
    return _clients[kind]
```

`RecordingClient` は `api_key` と `chat.completions.create` だけを使うので、`BedrockChatClient` をそのまま包める（トークン数は `usage.prompt_tokens` などから記録される）。

(d) `detect` の中の `get_client` の呼び出しに方式を渡す：

```python
    client = get_client(prompts_from_head, mode)
```

(e) 判定の理由も結果に残す（ガイド 04 の誤り分析で、モデルが何を根拠に間違えたかを読むため）。`detect` の成功時の `return` の辞書に 1 項目足す：

```python
        return {"error": None, "is_violation": bool(res.is_violation), "article_id": res.article_id,
                "reason": res.reason[:300],
```

理由には投稿の一部が引用されることがあるが、結果の JSON（`output/`）は commit しないので問題ない。`summarize.py` は理由を出力しない。

モジュールの先頭の docstring にも「`bedrock` 方式は `BedrockChatClient` を使う。再試行は boto3 の adaptive」と 1 行足す。

✅ 確認（AWS を呼ばずに、偽の応答で動きを確かめる）：

```bash
cd evals/promptfoo
python - <<'EOF'
import json
from unittest.mock import MagicMock, patch

fake = MagicMock()
fake.converse.side_effect = [
    {"output": {"message": {"content": [{"toolUse": {"toolUseId": "1", "name": "warn_decision_cands",
        "input": {"decision": "warn", "candidates": ["11-v"], "reason": "勧誘"}}}]}},
     "usage": {"inputTokens": 3000, "outputTokens": 40}},
    {"output": {"message": {"content": [{"toolUse": {"toolUseId": "2", "name": "article_choice",
        "input": {"article_id": "11-v", "reason": "勧誘"}}}]}},
     "usage": {"inputTokens": 1200, "outputTokens": 30}},
]
with patch("boto3.client", return_value=fake):
    import harness
    r = harness.detect("Join my group", mode="bedrock", model="apac.amazon.nova-lite-v1:0")
print(json.dumps({k: r[k] for k in ("error", "is_violation", "article_id", "method", "cost_usd")}, ensure_ascii=False))
print([(c["api"], c["model"], c["in"], c["out"]) for c in r["calls"]])
EOF
cd ../..
```

`"error": null`・`"is_violation": true`・`"method": "Bedrock"` が出て、`calls` に 2 件（3000/40 と 1200/30）が記録されていれば正しい。`cost_usd` は (b) の単価を入れていれば 0 より大きい。

💾 コミット：`feat(evals): 評価のハーネスを bedrock 方式（Nova）に対応させる`

### 3. promptfoo の設定に Nova の行を足す

`evals/promptfoo/promptfooconfig.yml` の `providers` を次にする（OpenAI の行は残し、比べるときに使う）：

```yaml
providers:
  - id: file://provider.py
    label: decisions
    config:
      mode: decisions
      workers: 4
  - id: file://provider.py
    label: bedrock-micro
    config:
      mode: bedrock
      model: apac.amazon.nova-micro-v1:0
      workers: 4
  - id: file://provider.py
    label: bedrock-lite
    config:
      mode: bedrock
      model: apac.amazon.nova-lite-v1:0
      workers: 4
```

実行するときは **`--filter-providers` で 1 つに絞る**（絞らないと全部の方式が走り、OpenAI のキーが無ければ `decisions` が全件失敗する）。

💾 コミット：`feat(evals): promptfoo の設定に Nova Micro / Lite の方式を追加`

### 4. シナリオ単位の dev / test 分割を作る

同じシナリオの 6 言語の対訳が dev と test の両方に入ると、dev で合わせた結果がそのまま test に漏れる。**シナリオ（`scenario_id`）単位**で分ける。

新しいファイル `evals/promptfoo/make_split.py`：

```python
#!/usr/bin/env python3
"""評価データを、シナリオ（scenario_id）単位で dev（改善の試行）と test（最後の確認）に分ける。

同じシナリオの対訳が両方に入らないようにする。警告すべきか（W/S）と難しさ（degree）で層に分け、
各層の中で乱数（種を固定）で振り分ける。言語混在（X〜）は件数が少ないので全部 test に入れる。
出力は ID の一覧だけ（本文を含まない）なので、リポジトリに置いてよい。

    python make_split.py datasets/eval_posts.csv            # → splits/pjt04_split.json
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from load_dataset import _bool, read_rows

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--dev-ratio", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--output", type=Path, default=HERE / "splits" / "pjt04_split.json")
    a = ap.parse_args()

    first: dict[str, dict] = {}
    for r in read_rows(a.dataset):
        first.setdefault(r["scenario_id"], r)

    strata: dict[tuple[bool, str], list[str]] = defaultdict(list)
    mixed: list[str] = []
    for sc, r in first.items():
        if sc.startswith("X"):
            mixed.append(sc)
        else:
            strata[(_bool(r["is_violation"]), r.get("degree", ""))].append(sc)

    rng = random.Random(a.seed)
    dev: list[str] = []
    test: list[str] = []
    for key in sorted(strata):
        scs = sorted(strata[key])
        rng.shuffle(scs)
        k = round(len(scs) * a.dev_ratio)
        dev += scs[:k]
        test += scs[k:]
    test += mixed

    out = {"seed": a.seed, "dev_ratio": a.dev_ratio, "dev": sorted(dev), "test": sorted(test)}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    w = lambda ids: sum(1 for s in ids if _bool(first[s]["is_violation"]))  # noqa: E731
    print(f"dev {len(dev)} シナリオ（警告すべき {w(dev)}）／ test {len(test)} シナリオ（警告すべき {w(test)}）→ {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`evals/promptfoo/load_dataset.py` に、分割のどちらかだけを書き出す引数を足す（`main` の中）：

```python
    ap.add_argument("--split-file", type=Path, help="make_split.py が書いた JSON")
    ap.add_argument("--split", choices=["dev", "test"], help="--split-file のどちらを使うか")
    a = ap.parse_args()
    article_ids = {x["id"] for x in json.loads(ARTICLES.read_text(encoding="utf-8"))["articles"]}
    rows = read_rows(a.dataset)
    if a.split_file and a.split:
        keep = set(json.loads(a.split_file.read_text(encoding="utf-8"))[a.split])
        rows = [r for r in rows if r["scenario_id"] in keep]
    if a.limit:
        rows = rows[: a.limit]
```

`evals/promptfoo/summarize.py` にも、結果を分割で絞って集計する引数を足す（全件で 1 回測れば、dev と test の集計は評価をやり直さずに出せる）：

```python
    ap.add_argument("--split-file", type=Path, help="make_split.py が書いた JSON")
    ap.add_argument("--split", choices=["dev", "test"], help="--split-file のどちらで集計するか")
    a = ap.parse_args()
    runs = load_runs(a.results)
    if a.split_file and a.split:
        keep = set(json.loads(a.split_file.read_text(encoding="utf-8"))[a.split])
        runs = [{k: v for k, v in r.items() if v["vars"]["scenario_id"] in keep} for r in runs]
```

分割を作る：

```bash
cd evals/promptfoo
python make_split.py datasets/eval_posts.csv
python load_dataset.py datasets/eval_posts.csv --split-file splits/pjt04_split.json --split dev --output datasets/testcases_dev.yaml
python load_dataset.py datasets/eval_posts.csv --split-file splits/pjt04_split.json --split test --output datasets/testcases_test.yaml
python load_dataset.py datasets/eval_posts.csv     # 全件（testcases.yaml）も作り直しておく
cd ../..
```

✅ 確認：

- dev は 58 × 0.6 ≈ 35 シナリオ前後（× 6 言語 ≈ 210 件）、test は残り＋言語混在 6 件
- dev と test の件数の合計が 354
- `git status` に `splits/pjt04_split.json` が出る（これは commit する）。`datasets/` は出ない

💾 コミット：`feat(evals): シナリオ単位の dev/test 分割（ID の一覧）と、分割で絞る引数を追加`

### 5. スモーク評価（5 件）

```bash
cd evals/promptfoo
export PROMPTFOO_PYTHON=$PWD/../../.venv/bin/python
export PROMPTFOO_DISABLE_TELEMETRY=1

npx promptfoo eval --filter-providers bedrock-lite --filter-first-n 5 --no-cache -o output/smoke_lite.json
python summarize.py output/smoke_lite.json
```

✅ 確認：5 件とも「判定の失敗」0。費用・時間の行に 0 より大きい値が出ている。失敗が出たら `npx promptfoo view` で 1 件ずつのエラーを見る（ガイド 02 の手順 11 の表）。

### 6. ベースラインを測る（Micro・Lite × 354 件 × 3 回）

```bash
npx promptfoo eval --filter-providers bedrock-micro --repeat 3 --no-cache -j 4 -o output/baseline_micro.json
npx promptfoo eval --filter-providers bedrock-lite  --repeat 3 --no-cache -j 4 -o output/baseline_lite.json
```

- 1 本あたり 1,062 回の判定（354 × 3）。1 回 1〜2 秒・並列 4 で 10〜20 分が目安
- スロットリングが続く（失敗が増える・遅い）なら `-j 2` に下げる。ガイド 02 で調べた上限（1 分あたりの要求数）÷ 2 回（1 投稿 2 段）を超えない並列数にする
- 途中で止まったら、同じコマンドをやり直す（`--no-cache` なので最初から）

### 7. 集計して記録する

```bash
D=../../docs/purchase_order/experiments
for M in micro lite; do
  python summarize.py output/baseline_$M.json --csv $D/baseline_${M}_all.csv  > $D/baseline_${M}_all.md
  python summarize.py output/baseline_$M.json --split-file splits/pjt04_split.json --split dev  > $D/baseline_${M}_dev.md
  python summarize.py output/baseline_$M.json --split-file splits/pjt04_split.json --split test > $D/baseline_${M}_test.md
done
cd ../..
```

`summarize.py` の出力は件数・率・ID・条文 ID だけで、投稿の本文を含まない。**念のため、commit 前に本文が混ざっていないか確かめる**：

```bash
grep -l "http\|@" docs/purchase_order/experiments/baseline_* || echo "本文らしき文字列なし"
```

[実験の記録](../experiments/README.md) に `EXP-000 ベースライン` の行を足す（モデル・温度・プロンプトのコミット・データ・回数・主な数値）。

💾 コミット：`docs: Bedrock 版ベースライン（Nova Micro / Lite × 354 件 × 3 回）の集計を記録`

### 8. 主なモデルを決める

次の順で比べ、**以降の改善で使うモデルを 1 つ**決める。決めた理由を実験の記録に書く。

1. 全体の取りこぼし（少ない方）
2. 言語別の再現率の最小値（高い方）
3. 1 投稿あたりの費用と p95（安い・速い方）

例：「Lite は Micro より取りこぼしが 8 件少なく、費用は 1 投稿 $0.000x 高いだけなので Lite を主にする。Micro は費用削減の候補（2 段判定のふるい分け）として残す」

もう一方のモデルの結果も、説明資料の「ベースラインの作り方」に参考として載せる。

### 9. OpenAI 版との差を表にする

運営が測った OpenAI 版（新方式・経路 B）の値（発注書 4 章）と並べる。

| 方式 | 取りこぼし | 誤検知 | 再現率 | 適合率 | 1 投稿あたりの費用 |
|---|--:|--:|--:|--:|--:|
| 新方式（OpenAI 版・運営の計測） | 9 | 48 | 0.941 | 0.750 | $0.000475 |
| Bedrock 版（Nova Lite・3 回の平均） | | | | | |
| Bedrock 版（Nova Micro・3 回の平均） | | | | | |

- 運営の値は**全体の値だけ**で、言語別の内訳は提供されていない。言語別の差を示すには、(a) 自費で OpenAI の判定を同じ条件で測る（`--filter-providers decisions`。キーは `OPENAI_API_KEY`）、(b) 全体だけを比べ、言語別はベースラインの中での差として示す、のどちらか。どちらにしたかと理由を書く
- 運営の値は 1 回の計測。こちらは 3 回の平均と範囲で示す
- この表を `experiments/baseline_vs_openai.md` に置き、説明資料の 2 章に転記する

💾 コミット：`docs: OpenAI 版と Bedrock 版ベースラインの比較表を追加`

### 10. PR

```bash
git push -u origin feat/eval-bedrock
gh pr create --base develop --title "feat(evals): Bedrock 版ベースラインの計測" --body "ガイド 03"
```

---

## ⚠️ つまずきやすい点

- `--filter-providers` の値は正規表現。`bedrock` だけだと Micro と Lite の両方に当たる
- `--repeat 3` の結果は 1 つのファイルに 3 回分入る。`summarize.py` は自動で回ごとに分けて「判定の安定性」を出す
- `output/` の JSON には**投稿の本文が入る**。commit しない（`.gitignore` 済み）。`npx promptfoo view` の共有機能（`--share`）も使わない
- 1 件で率が約 0.04 動く（全件では言語ごとに警告すべき投稿は 25 件ほど）。**test だけで見ると 1 言語 10 件ほどで、1 件で約 0.1 動く**。率と件数を並べて記録し、言語別の比較は全件の値を主に使う（test は「dev に合わせすぎていないか」の確認に使う）
- dev / test の分割は**この時点で固定**する。改善の結果を見てから分け直すと、分けた意味がなくなる

## 完了の条件

- [ ] ハーネスが `bedrock` 方式で動き、費用と時間が記録される
- [ ] `splits/pjt04_split.json` を commit した
- [ ] Micro・Lite の 354 件 × 3 回の集計（全件・dev・test）を `experiments/` に記録した
- [ ] 主なモデルを決め、理由を実験の記録に書いた
- [ ] OpenAI 版との比較表を作った
