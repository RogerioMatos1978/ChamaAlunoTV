"""
routes/screen.py
=================
Tela Screen (Módulo 6, revista no Módulo 14): o "painel de TV" que
exibe a foto e o nome do aluno chamado, com narração por voz (Web
Speech API no navegador).

Desde o Módulo 14, TODO o blueprint é público (sem login) — é pensado
para abrir sozinho em qualquer TV interativa da rede, sem ninguém
precisar digitar usuário/senha ali. A tela é somente leitura: toda a
atualização acontece via Socket.IO (evento 'aluno_chamado', o mesmo
emitido pelo Kiosk).

Três modos, todos servidos pelo mesmo template `screen.html`:
    - `/screen/`            -> seleção de sala (o professor escolhe a
                                sala desta TV; fica salvo no navegador
                                da própria TV via localStorage)
    - `/screen/<sala_id>`   -> painel dedicado a UMA sala — só exibe/
                                narra chamadas dessa sala (filtro no
                                próprio navegador, em screen.js)
    - `/screen/geral`       -> painel "geral", mostra a chamada de
                                qualquer sala (comportamento antigo,
                                para quem usa uma única TV central)
"""

from flask import Blueprint, render_template, flash, redirect, url_for

from database.services import listar_historico, listar_ultimas_chamadas_sala, obter_sala, listar_salas

screen_bp = Blueprint("screen", __name__, url_prefix="/screen")


@screen_bp.route("/")
def tela():
    """
    Ponto de entrada público do painel de TV. Sem login: basta o
    sistema estar no ar. Mostra a grade de salas ativas para o
    professor escolher a sala desta TV — o próprio `screen.js` verifica
    primeiro se já existe uma escolha salva no navegador (localStorage)
    e, se houver, pula direto para `/screen/<sala_id>` sem mostrar essa
    tela de novo.
    """
    salas = listar_salas(apenas_ativas=True)
    return render_template("screen.html", modo="selecionar", sala=None, salas=salas, ultimas=[])


@screen_bp.route("/geral")
def tela_geral():
    """
    Painel de TV "geral" (comportamento dos Módulos 6/11/12): mostra a
    chamada de QUALQUER sala, sem se prender a uma específica. Útil
    para quem tem uma única TV central (ex.: só a recepção) em vez de
    uma TV por sala de aula. Também sem login.
    """
    ultimas = listar_historico(limite=3)
    return render_template("screen.html", modo="geral", sala=None, salas=[], ultimas=ultimas)


@screen_bp.route("/<int:sala_id>")
def tela_sala(sala_id):
    """
    Painel de TV dedicado a UMA sala de aula (Módulo 13/14): cada uma
    das TVs interativas instaladas nas salas (matemática, ciências,
    robótica etc.) abre esta URL — diretamente, por QR Code/link do
    Admin, ou escolhendo a sala na tela de seleção em `/screen/`. Sem
    login.

    O Kiosk continua transmitindo toda chamada para todas as telas
    conectadas (mesmo padrão de broadcast do resto do sistema), mas o
    próprio `static/js/screen.js` descarta (não exibe, não narra)
    qualquer chamada cujo `sala_nome` não seja o desta TV — mesmo
    padrão de filtragem já usado no Kiosk para a lista "Últimos
    chamados". Assim nenhuma sala de aula vê/ouve a chamada de outra.
    """
    sala = obter_sala(sala_id)
    if not sala:
        flash("Sala não encontrada.", "erro")
        return redirect(url_for("screen.tela"))

    ultimas = listar_ultimas_chamadas_sala(sala["nome"], limite=3)
    return render_template("screen.html", modo="sala", sala=sala, salas=[], ultimas=ultimas)
