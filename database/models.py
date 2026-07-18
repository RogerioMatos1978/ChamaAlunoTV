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
# Dividido em duas partes (TABLES_SQL / INDEXES_SQL) de propósito: os
# índices referenciam colunas (ex.: alunos.ativo) que só existem de fato
# em bancos de dados NOVOS — em bancos já existentes, essas colunas só
# passam a existir depois que `_migrar_colunas_novas()` roda o `ALTER
# TABLE`. Se os índices fossem criados no mesmo script que as tabelas,
# `CREATE INDEX ... ON alunos(ativo)` falharia em qualquer instalação
# que já tivesse o banco criado por uma versão anterior do sistema
# (a tabela já existe, então `CREATE TABLE IF NOT EXISTS` não faz nada,
# e a coluna nova ainda não existe nesse ponto). Por isso `init_db()`
# executa: TABLES_SQL -> migração de colunas -> INDEXES_SQL, nessa ordem.
TABLES_SQL = """
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

-- Anos letivos: cada aluno fica vinculado a um ano letivo (Módulo 12).
-- Apenas um deles é o "ano letivo atual" (controlado via a tabela
-- `configuracoes`, chave 'ano_letivo_atual_id'), usado como padrão ao
-- cadastrar um novo aluno.
CREATE TABLE IF NOT EXISTS anos_letivos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL UNIQUE,     -- ex.: "2026"
    data_inicio     TEXT,
    data_fim        TEXT,
    ativo           INTEGER NOT NULL DEFAULT 1,  -- pode ser selecionado nos cadastros
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
    foto            TEXT,                       -- apenas o nome do arquivo (Módulo 12)
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
    ativo           INTEGER NOT NULL DEFAULT 1, -- 0 = inativo (transferido para outra escola)
    ano_letivo_id   INTEGER REFERENCES anos_letivos(id) ON DELETE SET NULL,
    data_cadastro   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Presença diária dos alunos, vinculada ao ano letivo (Módulo 12).
-- Não é necessário criar um registro para todo aluno todo dia: a
-- ausência de registro em um dia é interpretada como "presente" (só é
-- preciso marcar explicitamente quem faltou), o que evita obrigar o
-- usuário padrão a confirmar presença de todos, todos os dias.
CREATE TABLE IF NOT EXISTS presencas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id        INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
    ano_letivo_id   INTEGER REFERENCES anos_letivos(id) ON DELETE SET NULL,
    data            TEXT NOT NULL,              -- 'AAAA-MM-DD'
    status          TEXT NOT NULL DEFAULT 'presente'
                        CHECK (status IN ('presente', 'faltante')),
    registrado_por  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(aluno_id, data)
);

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
"""

# Índices — executados DEPOIS da migração de colunas (veja o comentário
# acima de TABLES_SQL), já que alguns referenciam colunas que só passam
# a existir em bancos antigos após o `ALTER TABLE`.
INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_alunos_sala   ON alunos(sala_id);
CREATE INDEX IF NOT EXISTS idx_alunos_status ON alunos(status);
CREATE INDEX IF NOT EXISTS idx_alunos_codigo ON alunos(codigo);
CREATE INDEX IF NOT EXISTS idx_alunos_ativo  ON alunos(ativo);
CREATE INDEX IF NOT EXISTS idx_alunos_ano_letivo ON alunos(ano_letivo_id);
CREATE INDEX IF NOT EXISTS idx_presencas_data  ON presencas(data);
CREATE INDEX IF NOT EXISTS idx_presencas_aluno ON presencas(aluno_id);
CREATE INDEX IF NOT EXISTS idx_chamadas_horario ON chamadas(horario);
CREATE INDEX IF NOT EXISTS idx_chamadas_aluno   ON chamadas(aluno_id);
CREATE INDEX IF NOT EXISTS idx_logs_tipo ON logs_auditoria(tipo);
CREATE INDEX IF NOT EXISTS idx_logs_data ON logs_auditoria(criado_em);
"""


def init_db():
    """
    Cria todas as tabelas do sistema caso ainda não existam.

    Seguro para ser chamado toda vez que a aplicação inicia: `CREATE TABLE
    IF NOT EXISTS` nunca apaga dados já existentes. A ordem importa: tabelas
    -> migração de colunas novas -> índices (veja o comentário acima de
    `TABLES_SQL` para o motivo).
    """
    with db_session() as conn:
        conn.executescript(TABLES_SQL)
    _migrar_colunas_novas()
    with db_session() as conn:
        conn.executescript(INDEXES_SQL)


# ---------------------------------------------------------------------------
# Migração segura de colunas novas (Módulo 12)
# ---------------------------------------------------------------------------
# `CREATE TABLE IF NOT EXISTS` não adiciona colunas a tabelas que já
# existem em um banco de dados criado por uma versão anterior do
# sistema. Para que instalações já em uso ganhem as novas colunas sem
# perder nenhum dado, cada `ALTER TABLE` é tentado individualmente e
# qualquer erro (coluna já existente, banco recém-criado que já nasceu
# com a coluna, etc.) é silenciosamente ignorado.
_COLUNAS_NOVAS = (
    ("alunos", "ativo", "INTEGER NOT NULL DEFAULT 1"),
    ("alunos", "ano_letivo_id", "INTEGER REFERENCES anos_letivos(id) ON DELETE SET NULL"),
    ("salas", "foto", "TEXT"),
)


def _migrar_colunas_novas():
    """Aplica `ALTER TABLE ... ADD COLUMN` em bancos de dados já existentes."""
    with db_session() as conn:
        for tabela, coluna, definicao in _COLUNAS_NOVAS:
            try:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
            except sqlite3.OperationalError:
                pass  # coluna já existe — nada a fazer
