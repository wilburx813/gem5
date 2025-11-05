#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PDF_OUT="gem5_intro.pdf"

download_tectonic() {
  echo "[build] Downloading tectonic (portable LaTeX engine)..."
  url_candidates=(
    # Known release URLs (update if needed)
    "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz"
    "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz"
  )
  for url in "${url_candidates[@]}"; do
    echo "[build] Trying $url"
    if curl -fsSL "$url" -o tectonic.tar.gz; then
      tar -xzf tectonic.tar.gz || tar -xJf tectonic.tar.gz || true
      # Find tectonic binary in extracted content
      binpath=$(find . -type f -name tectonic -perm -u+x | head -n 1 || true)
      if [[ -n "${binpath}" ]]; then
        if [[ "$binpath" != "./tectonic" ]]; then
          cp "$binpath" ./tectonic
        fi
        chmod +x ./tectonic
        rm -f tectonic.tar.gz || true
        echo "[build] Tectonic ready: $(./tectonic --version)"
        return 0
      fi
    fi
  done
  echo "[build] Failed to download/extract tectonic." >&2
  return 1
}

# 1) Ensure tectonic exists locally
if [[ ! -x ./tectonic ]]; then
  download_tectonic
fi

# 2) Ensure matplotlib and generate results plot before PDF build
echo "[build] Ensuring matplotlib is installed..."
python3 -m pip install --user --quiet matplotlib
echo "[build] Generating results plot..."
python3 plot_results.py || true

# 3) Build PDF via tectonic
echo "[build] Compiling PDF with tectonic..."
./tectonic -X compile gem5_intro.tex --keep-logs --keep-intermediates || ./tectonic gem5_intro.tex
if [[ ! -f "$PDF_OUT" ]]; then
  echo "[build] PDF output not found; build may have failed." >&2
  exit 2
fi
echo "[build] PDF generated: $PDF_OUT"

echo "[build] Done. Output: $PDF_OUT"
