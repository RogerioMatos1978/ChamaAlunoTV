"""
database/models.py
===================
Definição do esquema (schema) do banco de dados SQLite.

Este módulo NÃO executa nenhuma consulta de negócio (isso é
responsabilidade de `services.py`). Aqui só existe:

    1. A função `get_connection()` — abre uma conexão SQLite padronizada.
    2. A função `init_db()` — cria todas as tabelas caso não existam.

O esquema foi desenhado em SQL "puro" (sem ORM) para manter o projeto
simples, mas todos os nomes de colunas e tipos foram escolhidos para
facilitar uma futura migração para MariaDB/MySQL/PostgreSQL.
"""

import sqlite3
from contextlib import contextmanager

from config import Config


def get_connection():
    """
    Abre e retorna uma conexão SQLite configurada.

    - `row_factory = sqlite3.Row` permite acessar colunas por nome
      (ex.: linha["nome"]) em vez de índice numérico, o que deixa o
      código muito mais legível.
    - `PRAGMA foreign_keys = ON` garante que as relações entre tabelas
      (ex.: aluno -> sala) sejam respeitadas pelo próprio banco.
    """
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    """
    Context manager para uso em `with db_session() as conn:`.

    Garante commit automático em caso de sucesso e rollback em caso
    de exceção, além de sempre fechar a conexão corretamente.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Esquema do banco de dados
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
-- Unidades: suporte a múltiplas unidades/campi da mesma instituição.
CREATE TABLE IF NOT EXISTS unidades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    endereco        TEXT,
    ativa           INTEGER NOT NULL DEFAULT 1,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Usuários do sistema (administrador, operador, supervisor).
CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    usuario         TEXT NOT NULL UNIQUE,      -- login (username)
    email           TEXT,
    senha_hash      TEXT NOT NULL,
    perfil          TEXT NOT NULL DEFAULT 'operador'
                        CHECK (perfil IN ('administrador', 'supervisor', 'operador')),
    unidade_id      INTEGER REFERENCES unidades(id) ON DELETE SET NULL,
    ativo           INTEGER NOT NULL DEFAULT 1,
    ultimo_login    TEXT,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Salas de atendimento/chamada.
CREATE TABLE IF NOT EXISTS salas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    descricao       TEXT,
    cor             TEXT NOT NULL DEFAULT '#164194',
    ordem           INTEGER NOT NULL DEFAULT 0,
    ativa           INTEGER NOT NULL DEFAULT 1,
    observacoes     TEXT,
    unidade_id      INTEGER REFERENCES unidades(id) ON DELETE SET NULL,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(nome, unidade_id)
);

-- Alunos.
CREATE TABLE IF NOT EXISTS alunos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    turma           TEXT,
    sala_id         INTEGER REFERENCES salas(id) ON DELETE SET NULL,
    foto            TEXT,                       -- apenas o nome do arquivo, ex.: aluno_1_1.jpg
    codigo          TEXT,                       -- código/matrícula (usado na importação CSV)
    cpf             TEXT,
    observacoes     TEXT,
    prioridade      INTEGER NOT NULL DEFAULT 0, -- 0 = normal, 1 = prioridade
    status          TEXT NOT NULL DEFAULT 'aguardando'
                        CHECK (status IN ('aguardando', 'chamado')),
    data_cadastro   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_alunos_sala   ON alunos(sala_id);
CREATE INDEX IF NOT EXISTS idx_alunos_status ON alunos(status);
CREATE INDEX IF NOT EXISTS idx_alunos_codigo ON alunos(codigo);

-- Histórico de chamadas (cada chamada gera um registro permanente,
-- mesmo que o aluno seja excluído depois).
CREATE TABLE IF NOT EXISTS chamadas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id        INTEGER REFERENCES alunos(id) ON DELETE SET NULL,
    aluno_nome      TEXT NOT NULL,   -- snapshot: preserva o nome mesmo se o aluno mudar/for excluído
    turma           TEXT,
    sala_nome       TEXT,
    foto            TEXT,
    operador_id     INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    operador_nome   TEXT,
    guiche          TEXT,                -- identificação do guichê/balcão, se houver
    tipo            TEXT NOT NULL DEFAULT 'chamada'
                        CHECK (tipo IN ('chamada', 'rechamada', 'manual')),
    ip_operador     TEXT,
    horario         TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_chamadas_horario ON chamadas(horario);
CREATE INDEX IF NOT EXISTS idx_chamadas_aluno   ON chamadas(aluno_id);

-- Configurações gerais do sistema (chave/valor), usada por narração,
-- tema, sons, etc. Mantém o sistema flexível sem precisar alterar o schema.
CREATE TABLE IF NOT EXISTS configuracoes (
    chave           TEXT PRIMARY KEY,
    valor           TEXT,
    descricao       TEXT,
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Log de auditoria: login, erros, chamadas, importações, alterações.
CREATE TABLE IF NOT EXISTS logs_auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT NOT NULL,     -- 'login', 'erro', 'chamada', 'importacao', 'alteracao'
    mensagem        TEXT NOT NULL,
    usuario_id      INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_nome    TEXT,
    ip              TEXT,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_logs_tipo ON logs_auditoria(tipo);
CREATE INDEX IF NOT EXISTS idx_logs_data ON logs_auditoria(criado_em);
"""


def init_db():
    """
    Cria todas as tabelas do sistema caso ainda não existam.

    Seguro para ser chamado toda vez que a aplicação inicia: `CREATE TABLE
    IF NOT EXISTS` nunca apaga dados já existentes.
    """
    with db_session() as conn:
        conn.executescript(SCHEMA_SQL)
