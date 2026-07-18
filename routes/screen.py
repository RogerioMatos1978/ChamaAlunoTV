"""
routes/screen.py
=================
Tela Screen (Módulo 6): o "painel de TV" que exibe a foto e o nome do
aluno chamado, com narração por voz (Web Speech API no navegador).

É uma tela somente leitura: toda a atualização acontece via Socket.IO
(evento 'aluno_chamado', o mesmo emitido pelo Kiosk no Módulo 5).
"""

from flask import Blueprint, render_template

from routes.auth import login_required

screen_bp = Blueprint("screen", __name__, url_prefix="/screen")


@screen_bp.route("/")
@login_required
def tela():
    """
    Painel de TV em tela cheia. Fica aberto continuamente em um
    computador/TV conectado à rede local, exibindo cada chamada em
    tempo real conforme os operadores clicam em "CHAMAR" no Kiosk.
    """
    return render_template("screen.html")
