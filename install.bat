@echo off
REM ============================================================================
REM install.bat - instalacao do Sistema de Chamada Inteligente de Alunos
REM Uso: clique duas vezes neste arquivo, ou rode "install.bat" no cmd/PowerShell
REM ============================================================================

echo ==^> Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python 3.13+ ^(python.org^) antes de continuar.
    pause
    exit /b 1
)

echo ==^> Criando ambiente virtual (.venv)...
python -m venv .venv

echo ==^> Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo ==^> Instalando dependencias (requirements.txt)...
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist .env (
    echo ==^> Criando arquivo .env a partir de .env.example...
    copy .env.example .env
)

echo.
echo Instalacao concluida.
echo Para iniciar o sistema, rode: run.bat
pause
