@echo off
setlocal enabledelayedexpansion
REM ============================================================================
REM run_rede.bat - inicia o sistema em modo desenvolvimento, pronto para ser
REM acessado por outros dispositivos da rede local (Kiosk da portaria, TVs de
REM cada sala, tablets, outros computadores).
REM
REM O servidor (app.py / socketio.run) ja escuta em host="0.0.0.0" por padrao,
REM ou seja, ja aceita conexoes de outros dispositivos da rede sem precisar
REM alterar nada no codigo. Este script so detecta e mostra o IP desta
REM maquina automaticamente, para nao precisar rodar "ipconfig" na mao.
REM
REM Para producao (servico do Windows sempre ligado), veja o README.md,
REM secao "Windows Server".
REM ============================================================================

if not exist .venv (
    echo Ambiente virtual nao encontrado. Rode install.bat primeiro.
    pause
    exit /b 1
)

REM --- Detecta o IPv4 desta maquina (ignora enderecos APIPA 169.254.x.x) ---
set "IP_LOCAL="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4"') do (
    set "CANDIDATO=%%A"
    set "CANDIDATO=!CANDIDATO: =!"
    echo !CANDIDATO! | findstr /B /C:"169.254." >nul
    if errorlevel 1 (
        if not defined IP_LOCAL set "IP_LOCAL=!CANDIDATO!"
    )
)

if not defined IP_LOCAL (
    echo.
    echo AVISO: nao foi possivel detectar o IP desta maquina automaticamente.
    echo Rode "ipconfig" manualmente e procure por "Endereco IPv4".
    echo.
    set "IP_LOCAL=SEU-IP-AQUI"
)

set "PORTA=5000"

echo.
echo ============================================================================
echo  Sistema de Chamada Inteligente de Alunos - modo rede local
echo ============================================================================
echo.
echo  Endereco desta maquina (servidor): !IP_LOCAL!
echo.
echo  Acesse a partir de outros dispositivos na MESMA rede (Wi-Fi/LAN):
echo.
echo    Pagina inicial (login) ......... http://!IP_LOCAL!:%PORTA%/
echo    Kiosk da portaria (sem login) .. http://!IP_LOCAL!:%PORTA%/kiosk
echo    Painel de TV de uma sala ....... http://!IP_LOCAL!:%PORTA%/screen
echo    Painel de TV geral ............. http://!IP_LOCAL!:%PORTA%/screen/geral
echo    Painel administrativo .......... http://!IP_LOCAL!:%PORTA%/admin
echo.
echo  Nesta propria maquina (servidor), tambem funciona http://localhost:%PORTA%/
echo.
echo  Se algum dispositivo nao conseguir acessar:
echo    1. Confirme que esta no mesmo Wi-Fi/rede da maquina servidora.
echo    2. Libere a porta %PORTA% no Firewall do Windows desta maquina
echo       (Firewall do Windows Defender -^> Regras de Entrada -^> Nova Regra
echo       -^> Porta -^> TCP -^> %PORTA%).
echo    3. Se este computador tiver mais de uma rede ativa (ex.: VPN,
echo       VirtualBox, hotspot), o IP detectado acima pode nao ser o da rede
echo       correta - confira com "ipconfig" e use o IP da rede da instituicao.
echo ============================================================================
echo.

call .venv\Scripts\activate.bat
python app.py
pause
