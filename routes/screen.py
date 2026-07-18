"""
routes/screen.py
=================
Tela Screen (Módulo 6): o "painel de TV" que exibe a foto e o nome do
aluno chamado, com narração por voz (Web Speech API no navegador).

É uma tela somente leitura: toda a atualização acontece via Socket.IO
(evento 'aluno_chamado', o mesmo emitido pelo Kiosk no Módulo 5).
"""

from flask import Blueprint, render_template, flash, redirect, url_for

from database.services import listar_historico, listar_ultimas_chamadas_sala, obter_sala
from routes.auth import login_required

screen_bp = Blueprint("screen", __name__, url_prefix="/screen")


@screen_bp.route("/")
@login_required
def tela():
    """
    Painel de TV "geral", em tela cheia — mostra a chamada de QUALQUER
    sala. Útil para uma recepção única (Módulo 6) ou para
    acompanhamento administrativo. Quando o prédio tem uma TV dedicada
    por sala de aula (Módulo 13), use `/screen/<sala_id>` em vez desta,
    para que a TV só exiba/narre as chamadas da sua própria sala.

    Também carrega os 3 últimos chamados (de qualquer sala) para a
    barra lateral (Módulo 12), que continua se atualizando ao vivo via
    Socket.IO (evento 'aluno_chamado') enquanto a tela ficar aberta.
    """
    ultimas = listar_historico(limite=3)
    return render_template("screen.html", sala=None, ultimas=ultimas)


@screen_bp.route("/<int:sala_id>")
@login_required
def tela_sala(sala_id):
    """
    Painel de TV dedicado a UMA sala de aula (Módulo 13): cada uma das
    TVs interativas instaladas nas salas (matemática, ciências,
    robótica etc.) abre esta URL. O Kiosk da portaria continua
    transmitindo toda chamada para todas as telas conectadas (mesmo
    padrão de broadcast do resto do sistema), mas o próprio
    `static/js/screen.js` descarta (não exibe, não narra) qualquer
    chamada cujo `sala_nome` não seja o desta TV — o mesmo padrão de
    filtragem já usado no Kiosk para a lista "Últimos chamados"
    (Módulo 11). Assim nenhuma sala de aula vê/ouve a chamada de outra.
    """
    sala = obter_sala(sala_id)
    if not sala:
        flash("Sala não encontrada.", "erro")
        return redirect(url_for("screen.tela"))

    ultimas = listar_ultimas_chamadas_sala(sala["nome"], limite=3)
    return render_template("screen.html", sala=sala, ultimas=ultimas)
