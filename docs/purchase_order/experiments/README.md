# 実験の記録

ベースラインと改善の試行を、**効かなかった案も含めて**ここに残します。説明資料の「なぜ効いたのか（考察）」「試したが採用しなかった案」の材料になります。

## 置いてよいもの・いけないもの

| 置いてよい | 置いてはいけない |
|---|---|
| `summarize.py` の出力（件数・率・ID・条文 ID）、`--csv` の言語別の表 | promptfoo の結果の JSON（`evals/promptfoo/output/`。投稿の本文が入る） |
| 試した案の説明、プロンプトのコミット、モデル・設定 | 提供データ・追加データの投稿の本文 |
| 環境の情報（リージョン・モデル ID・単価・上限） | アカウント ID・API キー・認証情報 |

## ファイルの名前

| ファイル | 内容 |
|---|---|
| `env.md` | 評価・実行の環境（ガイド 02 の手順 4） |
| `baseline_<model>_<all/dev/test>.md`・`.csv` | ベースラインの集計（ガイド 03） |
| `baseline_vs_openai.md` | OpenAI 版との比較（ガイド 03） |
| `analysis_baseline.md` | ベースラインの誤り分析（ガイド 04） |
| `exp<番号>_<短い名前>_<dev/test/all>.md` | 改善の試行の集計（ガイド 05） |
| `exp<番号>_<短い名前>_<dev/test/all>.csv` | 同じ試行の言語別の表（`run_trial.sh` が書く） |
| `metrics_<名前>_<dev/test/all>.json` | 比べるための値（3 回の平均。本文を含まない。`compare_runs.py --save-metrics`）。`metrics_baseline_lite_*`・`metrics_current_dev`・`metrics_final_all`・`metrics_ci_smoke`（ガイド 05・07） |
| `final_vs_baseline_<test/all>.md` | 採用した改善とベースラインの比較（ガイド 05 の手順 9） |
| `injection_<before/after/compare>.md` | 注入の評価データでの対策の前後（ガイド 06） |
| `custom_<baseline/final/compare>.md`・`.csv` | 自作データでの最後の確認（ガイド 08） |
| `deploy_outputs.txt` | 講座の AWS へのデプロイの出力（アカウント ID は伏せる。ガイド 09） |

## 試行の一覧

1 行 1 試行。**dev の数値で判断し、test は採用を決めた案だけで見る**（ガイド 05）。

| ID | 日付 | 案 | 狙った誤り | モデル | プロンプトのコミット | データ・回数 | 取りこぼし | 誤検知 | 再現率 / 適合率 | 言語差（再現率の最大−最小） | 費用 / 投稿 | 判断 |
|---|---|---|---|---|---|---|--:|--:|--:|--:|--:|---|
| EXP-000 | | ベースライン（経路 B をそのまま） | — | | | 全件 × 3 | | | | | | 基準 |

## 試行ごとのメモ

### EXP-000 ベースライン

- 設定：モデル（ ）、温度 0、最大トークン 512、プロンプトのコミット（ ）
- 結果のファイル：`baseline_<model>_all.md`
- 気づいたこと：
