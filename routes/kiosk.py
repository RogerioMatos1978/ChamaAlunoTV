"""
routes/kiosk.py
================
Tela Kiosk (Módulo 5, aberta ao público no Módulo 14): onde o
responsável pela recepção seleciona uma sala e chama os alunos. A
remoção da fila, o registro de histórico e a sincronização das telas
acontecem via Socket.IO (veja database/socket_events.py) — as rotas
HTTP aqui servem apenas para carregar a página inicialmente.

`selecionar_sala` e `fila_sala` (o Kiosk de chamada em si) são
PÚBLICAS DE PROPÓSITO — sem exigir login — pois é o terminal fixo da
portaria (ex.: TV interativa de 86"), pensado para abrir sozinho, sem
ninguém precisar digitar usuário/senha ali. Já as rotas de "gestão"
(ativo/presença/foto do usuário padrão, mais abaixo) continuam
exigindo login — são telas de manutenção de dados, não o terminal
público — por isso cada uma delas tem `@login_required` individual em
vez de um `before_request` do blueprint inteiro.
"""

from flask import Blueprint, render_template, flash, redirect, url_for, request, session

from database.services import (
    listar_salas, obter_sala, listar_alunos, obter_aluno, listar_ultimas_chamadas_sala,
    atualizar_status_ativo_aluno, marcar_presenca, extensao_permitida,
    salvar_foto_aluno, salvar_foto_sala, obter_ano_letivo_atual_id, registrar_log,
    get_configuracao,
)
from routes.auth import login_required

kiosk_bp = Blueprint("kiosk", __name__, url_prefix="/kiosk")


def _notificar_dados_atualizados(tipo: str):
    """Mesmo mecanismo usado em routes/admin.py (Módulo 11) — avisa outras telas."""
    from app import socketio
    socketio.emit("dados_atualizados", {"tipo": tipo})


def _kiosk_simplificado() -> bool:
    """
    Módulo 13: quando ligado (padrão), o Kiosk mostra apenas o botão
    "Trocar sala" no cabeçalho — pensado para o terminal fixo da
    portaria (TV interativa de 86"), onde o responsável pela recepção
    só precisa selecionar a sala e chamar o aluno, sem acesso aos links
    de administração/gestão/presença/painel de TV/logout. Pode ser
    desligado em Configurações administrativas, caso o mesmo Kiosk
    também seja usado por um operador que precise desses atalhos.
    """
    return get_configuracao("kiosk_modo_simplificado", "1") == "1"


@kiosk_bp.route("/")
def selecionar_sala():
    """Tela inicial do Kiosk: escolha da sala a ser atendida."""
    salas = listar_salas(apenas_ativas=True)
    return render_template(
        "kiosk.html", modo="selecionar", salas=salas, kiosk_simplificado=_kiosk_simplificado(),
    )


@kiosk_bp.route("/<int:sala_id>")
def fila_sala(sala_id):
    """Mostra a fila de alunos aguardando na sala selecionada."""
    sala = obter_sala(sala_id)
    if not sala or not sala["ativa"]:
        flash("Sala não encontrada ou inativa.", "erro")
        return redirect(url_for("kiosk.selecionar_sala"))

    # A fila só mostra alunos ativos (não transferidos) e que não foram
    # explicitamente marcados como faltantes hoje (Módulo 12).
    alunos = listar_alunos(
        sala_id=sala_id, status="aguardando", ordenar_por="fila",
        ativo=1, excluir_faltantes_hoje=True,
    )
    recentes = listar_ultimas_chamadas_sala(sala["nome"], limite=6)
    return render_template(
        "kiosk.html", modo="fila", sala=sala, alunos=alunos, recentes=recentes,
        kiosk_simplificado=_kiosk_simplificado(),
    )


# ---------------------------------------------------------------------------
# Gestão do dia a dia pelo usuário padrão (operador) — Módulo 12
# ---------------------------------------------------------------------------
# O cadastro completo (dados cadastrais, importação em massa via CSV) fica
# restrito ao Admin/Supervisor em routes/admin.py. Aqui ficam apenas as
# três coisas que a especificação autoriza o usuário padrão a alterar no
# dia a dia: se o aluno está ativo/inativo, se ele está presente/faltante
# hoje, a foto do aluno e a foto da sala.
@kiosk_bp.route("/gestao/alunos")
@login_required
def gestao_alunos():
    """Lista de alunos para o usuário padrão gerenciar ativo/presença/foto."""
    sala_id = request.args.get("sala_id", type=int)
    busca = request.args.get("busca", "").strip() or None

    alunos = listar_alunos(sala_id=sala_id, busca=busca, ordenar_por="nome")
    salas = listar_salas()
    return render_template(
        "kiosk_gestao_alunos.html", alunos=alunos, salas=salas,
        sala_id=sala_id, busca=busca or "",
    )


@kiosk_bp.route("/gestao/alunos/<int:aluno_id>/ativo", methods=["POST"])
@login_required
def gestao_aluno_ativo(aluno_id):
    """Alterna um aluno entre ativo/inativo (ex.: transferido para outra escola)."""
    aluno = obter_aluno(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect(url_for("kiosk.gestao_alunos"))

    novo_status = not bool(aluno["ativo"])
    atualizar_status_ativo_aluno(aluno_id, novo_status)
    registrar_log(
        tipo="alteracao",
        mensagem=f"Aluno \"{aluno['nome']}\" marcado como {'ativo' if novo_status else 'inativo'} (id={aluno_id}).",
        usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
    )
    _notificar_dados_atualizados("alunos")
    flash(f"\"{aluno['nome']}\" agora está {'ativo' if novo_status else 'inativo'}.", "sucesso")
    return redirect(request.referrer or url_for("kiosk.gestao_alunos"))


@kiosk_bp.route("/gestao/alunos/<int:aluno_id>/presenca", methods=["POST"])
@login_required
def gestao_aluno_presenca(aluno_id):
    """Marca a presença/falta de hoje de um aluno."""
    aluno = obter_aluno(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect(url_for("kiosk.gestao_alunos"))

    status = request.form.get("status")
    if status not in ("presente", "faltante"):
        flash("Status de presença inválido.", "erro")
        return redirect(request.referrer or url_for("kiosk.gestao_alunos"))

    marcar_presenca(
        aluno_id, status=status, ano_letivo_id=aluno.get("ano_letivo_id") or obter_ano_letivo_atual_id(),
        registrado_por=session.get("usuario_id"),
    )
    registrar_log(
        tipo="alteracao",
        mensagem=f"Presença de hoje de \"{aluno['nome']}\" marcada como {status} (id={aluno_id}).",
        usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
    )
    _notificar_dados_atualizados("alunos")
    flash(f"\"{aluno['nome']}\" marcado(a) como {status} hoje.", "sucesso")
    return redirect(request.referrer or url_for("kiosk.gestao_alunos"))


@kiosk_bp.route("/gestao/alunos/<int:aluno_id>/foto", methods=["POST"])
@login_required
def gestao_aluno_foto(aluno_id):
    """Permite ao usuário padrão trocar apenas a foto do aluno (não os dados cadastrais)."""
    aluno = obter_aluno(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect(url_for("kiosk.gestao_alunos"))

    arquivo_foto = request.files.get("foto")
    if not arquivo_foto or not arquivo_foto.filename:
        flash("Selecione uma foto para enviar.", "erro")
        return redirect(request.referrer or url_for("kiosk.gestao_alunos"))

    if not extensao_permitida(arquivo_foto.filename):
        flash("Formato de foto não suportado. Use PNG, JPG, JPEG ou WEBP.", "erro")
        return redirect(request.referrer or url_for("kiosk.gestao_alunos"))

    try:
        from database.services import atualizar_foto_aluno
        nome_arquivo = salvar_foto_aluno(arquivo_foto, aluno_id)
        atualizar_foto_aluno(aluno_id, nome_arquivo)
        registrar_log(
            tipo="alteracao", mensagem=f"Foto do aluno \"{aluno['nome']}\" atualizada pelo usuário padrão (id={aluno_id}).",
            usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
        )
        _notificar_dados_atualizados("alunos")
        flash(f"Foto de \"{aluno['nome']}\" atualizada.", "sucesso")
    except ValueError as erro:
        flash(str(erro), "erro")

    return redirect(request.referrer or url_for("kiosk.gestao_alunos"))


@kiosk_bp.route("/gestao/salas")
@login_required
def gestao_salas():
    """Lista de salas para o usuário padrão cadastrar apenas a foto."""
    salas = listar_salas()
    return render_template("kiosk_gestao_salas.html", salas=salas)


@kiosk_bp.route("/gestao/salas/<int:sala_id>/foto", methods=["POST"])
@login_required
def gestao_sala_foto(sala_id):
    """Permite ao usuário padrão cadastrar/trocar a foto da sala (não os demais dados)."""
    sala = obter_sala(sala_id)
    if not sala:
        flash("Sala não encontrada.", "erro")
        return redirect(url_for("kiosk.gestao_salas"))

    arquivo_foto = request.files.get("foto")
    if not arquivo_foto or not arquivo_foto.filename:
        flash("Selecione uma foto para enviar.", "erro")
        return redirect(url_for("kiosk.gestao_salas"))

    if not extensao_permitida(arquivo_foto.filename):
        flash("Formato de foto não suportado. Use PNG, JPG, JPEG ou WEBP.", "erro")
        return redirect(url_for("kiosk.gestao_salas"))

    try:
        salvar_foto_sala(arquivo_foto, sala_id)
        registrar_log(
            tipo="alteracao", mensagem=f"Foto da sala \"{sala['nome']}\" atualizada pelo usuário padrão (id={sala_id}).",
            usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
        )
        _notificar_dados_atualizados("salas")
        flash(f"Foto de \"{sala['nome']}\" atualizada.", "sucesso")
    except ValueError as erro:
        flash(str(erro), "erro")

    return redirect(url_for("kiosk.gestao_salas"))
