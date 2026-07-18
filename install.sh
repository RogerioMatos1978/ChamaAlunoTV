#!/usr/bin/env bash
###############################################################################
# install.sh — instalação do Sistema de Chamada Inteligente de Alunos
# Uso: chmod +x install.sh && ./install.sh
###############################################################################
set -e

echo "==> Verificando Python 3..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 não encontrado. Instale o Python 3.13+ antes de continuar."; exit 1; }

echo "==> Criando ambiente virtual (.venv)..."
python3 -m venv .venv

echo "==> Ativando ambiente virtual..."
source .venv/bin/activate

echo "==> Instalando dependências (requirements.txt)..."
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "==> Criando arquivo .env a partir de .env.example..."
    cp .env.example .env
fi

echo ""
echo "Instalação concluída."
echo "Para iniciar o sistema, rode: ./run.sh"
