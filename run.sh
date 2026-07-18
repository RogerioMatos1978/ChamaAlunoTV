#!/usr/bin/env bash
###############################################################################
# run.sh — inicia o sistema em modo desenvolvimento (Linux/macOS)
# Para produção, veja o README.md (seção "Nginx + Gunicorn").
###############################################################################
set -e

if [ ! -d .venv ]; then
    echo "Ambiente virtual não encontrado. Rode ./install.sh primeiro."
    exit 1
fi

source .venv/bin/activate
python app.py
