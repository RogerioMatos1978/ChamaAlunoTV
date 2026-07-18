"""
routes/admin.py
================
Área administrativa: Dashboard e cadastro de Salas (Módulo 3).

Acesso restrito aos perfis "administrador" e "supervisor" — o perfil
"operador" fica limitado às telas operacionais (Kiosk, Presença), que
serão implementadas nos próximos módulos.

Os próximos módulos vão adicionar novas rotas aqui mesmo (alunos,
importação CSV, histórico, usuários, configurações), mantendo tudo o
que é "administração" organizado em um único blueprint.
"""

import csv
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, session, send_file

from database.services import (
    listar_salas, obter_sala, criar_sala, atualizar_sala, excluir_sala,
    existe_nome_sala, obter_estatisticas_dashboard, registrar_log,
    listar_alunos, obter_aluno, criar_aluno, atualizar_aluno, excluir_aluno,
    salvar_foto_aluno, excluir_foto_aluno, extensao_permitida,
    importar_alunos_csv,
    listar_historico, obter_nomes_salas_no_historico, obter_chamada,
    gerar_csv_historico, gerar_excel_historico, gerar_pdf_historico,
    rechamar_aluno,
    listar_usuarios, criar_usuario, atualizar_usuario, alterar_senha_usuario,
    excluir_usuario, existe_login_usuario, contar_administradores_ativos,
    obter_usuario_por_id, PERFIS_VALIDOS,
    get_configuracao, set_configuracao,
    listar_logs,
    criar_backup, listar_backups, restaurar_backup,
)
from routes.auth import perfil_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _notificar_dados_atualizados(tipo: str):
    """
    Avisa (via Socket.IO) todas as telas abertas — Kiosk, Presença, outras
    abas do Admin — que salas ou alunos mudaram em algum lugar do sistema.
    Cada tela decide o que fazer: mostrar o aviso "Atualizar agora"
    (comportamento padrão, veja templates/base.html) em vez de recarregar
    sozinha e atrapalhar quem está no meio de uma tarefa (Módulo 11).

    Import tardio para evitar dependência circular com app.py (que
    importa este blueprint durante a criação da aplicação).
    """
    from app import socketio
    socketio.emit("dados_atualizados", {"tipo": tipo})


@admin_bp.before_request
@perfil_required("administrador", "supervisor")
def restringir_acesso():
    """
    Aplica a restrição de perfil a TODAS as rotas deste blueprint de uma
    só vez. Assim, cada rota nova adicionada aqui já nasce protegida,
    sem precisar repetir o decorator em cada função.
    """
    pass


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/")
@admin_bp.route("/dashboard")
def dashboard():
    """Painel inicial com os indicadores gerais do sistema."""
    stats = obter_estatisticas_dashboard()
    return render_template("admin/dashboard.html", stats=stats)


# ---------------------------------------------------------------------------
# Salas
# ---------------------------------------------------------------------------
@admin_bp.route("/salas")
def salas_lista():
    """Lista todas as salas cadastradas."""
    salas = listar_salas()
    return render_template("admin/salas_lista.html", salas=salas)


@admin_bp.route("/salas/nova", methods=["GET", "POST"])
def salas_nova():
    """Formulário de cadastro de uma nova sala."""
    if request.method == "POST":
        dados = _extrair_dados_formulario_sala()

        if not dados["nome"]:
            flash("O nome da sala é obrigatório.", "erro")
            return render_template("admin/sala_form.html", sala=dados, modo="nova")

        if existe_nome_sala(dados["nome"]):
            flash(f"Já existe uma sala chamada \"{dados['nome']}\".", "erro")
            return render_template("admin/sala_form.html", sala=dados, modo="nova")

        sala_id = criar_sala(**dados)
        registrar_log(tipo="alteracao", mensagem=f"Sala \"{dados['nome']}\" criada (id={sala_id}).")
        _notificar_dados_atualizados("salas")
        flash(f"Sala \"{dados['nome']}\" criada com sucesso.", "sucesso")
        return redirect(url_for("admin.salas_lista"))

    return render_template("admin/sala_form.html", sala=None, modo="nova")


@admin_bp.route("/salas/<int:sala_id>/editar", methods=["GET", "POST"])
def salas_editar(sala_id):
    """Formulário de edição de uma sala existente."""
    sala = obter_sala(sala_id)
    if not sala:
        flash("Sala não encontrada.", "erro")
        return redirect(url_for("admin.salas_lista"))

    if request.method == "POST":
        dados = _extrair_dados_formulario_sala()

        if not dados["nome"]:
            flash("O nome da sala é obrigatório.", "erro")
            return render_template("admin/sala_form.html", sala={**sala, **dados}, modo="editar")

        if existe_nome_sala(dados["nome"], ignorar_id=sala_id):
            flash(f"Já existe uma sala chamada \"{dados['nome']}\".", "erro")
            return render_template("admin/sala_form.html", sala={**sala, **dados}, modo="editar")

        atualizar_sala(sala_id, **dados)
        registrar_log(tipo="alteracao", mensagem=f"Sala \"{dados['nome']}\" (id={sala_id}) atualizada.")
        _notificar_dados_atualizados("salas")
        flash(f"Sala \"{dados['nome']}\" atualizada com sucesso.", "sucesso")
        return redirect(url_for("admin.salas_lista"))

    return render_template("admin/sala_form.html", sala=sala, modo="editar")


@admin_bp.route("/salas/<int:sala_id>/excluir", methods=["POST"])
def salas_excluir(sala_id):
    """Exclui uma sala (os alunos vinculados são preservados, apenas desvinculados)."""
    sala = obter_sala(sala_id)
    if sala:
        excluir_sala(sala_id)
        registrar_log(tipo="alteracao", mensagem=f"Sala \"{sala['nome']}\" (id={sala_id}) excluída.")
        _notificar_dados_atualizados("salas")
        flash(f"Sala \"{sala['nome']}\" excluída.", "sucesso")
    else:
        flash("Sala não encontrada.", "erro")
    return redirect(url_for("admin.salas_lista"))


def _extrair_dados_formulario_sala() -> dict:
    """Lê e normaliza os campos do formulário de sala vindos do POST."""
    try:
        ordem = int(request.form.get("ordem") or 0)
    except ValueError:
        ordem = 0

    return {
        "nome": (request.form.get("nome") or "").strip(),
        "descricao": (request.form.get("descricao") or "").strip() or None,
        "cor": request.form.get("cor") or "#164194",
        "ordem": ordem,
        "ativa": request.form.get("ativa") == "on",
        "observacoes": (request.form.get("observacoes") or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# Alunos
# ---------------------------------------------------------------------------
@admin_bp.route("/alunos")
def alunos_lista():
    """Lista de alunos com busca e filtro por sala."""
    sala_id = request.args.get("sala_id", type=int)
    busca = request.args.get("busca", "").strip() or None

    alunos = listar_alunos(sala_id=sala_id, busca=busca)
    salas = listar_salas()
    return render_template(
        "admin/alunos_lista.html", alunos=alunos, salas=salas,
        sala_id=sala_id, busca=busca or "",
    )


@admin_bp.route("/alunos/novo", methods=["GET", "POST"])
def alunos_novo():
    """Formulário de cadastro de um novo aluno (com upload de foto opcional)."""
    salas = listar_salas()

    if request.method == "POST":
        dados = _extrair_dados_formulario_aluno()

        if not dados["nome"]:
            flash("O nome do aluno é obrigatório.", "erro")
            return render_template("admin/aluno_form.html", aluno=dados, salas=salas, modo="novo")

        arquivo_foto = request.files.get("foto")
        if arquivo_foto and arquivo_foto.filename and not extensao_permitida(arquivo_foto.filename):
            flash("Formato de foto não suportado. Use PNG, JPG, JPEG ou WEBP.", "erro")
            return render_template("admin/aluno_form.html", aluno=dados, salas=salas, modo="novo")

        aluno_id = criar_aluno(**dados)

        if arquivo_foto and arquivo_foto.filename:
            try:
                nome_arquivo = salvar_foto_aluno(arquivo_foto, aluno_id)
                atualizar_aluno(aluno_id, foto=nome_arquivo, **dados)
            except ValueError as erro:
                flash(str(erro), "alerta")

        registrar_log(tipo="alteracao", mensagem=f"Aluno \"{dados['nome']}\" cadastrado (id={aluno_id}).")
        _notificar_dados_atualizados("alunos")
        flash(f"Aluno \"{dados['nome']}\" cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin.alunos_lista"))

    return render_template("admin/aluno_form.html", aluno=None, salas=salas, modo="novo")


@admin_bp.route("/alunos/<int:aluno_id>/editar", methods=["GET", "POST"])
def alunos_editar(aluno_id):
    """Formulário de edição de um aluno existente."""
    aluno = obter_aluno(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect(url_for("admin.alunos_lista"))

    salas = listar_salas()

    if request.method == "POST":
        dados = _extrair_dados_formulario_aluno()

        if not dados["nome"]:
            flash("O nome do aluno é obrigatório.", "erro")
            return render_template("admin/aluno_form.html", aluno={**aluno, **dados}, salas=salas, modo="editar")

        arquivo_foto = request.files.get("foto")
        nome_foto = aluno["foto"]
        if arquivo_foto and arquivo_foto.filename:
            if not extensao_permitida(arquivo_foto.filename):
                flash("Formato de foto não suportado. Use PNG, JPG, JPEG ou WEBP.", "erro")
                return render_template("admin/aluno_form.html", aluno={**aluno, **dados}, salas=salas, modo="editar")
            try:
                nome_foto = salvar_foto_aluno(arquivo_foto, aluno_id)
            except ValueError as erro:
                flash(str(erro), "alerta")

        atualizar_aluno(aluno_id, foto=nome_foto, **dados)
        registrar_log(tipo="alteracao", mensagem=f"Aluno \"{dados['nome']}\" (id={aluno_id}) atualizado.")
        _notificar_dados_atualizados("alunos")
        flash(f"Aluno \"{dados['nome']}\" atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin.alunos_lista"))

    return render_template("admin/aluno_form.html", aluno=aluno, salas=salas, modo="editar")


@admin_bp.route("/alunos/<int:aluno_id>/excluir", methods=["POST"])
def alunos_excluir(aluno_id):
    """Exclui um aluno e sua foto (o histórico de chamadas é preservado por snapshot)."""
    aluno = obter_aluno(aluno_id)
    if aluno:
        excluir_foto_aluno(aluno["foto"])
        excluir_aluno(aluno_id)
        registrar_log(tipo="alteracao", mensagem=f"Aluno \"{aluno['nome']}\" (id={aluno_id}) excluído.")
        _notificar_dados_atualizados("alunos")
        flash(f"Aluno \"{aluno['nome']}\" excluído.", "sucesso")
    else:
        flash("Aluno não encontrado.", "erro")
    return redirect(url_for("admin.alunos_lista"))


def _extrair_dados_formulario_aluno() -> dict:
    """Lê e normaliza os campos do formulário de aluno vindos do POST."""
    try:
        sala_id = int(request.form.get("sala_id") or 0) or None
    except ValueError:
        sala_id = None

    return {
        "nome": (request.form.get("nome") or "").strip(),
        "turma": (request.form.get("turma") or "").strip() or None,
        "sala_id": sala_id,
        "codigo": (request.form.get("codigo") or "").strip() or None,
        "cpf": (request.form.get("cpf") or "").strip() or None,
        "observacoes": (request.form.get("observacoes") or "").strip() or None,
        "prioridade": 1 if request.form.get("prioridade") == "on" else 0,
    }


# ---------------------------------------------------------------------------
# Importação de alunos via CSV
# ---------------------------------------------------------------------------
@admin_bp.route("/alunos/importar", methods=["GET", "POST"])
def alunos_importar():
    """
    Importação em massa de alunos a partir de um arquivo CSV no formato:

        aluno;serie;sala;foto

    Salas citadas são criadas automaticamente; alunos já existentes
    (mesmo nome + série) são atualizados em vez de duplicados.
    """
    if request.method == "POST":
        arquivo = request.files.get("arquivo_csv")
        if not arquivo or not arquivo.filename:
            flash("Selecione um arquivo CSV para importar.", "erro")
            return render_template("admin/importar_csv.html", resumo=None)

        if not arquivo.filename.lower().endswith(".csv"):
            flash("O arquivo precisa ter a extensão .csv.", "erro")
            return render_template("admin/importar_csv.html", resumo=None)

        try:
            linhas = _ler_linhas_csv(arquivo)
        except (UnicodeDecodeError, csv.Error) as erro:
            flash(f"Não foi possível ler o arquivo: {erro}", "erro")
            return render_template("admin/importar_csv.html", resumo=None)

        resumo = importar_alunos_csv(linhas)
        registrar_log(
            tipo="importacao",
            mensagem=(
                f"Importação CSV concluída: {resumo['criados']} criados, "
                f"{resumo['atualizados']} atualizados, {resumo['salas_criadas']} salas criadas, "
                f"{resumo['ignorados']} linhas ignoradas."
            ),
        )
        if resumo["criados"] or resumo["atualizados"] or resumo["salas_criadas"]:
            _notificar_dados_atualizados("alunos")
        flash("Importação concluída com sucesso.", "sucesso")
        return render_template("admin/importar_csv.html", resumo=resumo)

    return render_template("admin/importar_csv.html", resumo=None)


def _ler_linhas_csv(arquivo) -> list:
    """
    Lê o arquivo CSV enviado (delimitador ';') e retorna uma lista de
    dicionários com as chaves 'aluno', 'serie', 'sala', 'foto'.

    Tenta decodificar em UTF-8 primeiro (padrão) e, se falhar, em
    Latin-1 (comum em arquivos exportados de planilhas no Windows).
    """
    conteudo_bytes = arquivo.read()
    try:
        texto = conteudo_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo_bytes.decode("latin-1")

    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    linhas_brutas = [linha for linha in leitor if any(campo.strip() for campo in linha)]

    if not linhas_brutas:
        return []

    # Detecta e descarta a linha de cabeçalho, se presente.
    primeira = [campo.strip().lower() for campo in linhas_brutas[0]]
    inicio = 1 if primeira and primeira[0] in ("aluno", "nome") else 0

    colunas = ["aluno", "serie", "sala", "foto"]
    resultado = []
    for linha in linhas_brutas[inicio:]:
        item = {colunas[i]: (linha[i] if i < len(linha) else "") for i in range(len(colunas))}
        resultado.append(item)
    return resultado


# ---------------------------------------------------------------------------
# Histórico e exportações (Módulo 8)
# ---------------------------------------------------------------------------
def _filtros_historico_da_query():
    """Lê os filtros de histórico a partir da query string (compartilhado entre tela e exportações)."""
    return {
        "busca": request.args.get("busca", "").strip() or None,
        "sala_nome": request.args.get("sala_nome", "").strip() or None,
        "tipo": request.args.get("tipo", "").strip() or None,
        "data_inicio": request.args.get("data_inicio", "").strip() or None,
        "data_fim": request.args.get("data_fim", "").strip() or None,
    }


@admin_bp.route("/historico")
def historico_lista():
    """Histórico pesquisável de todas as chamadas realizadas."""
    filtros = _filtros_historico_da_query()
    registros = listar_historico(**filtros)
    salas_historico = obter_nomes_salas_no_historico()
    return render_template(
        "admin/historico_lista.html", registros=registros, salas_historico=salas_historico,
        filtros=filtros,
    )


@admin_bp.route("/historico/exportar/<formato>")
def historico_exportar(formato):
    """Exporta o histórico filtrado nos formatos csv, xlsx ou pdf."""
    filtros = _filtros_historico_da_query()
    registros = listar_historico(**filtros, limite=10000)
    nome_arquivo = "historico_chamadas"

    if formato == "csv":
        conteudo = gerar_csv_historico(registros)
        tipo_mime = "text/csv; charset=utf-8-sig"
        extensao = "csv"
    elif formato == "xlsx":
        conteudo = gerar_excel_historico(registros)
        tipo_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extensao = "xlsx"
    elif formato == "pdf":
        conteudo = gerar_pdf_historico(registros)
        tipo_mime = "application/pdf"
        extensao = "pdf"
    else:
        flash("Formato de exportação inválido.", "erro")
        return redirect(url_for("admin.historico_lista"))

    registrar_log(tipo="alteracao", mensagem=f"Histórico exportado em formato {extensao.upper()} ({len(registros)} registros).")

    # Usamos o header Content-Type diretamente (em vez do parâmetro
    # `mimetype`) para evitar que o Flask acrescente um `charset=utf-8`
    # duplicado por cima do `utf-8-sig` do CSV.
    return Response(
        conteudo,
        headers={
            "Content-Type": tipo_mime,
            "Content-Disposition": f"attachment; filename={nome_arquivo}.{extensao}",
        },
    )


@admin_bp.route("/historico/<int:chamada_id>/rechamar", methods=["POST"])
def historico_rechamar(chamada_id):
    """Repete a narração/exibição de uma chamada já registrada (aluno não compareceu, por exemplo)."""
    registro = obter_chamada(chamada_id)
    if not registro or not registro["aluno_id"]:
        flash("Não é possível rechamar: aluno não encontrado (pode ter sido excluído).", "erro")
        return redirect(url_for("admin.historico_lista"))

    nova_chamada = rechamar_aluno(
        registro["aluno_id"],
        operador_id=session.get("usuario_id"),
        operador_nome=session.get("usuario_nome"),
        ip=request.remote_addr,
    )

    if nova_chamada:
        # Import tardio para evitar dependência circular com app.py (que
        # importa este blueprint durante a criação da aplicação).
        from app import socketio
        socketio.emit("aluno_chamado", nova_chamada)
        registrar_log(
            tipo="chamada",
            mensagem=f"Aluno \"{nova_chamada['aluno_nome']}\" rechamado a partir do histórico.",
            usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"),
            ip=request.remote_addr,
        )
        flash(f"\"{nova_chamada['aluno_nome']}\" foi rechamado(a).", "sucesso")
    else:
        flash("Não foi possível rechamar este aluno.", "erro")

    return redirect(url_for("admin.historico_lista"))


# ---------------------------------------------------------------------------
# Usuários (Módulo 10) — apenas administradores
# ---------------------------------------------------------------------------
@admin_bp.route("/usuarios")
@perfil_required("administrador")
def usuarios_lista():
    """Lista todos os usuários do sistema."""
    return render_template("admin/usuarios_lista.html", usuarios=listar_usuarios())


@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@perfil_required("administrador")
def usuarios_novo():
    """Cadastro de um novo usuário (administrador, supervisor ou operador)."""
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        usuario = (request.form.get("usuario") or "").strip()
        senha = request.form.get("senha") or ""
        perfil = request.form.get("perfil") or "operador"
        email = (request.form.get("email") or "").strip() or None

        erro = _validar_dados_usuario(nome, usuario, senha, perfil, exigir_senha=True)
        if erro:
            flash(erro, "erro")
            return render_template("admin/usuario_form.html", usuario=request.form, modo="novo", perfis=PERFIS_VALIDOS)

        if existe_login_usuario(usuario):
            flash(f"Já existe um usuário com o login \"{usuario}\".", "erro")
            return render_template("admin/usuario_form.html", usuario=request.form, modo="novo", perfis=PERFIS_VALIDOS)

        usuario_id = criar_usuario(nome=nome, usuario=usuario, senha=senha, perfil=perfil, email=email)
        registrar_log(tipo="alteracao", mensagem=f"Usuário \"{usuario}\" criado (id={usuario_id}, perfil={perfil}).",
                      usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
        flash(f"Usuário \"{nome}\" criado com sucesso.", "sucesso")
        return redirect(url_for("admin.usuarios_lista"))

    return render_template("admin/usuario_form.html", usuario=None, modo="novo", perfis=PERFIS_VALIDOS)


@admin_bp.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@perfil_required("administrador")
def usuarios_editar(usuario_id):
    """Edição de um usuário existente (dados cadastrais, perfil e situação)."""
    usuario_atual = obter_usuario_por_id(usuario_id)
    if not usuario_atual:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios_lista"))

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        login = (request.form.get("usuario") or "").strip()
        perfil = request.form.get("perfil") or "operador"
        email = (request.form.get("email") or "").strip() or None
        ativo = request.form.get("ativo") == "on"

        erro = _validar_dados_usuario(nome, login, "x", perfil, exigir_senha=False)
        if erro:
            flash(erro, "erro")
            return render_template("admin/usuario_form.html", usuario={**usuario_atual, **request.form}, modo="editar", perfis=PERFIS_VALIDOS)

        if existe_login_usuario(login, ignorar_id=usuario_id):
            flash(f"Já existe um usuário com o login \"{login}\".", "erro")
            return render_template("admin/usuario_form.html", usuario={**usuario_atual, **request.form}, modo="editar", perfis=PERFIS_VALIDOS)

        # Impede remover o último administrador ativo do sistema.
        vai_deixar_de_ser_admin = usuario_atual["perfil"] == "administrador" and (perfil != "administrador" or not ativo)
        if vai_deixar_de_ser_admin and contar_administradores_ativos(ignorar_id=usuario_id) == 0:
            flash("Não é possível remover o último administrador ativo do sistema.", "erro")
            return render_template("admin/usuario_form.html", usuario=usuario_atual, modo="editar", perfis=PERFIS_VALIDOS)

        atualizar_usuario(usuario_id, nome=nome, email=email, perfil=perfil, ativo=ativo)

        nova_senha = request.form.get("nova_senha")
        if nova_senha:
            alterar_senha_usuario(usuario_id, nova_senha)

        registrar_log(tipo="alteracao", mensagem=f"Usuário \"{login}\" (id={usuario_id}) atualizado.",
                      usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
        flash(f"Usuário \"{nome}\" atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin.usuarios_lista"))

    return render_template("admin/usuario_form.html", usuario=usuario_atual, modo="editar", perfis=PERFIS_VALIDOS)


@admin_bp.route("/usuarios/<int:usuario_id>/excluir", methods=["POST"])
@perfil_required("administrador")
def usuarios_excluir(usuario_id):
    """Exclui um usuário (impede excluir o último administrador ou a si mesmo)."""
    usuario_alvo = obter_usuario_por_id(usuario_id)
    if not usuario_alvo:
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin.usuarios_lista"))

    if usuario_id == session.get("usuario_id"):
        flash("Você não pode excluir o próprio usuário enquanto estiver logado.", "erro")
        return redirect(url_for("admin.usuarios_lista"))

    if usuario_alvo["perfil"] == "administrador" and contar_administradores_ativos(ignorar_id=usuario_id) == 0:
        flash("Não é possível excluir o último administrador ativo do sistema.", "erro")
        return redirect(url_for("admin.usuarios_lista"))

    excluir_usuario(usuario_id)
    registrar_log(tipo="alteracao", mensagem=f"Usuário \"{usuario_alvo['usuario']}\" (id={usuario_id}) excluído.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    flash(f"Usuário \"{usuario_alvo['nome']}\" excluído.", "sucesso")
    return redirect(url_for("admin.usuarios_lista"))


def _validar_dados_usuario(nome, usuario, senha, perfil, exigir_senha):
    """Validações compartilhadas entre criação e edição de usuário."""
    if not nome:
        return "O nome é obrigatório."
    if not usuario:
        return "O login é obrigatório."
    if perfil not in PERFIS_VALIDOS:
        return "Perfil inválido."
    if exigir_senha and len(senha) < 4:
        return "A senha deve ter pelo menos 4 caracteres."
    return None


# ---------------------------------------------------------------------------
# Configurações do sistema (Módulo 10) — apenas administradores
# ---------------------------------------------------------------------------
@admin_bp.route("/configuracoes", methods=["GET", "POST"])
@perfil_required("administrador")
def configuracoes():
    """
    Configurações gerais: nome da instituição, logo, cores de identidade
    visual e padrões de narração. Fica salvo na tabela `configuracoes`
    (chave/valor) e tem prioridade sobre os valores padrão de config.py.
    """
    if request.method == "POST":
        set_configuracao("nome_instituicao", (request.form.get("nome_instituicao") or "").strip())
        set_configuracao("cor_menu", request.form.get("cor_menu") or "#164194")
        set_configuracao("cor_footer", request.form.get("cor_footer") or "#6CC2BA")
        set_configuracao("narracao_idioma", request.form.get("narracao_idioma") or "pt-BR")
        set_configuracao("narracao_repeticoes", request.form.get("narracao_repeticoes") or "2")

        arquivo_logo = request.files.get("logo")
        if arquivo_logo and arquivo_logo.filename:
            if extensao_permitida(arquivo_logo.filename):
                from config import Config as ConfigApp
                arquivo_logo.save(str(ConfigApp.LOGOS_DIR / "logo.png"))
            else:
                flash("Formato de imagem não suportado para a logo. Use PNG, JPG, JPEG ou WEBP.", "alerta")

        registrar_log(tipo="alteracao", mensagem="Configurações do sistema atualizadas.",
                      usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
        flash("Configurações salvas com sucesso.", "sucesso")
        return redirect(url_for("admin.configuracoes"))

    valores = {
        "nome_instituicao": get_configuracao("nome_instituicao", ""),
        "cor_menu": get_configuracao("cor_menu", "#164194"),
        "cor_footer": get_configuracao("cor_footer", "#6CC2BA"),
        "narracao_idioma": get_configuracao("narracao_idioma", "pt-BR"),
        "narracao_repeticoes": get_configuracao("narracao_repeticoes", "2"),
    }
    return render_template("admin/configuracoes.html", valores=valores)


# ---------------------------------------------------------------------------
# Auditoria (Módulo 10)
# ---------------------------------------------------------------------------
@admin_bp.route("/auditoria")
@perfil_required("administrador", "supervisor")
def auditoria():
    """Consulta ao log de auditoria (login, erros, chamadas, importações, alterações)."""
    tipo = request.args.get("tipo") or None
    registros = listar_logs(tipo=tipo, limite=300)
    return render_template("admin/auditoria.html", registros=registros, tipo=tipo)


# ---------------------------------------------------------------------------
# Backup e restauração (Módulo 10)
# ---------------------------------------------------------------------------
@admin_bp.route("/backup")
@perfil_required("administrador")
def backup_lista():
    """Lista os backups existentes e permite criar um novo ou restaurar."""
    return render_template("admin/backup.html", backups=listar_backups())


@admin_bp.route("/backup/novo", methods=["POST"])
@perfil_required("administrador")
def backup_novo():
    """Cria um novo backup manual do banco de dados."""
    nome_arquivo = criar_backup()
    registrar_log(tipo="alteracao", mensagem=f"Backup manual criado: {nome_arquivo}.",
                  usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
    flash(f"Backup \"{nome_arquivo}\" criado com sucesso.", "sucesso")
    return redirect(url_for("admin.backup_lista"))


@admin_bp.route("/backup/<nome_arquivo>/baixar")
@perfil_required("administrador")
def backup_baixar(nome_arquivo):
    """Baixa um arquivo de backup específico."""
    from config import Config as ConfigApp
    from werkzeug.utils import secure_filename as sf
    caminho = ConfigApp.BACKUPS_DIR / sf(nome_arquivo)
    if not caminho.exists():
        flash("Backup não encontrado.", "erro")
        return redirect(url_for("admin.backup_lista"))
    return send_file(caminho, as_attachment=True)


@admin_bp.route("/backup/<nome_arquivo>/restaurar", methods=["POST"])
@perfil_required("administrador")
def backup_restaurar(nome_arquivo):
    """Restaura o banco de dados a partir de um backup existente."""
    try:
        restaurar_backup(nome_arquivo)
        registrar_log(tipo="alteracao", mensagem=f"Banco de dados restaurado a partir do backup: {nome_arquivo}.",
                      usuario_id=session.get("usuario_id"), usuario_nome=session.get("usuario_nome"))
        flash("Banco de dados restaurado com sucesso. Recomenda-se reiniciar o sistema.", "sucesso")
    except FileNotFoundError:
        flash("Arquivo de backup não encontrado.", "erro")
    return redirect(url_for("admin.backup_lista"))


# ---------------------------------------------------------------------------
# QR Code por sala (Módulo 10)
# ---------------------------------------------------------------------------
@admin_bp.route("/salas/<int:sala_id>/qrcode.png")
def sala_qrcode(sala_id):
    """
    Gera (sob demanda, sem salvar em disco) um QR Code apontando para a
    tela de Presença filtrada por esta sala — útil para famílias/alunos
    acompanharem a fila pelo celular.
    """
    import qrcode

    sala = obter_sala(sala_id)
    if not sala:
        flash("Sala não encontrada.", "erro")
        return redirect(url_for("admin.salas_lista"))

    url_destino = url_for("presenca.lista", sala_id=sala_id, _external=True)
    imagem = qrcode.make(url_destino)

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")
