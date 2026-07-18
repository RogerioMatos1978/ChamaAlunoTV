"""
routes/auth.py
===============
Autenticação: login, logout e controle de permissões por perfil.

Este blueprint concentra tudo que é comum a todas as telas protegidas
do sistema (admin, kiosk, presença, etc.):

    - `login_required`   -> exige que exista uma sessão válida.
    - `perfil_required`  -> exige, além da sessão, um perfil específico
                             (ex.: apenas "administrador").

Os demais blueprints (routes/admin.py, routes/kiosk.py, ...) importam
esses decorators daqui em vez de duplicar a lógica de sessão.
"""

from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash
)

from database.services import (
    autenticar_usuario, atualizar_ultimo_login, registrar_log, obter_usuario_por_id,
)

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Decorators de proteção de rota
# ---------------------------------------------------------------------------
def login_required(view_func):
    """
    Bloqueia o acesso à rota se não houver usuário logado na sessão.

    Também detecta uma "sessão fantasma": quando a conta foi excluída ou
    desativada (ex.: pelo admin) DEPOIS que o login já tinha sido feito
    em outro dispositivo/aba — o cookie de sessão continua válido, mas o
    usuário não existe mais no banco. Sem essa checagem, qualquer ação
    dessa sessão que gravasse o `usuario_id` (log de auditoria, chamada,
    presença) quebraria com `IntegrityError` de chave estrangeira. Aqui
    a sessão é encerrada de forma limpa e a pessoa é levada de volta ao
    login, com uma mensagem clara em vez de um erro técnico.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para continuar.", "alerta")
            return redirect(url_for("auth.login", proximo=request.path))

        usuario_atual = obter_usuario_por_id(session["usuario_id"])
        if not usuario_atual or not usuario_atual["ativo"]:
            session.clear()
            flash("Sua sessão não é mais válida (a conta foi removida ou desativada). Faça login novamente.", "alerta")
            return redirect(url_for("auth.login", proximo=request.path))

        return view_func(*args, **kwargs)
    return wrapper


def perfil_required(*perfis_permitidos):
    """
    Bloqueia o acesso se o perfil da sessão não estiver entre os permitidos.

    Uso:
        @perfil_required("administrador")
        @perfil_required("administrador", "supervisor")
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("perfil") not in perfis_permitidos:
                flash("Você não tem permissão para acessar esta página.", "erro")
                return redirect(url_for("index"))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Tela de login. Redireciona para a página inicial se já estiver logado."""
    if "usuario_id" in session:
        return redirect(url_for("index"))

    proximo = request.args.get("proximo") or request.form.get("proximo") or url_for("index")

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        senha = request.form.get("senha") or ""
        ip = request.remote_addr

        dados = autenticar_usuario(usuario, senha)
        if dados:
            # Sessão protegida: `permanent=True` faz o cookie expirar após
            # PERMANENT_SESSION_LIFETIME (configurado em config.py), em vez
            # de durar indefinidamente.
            session.permanent = True
            session["usuario_id"] = dados["id"]
            session["usuario_nome"] = dados["nome"]
            session["perfil"] = dados["perfil"]

            atualizar_ultimo_login(dados["id"])
            registrar_log(
                tipo="login",
                mensagem=f"Login realizado com sucesso (usuário: {usuario}).",
                usuario_id=dados["id"],
                usuario_nome=dados["nome"],
                ip=ip,
            )
            return redirect(proximo)

        # Falha de autenticação: mensagem genérica de propósito
        # (não revela se o problema foi o usuário ou a senha).
        registrar_log(
            tipo="erro",
            mensagem=f"Tentativa de login falhou para o usuário '{usuario}'.",
            ip=ip,
        )
        flash("Usuário ou senha inválidos.", "erro")

    return render_template("login.html", proximo=proximo)


@auth_bp.route("/logout")
def logout():
    """Encerra a sessão do usuário atual."""
    usuario_nome = session.get("usuario_nome")
    usuario_id = session.get("usuario_id")
    session.clear()

    if usuario_id:
        registrar_log(
            tipo="login",
            mensagem="Logout realizado.",
            usuario_id=usuario_id,
            usuario_nome=usuario_nome,
            ip=request.remote_addr,
        )
    flash("Sessão encerrada com sucesso.", "sucesso")
    return redirect(url_for("auth.login"))
