"""
routes/api.py
=============
API REST do sistema (Módulo 9).

Endpoints:
    /api/salas       -> GET, POST, PUT (/<id>), DELETE (/<id>)
    /api/alunos      -> GET, POST, PUT (/<id>), DELETE (/<id>)
    /api/chamadas    -> GET (fila atual) e POST (chama um aluno)
    /api/historico   -> GET (somente leitura — é um registro permanente)

Autenticação: reaproveita a sessão de login do sistema (o mesmo cookie
usado pelas telas HTML) — quem chama a API precisa estar logado. Esta
rota é isenta de CSRF (veja `csrf.exempt(api_bp)` em app.py) porque é
pensada para ser consumida por código (fetch/JSON), não por formulários
HTML. Para integração com sistemas externos em produção, recomenda-se
adicionar autenticação por token/API key na frente deste blueprint.

Formato de resposta: o próprio recurso em caso de sucesso, ou
`{"erro": "mensagem"}` com o status HTTP apropriado em caso de falha.
"""

from flask import Blueprint, jsonify, request, session

from database.services import (
    listar_salas, obter_sala, criar_sala, atualizar_sala, excluir_sala, existe_nome_sala,
    listar_alunos, obter_aluno, criar_aluno, atualizar_aluno, excluir_aluno,
    chamar_aluno, listar_historico, registrar_log,
)
from routes.auth import login_required, perfil_required

api_bp = Blueprint("api", __name__)


@api_bp.before_request
@login_required
def exigir_login_api():
    """Toda a API exige uma sessão autenticada."""
    pass


# ---------------------------------------------------------------------------
# /api/salas
# ---------------------------------------------------------------------------
@api_bp.route("/salas", methods=["GET"])
def api_salas_listar():
    return jsonify(listar_salas())


@api_bp.route("/salas/<int:sala_id>", methods=["GET"])
def api_salas_obter(sala_id):
    sala = obter_sala(sala_id)
    if not sala:
        return jsonify({"erro": "Sala não encontrada."}), 404
    return jsonify(sala)


@api_bp.route("/salas", methods=["POST"])
@perfil_required("administrador", "supervisor")
def api_salas_criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "O campo 'nome' é obrigatório."}), 400
    if existe_nome_sala(nome):
        return jsonify({"erro": f"Já existe uma sala chamada \"{nome}\"."}), 409

    sala_id = criar_sala(
        nome=nome, descricao=dados.get("descricao"), cor=dados.get("cor", "#164194"),
        ordem=int(dados.get("ordem", 0)), ativa=bool(dados.get("ativa", True)),
        observacoes=dados.get("observacoes"),
    )
    registrar_log(tipo="alteracao", mensagem=f"Sala \"{nome}\" criada via API (id={sala_id}).",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify(obter_sala(sala_id)), 201


@api_bp.route("/salas/<int:sala_id>", methods=["PUT"])
@perfil_required("administrador", "supervisor")
def api_salas_atualizar(sala_id):
    if not obter_sala(sala_id):
        return jsonify({"erro": "Sala não encontrada."}), 404

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "O campo 'nome' é obrigatório."}), 400
    if existe_nome_sala(nome, ignorar_id=sala_id):
        return jsonify({"erro": f"Já existe uma sala chamada \"{nome}\"."}), 409

    atualizar_sala(
        sala_id, nome=nome, descricao=dados.get("descricao"), cor=dados.get("cor", "#164194"),
        ordem=int(dados.get("ordem", 0)), ativa=bool(dados.get("ativa", True)),
        observacoes=dados.get("observacoes"),
    )
    registrar_log(tipo="alteracao", mensagem=f"Sala \"{nome}\" (id={sala_id}) atualizada via API.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify(obter_sala(sala_id))


@api_bp.route("/salas/<int:sala_id>", methods=["DELETE"])
@perfil_required("administrador", "supervisor")
def api_salas_excluir(sala_id):
    sala = obter_sala(sala_id)
    if not sala:
        return jsonify({"erro": "Sala não encontrada."}), 404
    excluir_sala(sala_id)
    registrar_log(tipo="alteracao", mensagem=f"Sala \"{sala['nome']}\" (id={sala_id}) excluída via API.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify({"sucesso": True})


# ---------------------------------------------------------------------------
# /api/alunos
# ---------------------------------------------------------------------------
@api_bp.route("/alunos", methods=["GET"])
def api_alunos_listar():
    sala_id = request.args.get("sala_id", type=int)
    status = request.args.get("status")
    busca = request.args.get("busca")
    return jsonify(listar_alunos(sala_id=sala_id, status=status, busca=busca))


@api_bp.route("/alunos/<int:aluno_id>", methods=["GET"])
def api_alunos_obter(aluno_id):
    aluno = obter_aluno(aluno_id)
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado."}), 404
    return jsonify(aluno)


@api_bp.route("/alunos", methods=["POST"])
def api_alunos_criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "O campo 'nome' é obrigatório."}), 400

    aluno_id = criar_aluno(
        nome=nome, turma=dados.get("turma"), sala_id=dados.get("sala_id"),
        codigo=dados.get("codigo"), cpf=dados.get("cpf"), observacoes=dados.get("observacoes"),
        prioridade=int(dados.get("prioridade", 0)),
    )
    registrar_log(tipo="alteracao", mensagem=f"Aluno \"{nome}\" criado via API (id={aluno_id}).",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify(obter_aluno(aluno_id)), 201


@api_bp.route("/alunos/<int:aluno_id>", methods=["PUT"])
def api_alunos_atualizar(aluno_id):
    if not obter_aluno(aluno_id):
        return jsonify({"erro": "Aluno não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "O campo 'nome' é obrigatório."}), 400

    atualizar_aluno(
        aluno_id, nome=nome, turma=dados.get("turma"), sala_id=dados.get("sala_id"),
        codigo=dados.get("codigo"), cpf=dados.get("cpf"), observacoes=dados.get("observacoes"),
        prioridade=int(dados.get("prioridade", 0)),
    )
    registrar_log(tipo="alteracao", mensagem=f"Aluno \"{nome}\" (id={aluno_id}) atualizado via API.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify(obter_aluno(aluno_id))


@api_bp.route("/alunos/<int:aluno_id>", methods=["DELETE"])
def api_alunos_excluir(aluno_id):
    aluno = obter_aluno(aluno_id)
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado."}), 404
    excluir_aluno(aluno_id)
    registrar_log(tipo="alteracao", mensagem=f"Aluno \"{aluno['nome']}\" (id={aluno_id}) excluído via API.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    return jsonify({"sucesso": True})


# ---------------------------------------------------------------------------
# /api/chamadas
# ---------------------------------------------------------------------------
@api_bp.route("/chamadas", methods=["GET"])
def api_chamadas_fila():
    """Retorna a fila atual (alunos aguardando), opcionalmente filtrada por sala."""
    sala_id = request.args.get("sala_id", type=int)
    return jsonify(listar_alunos(sala_id=sala_id, status="aguardando", ordenar_por="fila"))


@api_bp.route("/chamadas", methods=["POST"])
def api_chamadas_criar():
    """
    Chama um aluno (equivalente a clicar em "CHAMAR" no Kiosk): remove
    da fila, grava o histórico e transmite o evento para todas as telas
    conectadas via Socket.IO.
    """
    dados = request.get_json(silent=True) or {}
    aluno_id = dados.get("aluno_id")
    if not aluno_id:
        return jsonify({"erro": "O campo 'aluno_id' é obrigatório."}), 400

    chamada = chamar_aluno(
        aluno_id, operador_id=session.get("usuario_id"), operador_nome=session.get("usuario_nome"),
        ip=request.remote_addr, guiche=dados.get("guiche"),
    )
    if not chamada:
        return jsonify({"erro": "Aluno não encontrado ou já foi chamado."}), 409

    # Import tardio para evitar dependência circular (app.py importa este
    # blueprint durante a criação da aplicação).
    from app import socketio
    socketio.emit("aluno_chamado", chamada)

    registrar_log(tipo="chamada", mensagem=f"Aluno \"{chamada['aluno_nome']}\" chamado via API.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
                  ip=request.remote_addr)
    return jsonify(chamada), 201


# ---------------------------------------------------------------------------
# /api/historico (somente leitura)
# ---------------------------------------------------------------------------
@api_bp.route("/historico", methods=["GET"])
def api_historico_listar():
    filtros = {
        "busca": request.args.get("busca"),
        "sala_nome": request.args.get("sala_nome"),
        "tipo": request.args.get("tipo"),
        "data_inicio": request.args.get("data_inicio"),
        "data_fim": request.args.get("data_fim"),
        "limite": request.args.get("limite", default=200, type=int),
    }
    return jsonify(listar_historico(**filtros))
