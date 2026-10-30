#!/usr/bin/env bash
# Mac / Linux: na primeira vez instala tudo, depois só abre o Cifrador.
set -e
cd "$(dirname "$0")"

# precisa do ffmpeg pra ler qualquer formato de áudio
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg não encontrado. No Mac: brew install ffmpeg"
  exit 1
fi

# só considera instalado quando a instalação inteira terminou sem erro
if [ ! -f ".venv/instalado.ok" ]; then
  echo "Instalando (uns minutos)..."
  rm -rf .venv
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
  touch .venv/instalado.ok
fi

# puxa a versão mais nova do GitHub (se tiver internet)
.venv/bin/python atualizar.py
.venv/bin/python -m cifrador "$@"
