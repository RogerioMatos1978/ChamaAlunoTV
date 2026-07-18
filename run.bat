@echo off
REM ============================================================================
REM run.bat - inicia o sistema em modo desenvolvimento (Windows)
REM Para producao, veja o README.md (secao "Windows Server").
REM ============================================================================

if not exist .venv (
    echo Ambiente virtual nao encontrado. Rode install.bat primeiro.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python app.py
pause
