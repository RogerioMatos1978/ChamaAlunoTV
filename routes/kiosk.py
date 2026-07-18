"""
routes/kiosk.py
================
Tela Kiosk (Módulo 5): onde o operador seleciona uma sala e chama os
alunos. A remoção da fila, o registro de histórico e a sincronização
das telas acontecem via Socket.IO (veja database/socket_events.py) —
as rotas HTTP aqui servem apenas para carregar a página inicialmente.

Acessível a qualquer usuário logado (administrador, supervisor ou
operador): é a ferramenta principal do dia a dia da secretaria.
"""

from flask import Blueprint, render_template, flash, redirect, url_for

from database.services import listar_salas, obter_sala, listar_alunos, listar_ultimas_chamadas_sala
from routes.auth import login_required

kiosk_bp = Blueprint("kiosk", __name__, url_prefix="/kiosk")


@kiosk_bp.before_request
@login_required
def exigir_login():
    """Qualquer perfil logado pode operar o Kiosk."""
    pass


@kiosk_bp.route("/")
def selecionar_sala():
    """Tela inicial do Kiosk: escolha da sala a ser atendida."""
    salas = listar_salas(apenas_ativas=True)
    return render_template("kiosk.html", modo="selecionar", salas=salas)


@kiosk_bp.route("/<int:sala_id>")
def fila_sala(sala_id):
    """Mostra a fila de alunos aguardando na sala selecionada."""
    sala = obter_sala(sala_id)
    if not sala or not sala["ativa"]:
        flash("Sala não encontrada ou inativa.", "erro")
        return redirect(url_for("kiosk.selecionar_sala"))

    alunos = listar_alunos(sala_id=sala_id, status="aguardando", ordenar_por="fila")
    recentes = listar_ultimas_chamadas_sala(sala["nome"], limite=6)
    return render_template("kiosk.html", modo="fila", sala=sala, alunos=alunos, recentes=recentes)
