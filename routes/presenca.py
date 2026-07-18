"""
routes/presenca.py
===================
Tela de Presença (Módulo 7): lista pública/operacional de todos os
alunos que ainda estão aguardando atendimento, com busca instantânea,
filtro por sala e contagem por sala.

Diferente do Kiosk, esta tela é somente leitura — não tem botão de
chamar. Serve para que o próprio aluno/família acompanhe a fila (ex.:
em um monitor na sala de espera) ou para a coordenação ter uma visão
geral rápida.
"""

from flask import Blueprint, render_template, request

from database.services import listar_alunos, listar_salas
from routes.auth import login_required

presenca_bp = Blueprint("presenca", __name__, url_prefix="/presenca")


@presenca_bp.route("/")
@login_required
def lista():
    """
    Lista os alunos aguardando. A busca e o filtro por sala também
    funcionam no servidor (para o carregamento inicial da página);
    depois disso, a busca instantânea é refeita no navegador via
    JavaScript, sem precisar recarregar.
    """
    sala_id = request.args.get("sala_id", type=int)
    busca = request.args.get("busca", "").strip() or None

    alunos = listar_alunos(sala_id=sala_id, status="aguardando", busca=busca, ordenar_por="fila")
    salas = listar_salas(apenas_ativas=True)

    return render_template(
        "presenca.html", alunos=alunos, salas=salas, sala_id=sala_id, busca=busca or "",
    )
