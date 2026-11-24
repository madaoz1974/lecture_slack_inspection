# 説明資料（スライド）

最終課題の説明資料を、1 つの Markdown 原稿から **編集できる PPTX** と **PDF**（提出用）の 2 形式で出力します。

| ファイル | 内容 |
|---|---|
| `report.md` | 原稿（唯一の正本）。発注書 7 章の必須項目 ①〜⑥ に沿った骨組み。`（記入）`・`—` を埋めていく |
| `build.sh` | ビルド。`./build.sh`（両方）／`./build.sh pdf`／`./build.sh pptx` |
| `tools/md2pptx.py` | 原稿 → 編集できる PPTX（python-pptx でテキストボックス・表を直接組み立てる） |
| `tools/requirements.txt` | `md2pptx.py` の依存（`build.sh` が `.venv/` に自動で入れる） |
| `.marprc.yml` | Marp CLI の設定（2 段組みの HTML を有効にする） |
| `assets/` | スクリーンショット・図を置く場所 |
| `dist/` | 出力先（`report.pdf`・`report.pptx`。コミットしない） |

## 必要なもの

- Node.js 18 以上（`npx` で Marp CLI を取得する）
- Google Chrome / Microsoft Edge / Chromium のいずれか（Marp が PDF の描画に使う）
- Python 3.10 以上（PPTX の生成）

## ビルド

```bash
cd docs/purchase_order/slides
./build.sh          # dist/report.pptx と dist/report.pdf
./build.sh pdf      # PDF のみ（提出用）
./build.sh pptx     # 編集できる PPTX のみ
```

内容が下端からはみ出すスライドは、PPTX では文字と画像を自動で縮め（最小 60%）、それでも収まらないときは警告を出します。PDF は縮めないので、警告が出たら原稿を減らしてください。

## 書き方

- `---` でページを区切る。各ページの見出しは `## `
- 表紙は `<!-- _class: title -->`、章の扉は `<!-- _class: section -->`
- 2 段組みは `<div class="columns">` の中に `<div>` を 2 つ置く（`<div>` の直後と `</div>` の直前に空行を入れる）
- `**強調**` は朱色、`` `コード` `` は等幅の紺色、`> ` は薄い灰色の囲み
- 画像は `assets/` に置き、`![w:900](assets/xxx.png)` の形で貼る（`w:` は 1280 × 720 を基準とした px）
- `<!-- ... -->` は発表者ノート（記入ガイド）。PDF には出ず、PPTX ではノート欄に入る

PPTX の生成では、上の記法だけを扱います。Marp のほかの記法（背景画像 `![bg]`、数式など）は PDF にしか反映されません。

## 編集の流れ

1. **原稿（`report.md`）を直して再ビルドするのが基本**です。PDF と PPTX の内容がずれません
2. PPTX を PowerPoint で直接直した場合、その変更は原稿に戻りません。その PPTX を最終版にするなら、PDF も PowerPoint から書き出してください（「ファイル → エクスポート → PDF」）

## プレビュー

VS Code の拡張機能「Marp for VS Code」で `report.md` を開くと、プレビューで確認できます。2 段組みを表示するには、設定で HTML を有効にします（`markdown.marp.html` を `all`）。

## フォント

- PDF：ヒラギノ角ゴシック（macOS）／游ゴシック（Windows）／Noto Sans JP の順に使う
- PPTX：游ゴシック（Yu Gothic）を指定。Windows と Microsoft 365 の PowerPoint には標準で入っています。LibreOffice・Keynote で開くとほかのフォントに置き換わり、折り返しの位置が変わることがあります
