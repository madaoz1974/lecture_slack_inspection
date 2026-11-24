#!/usr/bin/env bash
#
# 説明資料（report.md）のビルド
#
#   ./build.sh          # 編集できる PPTX と PDF の両方
#   ./build.sh pdf      # PDF のみ（Marp CLI。提出用）
#   ./build.sh pptx     # 編集できる PPTX のみ（tools/md2pptx.py。python-pptx で直接生成）
#
#   DECK=other.md ./build.sh   # 別の原稿をビルドする
#
set -euo pipefail

SLIDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DECK="${DECK:-report.md}"
NAME="$(basename "${DECK}" .md)"
DIST_DIR="${SLIDE_DIR}/dist"
VENV_DIR="${SLIDE_DIR}/.venv"

MARP=(npx -y @marp-team/marp-cli@4)

# Marp CLI は PDF の描画に Chrome / Edge / Chromium を使う
detect_chrome() {
  if [[ -n "${CHROME_PATH:-}" ]]; then return; fi
  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "$(command -v google-chrome || true)" \
    "$(command -v chromium || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      export CHROME_PATH="${candidate}"
      return
    fi
  done
}

build_pdf() {
  detect_chrome
  mkdir -p "${DIST_DIR}"
  # 発表者ノート（<!-- --> の記入ガイド）は PDF に入れない
  "${MARP[@]}" "${DECK}" --pdf --allow-local-files -o "${DIST_DIR}/${NAME}.pdf"
}

build_pptx() {
  # python-pptx / Pillow は隔離した venv に入れる（システムの Python は汚さない）
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "  venv を作成中: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet -r "${SLIDE_DIR}/tools/requirements.txt"
  fi
  "${VENV_DIR}/bin/python" "${SLIDE_DIR}/tools/md2pptx.py" "${DECK}" -o "${DIST_DIR}/${NAME}.pptx"
}

cd "${SLIDE_DIR}"

case "${1:-all}" in
  pdf) build_pdf ;;
  pptx) build_pptx ;;
  all)
    build_pptx
    build_pdf
    echo "出力: ${DIST_DIR}"
    ;;
  *)
    echo "usage: $0 [all|pdf|pptx]" >&2
    exit 1
    ;;
esac
