"""
config.py
=========
Configurações centrais do sistema.

Aqui ficam TODOS os parâmetros que podem mudar entre ambientes
(desenvolvimento, produção) ou entre instituições (cores, nome, etc.).
Nada de "números mágicos" espalhados pelo código: tudo referenciado
a partir daqui.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos base do projeto
# ---------------------------------------------------------------------------
# BASE_DIR = pasta raiz do projeto (onde este arquivo está localizado).
BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "alunos.db"

STATIC_DIR = BASE_DIR / "static"
FOTOS_DIR = STATIC_DIR / "fotos"
SALAS_DIR = STATIC_DIR / "fotos_salas"    # fotos das salas (Módulo 12)
UPLOADS_DIR = STATIC_DIR / "uploads"
LOGOS_DIR = STATIC_DIR / "img" / "logos"
ICONS_DIR = STATIC_DIR / "img" / "icons"

BACKUPS_DIR = BASE_DIR / "backups"
LOGS_DIR = BASE_DIR / "logs"

# Garante que as pastas essenciais existam mesmo em uma instalação nova
for _dir in (DATABASE_DIR, FOTOS_DIR, SALAS_DIR, UPLOADS_DIR, LOGOS_DIR, ICONS_DIR, BACKUPS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


class Config:
    """Configuração base, compartilhada por todos os ambientes."""

    # --- Segurança ---
    # Em produção, defina a variável de ambiente SECRET_KEY com um valor
    # aleatório e seguro (nunca deixe o valor padrão em produção).
    SECRET_KEY = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento-trocar-em-producao")

    # Proteção CSRF (Flask-WTF)
    WTF_CSRF_ENABLED = True

    # Sessão expira após período de inatividade (em segundos)
    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60  # 8 horas

    # --- Banco de dados ---
    DATABASE_PATH = str(DATABASE_PATH)

    # --- Pastas do projeto ---
    # Expostas também como atributos de classe (além das variáveis de
    # módulo acima) para que `database/services.py` possa importar apenas
    # `from config import Config` e usar `Config.FOTOS_DIR`, `Config.BACKUPS_DIR`
    # etc. de forma consistente com o restante das configurações.
    FOTOS_DIR = FOTOS_DIR
    SALAS_DIR = SALAS_DIR
    UPLOADS_DIR = UPLOADS_DIR
    LOGOS_DIR = LOGOS_DIR
    ICONS_DIR = ICONS_DIR
    BACKUPS_DIR = BACKUPS_DIR
    LOGS_DIR = LOGS_DIR

    # --- Upload de fotos ---
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB por requisição
    EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp"}
    FOTO_TAMANHO_MAX = (600, 600)   # redimensionamento máximo (compressão)
    FOTO_QUALIDADE = 82             # qualidade JPEG (0-100)
    FOTO_PADRAO = "img/icons/default_avatar.png"  # caminho (relativo a /static) usado quando o aluno não tem foto

    # --- Identidade visual da instituição ---
    NOME_INSTITUICAO = os.environ.get("NOME_INSTITUICAO", "Minha Instituição de Ensino")
    COR_MENU = "#164194"
    COR_FOOTER = "#6CC2BA"
    VERSAO_SISTEMA = "1.0.0"

    # --- Narração (valores padrão, ajustáveis na tela de configurações) ---
    NARRACAO_IDIOMA_PADRAO = "pt-BR"
    NARRACAO_REPETICOES = 2

    # --- Socket.IO ---
    SOCKETIO_ASYNC_MODE = "eventlet"

    # --- Backup automático ---
    BACKUP_INTERVALO_HORAS = 24
    BACKUP_MANTER_ULTIMOS = 30  # quantidade de backups mantidos no histórico


class DevelopmentConfig(Config):
    """Ambiente de desenvolvimento local."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Ambiente de produção (Nginx + Gunicorn ou Windows Server)."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # exige HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


# Mapa usado pelo app.py para escolher a configuração via variável de ambiente
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    """Retorna a classe de configuração conforme FLASK_ENV (padrão: development)."""
    ambiente = os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(ambiente, DevelopmentConfig)
