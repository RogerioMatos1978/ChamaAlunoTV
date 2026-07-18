"""
app.py
======
Ponto de entrada da aplicação.

Usa o padrão "application factory" (`create_app`), que é a forma
recomendada pelo próprio Flask para projetos modulares: facilita testes,
evita importações circulares entre blueprints e permite criar múltiplas
instâncias da aplicação (ex.: uma para testes, outra para produção).

Como rodar em desenvolvimento:
    python app.py

Como rodar em produção:
    veja o README.md (seção "Implantação em produção").
"""

import eventlet
eventlet.monkey_patch()  # Necessário ANTES de qualquer outro import que use rede/sockets.

from flask import Flask, session, redirect, url_for, render_template
from flask_socketio import SocketIO
from flask_wtf import CSRFProtect

from config import get_config
from database.models import init_db
from database.services import (
    seed_admin_padrao, resolver_caminho_foto, resolver_caminho_foto_sala,
    get_configuracao, criar_backup,
)
from database.socket_events import register_socket_events

# Instância global do SocketIO. Fica fora de create_app() porque alguns
# módulos (ex.: routes/kiosk.py) precisam importar `socketio` diretamente
# para emitir eventos a partir de uma rota HTTP comum.
socketio = SocketIO()
csrf = CSRFProtect()


def create_app():
    """Cria e configura a instância da aplicação Flask."""
    app = Flask(__name__)
    app.config.from_object(get_config())

    # --- Inicializa o banco de dados (cria tabelas se necessário) ---
    init_db()

    # --- Cria o usuário administrador padrão na primeira execução ---
    seed_admin_padrao()

    # --- Extensões ---
    csrf.init_app(app)
    socketio.init_app(app, async_mode=app.config["SOCKETIO_ASYNC_MODE"], cors_allowed_origins="*")
    register_socket_events(socketio)

    # --- Blueprints (rotas) ---
    _registrar_blueprints(app)

    # --- Backup automático em segundo plano ---
    _iniciar_backup_automatico(app)

    # --- Injeta variáveis globais em todos os templates (base.html) ---
    # As configurações salvas pelo administrador (tabela `configuracoes`,
    # Módulo 10) têm prioridade sobre os valores padrão de config.py —
    # é assim que a tela de Configurações consegue trocar nome/cores/logo
    # sem precisar editar arquivos ou reiniciar o servidor.
    @app.context_processor
    def inject_globals():
        return {
            "nome_instituicao": get_configuracao("nome_instituicao") or app.config["NOME_INSTITUICAO"],
            "versao_sistema": app.config["VERSAO_SISTEMA"],
            "cor_menu": get_configuracao("cor_menu") or app.config["COR_MENU"],
            "cor_footer": get_configuracao("cor_footer") or app.config["COR_FOOTER"],
            # Módulo 15: para onde o aluno é chamado a se dirigir na
            # narração/exibição da TV (independente da sala/TV que
            # disparou a chamada) — ex.: "Favor dirigir-se à Portaria de Saída".
            "destino_chamada": get_configuracao("destino_chamada") or "Portaria de Saída",
            "usuario_logado": session.get("usuario_nome"),
            "perfil_logado": session.get("perfil"),
            # Função auxiliar usada nos templates: foto_url(aluno.foto)
            # Retorna a URL correta da foto do aluno, ou da imagem padrão
            # caso o arquivo não exista.
            "foto_url": lambda foto: url_for("static", filename=resolver_caminho_foto(foto)),
            # Mesma ideia, mas para a foto da sala (Módulo 12).
            "resolver_foto_sala": lambda foto: url_for("static", filename=resolver_caminho_foto_sala(foto)),
        }

    # --- Rota inicial ---
    # Módulo 15: quem NÃO está logado vê a página inicial (`home.html`),
    # que convida a fazer login — mas com atalhos diretos para o Kiosk e
    # o painel de TV, que continuam públicos (Módulo 14) e não passam
    # por aqui na prática (cada TV/terminal abre direto em `/kiosk` ou
    # `/screen`). Quem já está logado nunca vê a home: vai direto para
    # sua área principal — administrador/supervisor -> Dashboard
    # administrativo; operador -> Kiosk (seleção de sala).
    @app.route("/")
    def index():
        if "usuario_id" in session:
            if session.get("perfil") in ("administrador", "supervisor"):
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("kiosk.selecionar_sala"))
        return render_template("home.html")

    @app.route("/healthcheck")
    def healthcheck():
        """Usado para verificar rapidamente se o servidor está de pé."""
        return {"status": "ok", "versao": app.config["VERSAO_SISTEMA"]}

    return app


def _registrar_blueprints(app):
    """
    Ponto único de registro de blueprints.

    Mantido como função separada para que, à medida que os módulos
    (auth, admin, kiosk, screen, presenca, api) forem implementados,
    baste importar e chamar `app.register_blueprint(...)` aqui — sem
    precisar mexer no resto de `create_app()`.
    """
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.kiosk import kiosk_bp
    from routes.screen import screen_bp
    from routes.presenca import presenca_bp
    from routes.api import api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(kiosk_bp)
    app.register_blueprint(screen_bp)
    app.register_blueprint(presenca_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # A API é isenta de CSRF: ela é pensada para ser consumida via
    # fetch/JSON (protegida pelo login de sessão), não por formulários
    # HTML — que são o mecanismo que o CSRFProtect existe para proteger.
    csrf.exempt(api_bp)


def _iniciar_backup_automatico(app):
    """
    Inicia uma tarefa em segundo plano (greenlet do eventlet) que cria um
    backup do banco de dados periodicamente, a cada
    `BACKUP_INTERVALO_HORAS` horas — sem depender de um agendador externo
    (cron/Agendador de Tarefas). Veja também o Módulo 10 -> "backup/*"
    em routes/admin.py para o backup manual pela interface.
    """
    intervalo_segundos = app.config["BACKUP_INTERVALO_HORAS"] * 60 * 60

    def _loop_backup():
        while True:
            eventlet.sleep(intervalo_segundos)
            try:
                criar_backup()
            except Exception:
                # Um backup automático que falha não deve derrubar o
                # servidor; o erro fica registrado no log de erros do
                # Python (stderr/gunicorn) para investigação.
                app.logger.exception("Falha ao criar backup automático.")

    eventlet.spawn(_loop_backup)


# ---------------------------------------------------------------------------
# Execução direta (desenvolvimento)
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0" permite acesso por outros dispositivos na rede local
    # (ex.: a TV acessando a tela /screen pelo IP do servidor).
    #
    # use_reloader=False: o reloader automático do Flask reinicia o
    # processo inteiro a cada alteração de arquivo, o que reexecuta
    # eventlet.monkey_patch() em um subprocesso e costuma imprimir o
    # aviso "N RLock(s) were not greened" duas vezes. O aviso em si é
    # inofensivo (conhecido em Python 3.12+/3.13 com eventlet) e o
    # servidor funciona normalmente mesmo com ele — mas manter o
    # reloader desligado deixa o terminal mais limpo em desenvolvimento.
    # Se quiser recarregar automaticamente ao editar o código, troque
    # para use_reloader=True e reinicie manualmente quando precisar.
    socketio.run(app, host="0.0.0.0", port=5000, debug=app.config["DEBUG"], use_reloader=False)
