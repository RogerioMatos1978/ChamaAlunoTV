"""
database/services.py
=====================
Camada de serviços (regras de negócio + acesso a dados).

Este arquivo cresce ao longo dos módulos do projeto. Contém, por
enquanto:

    - Configurações do sistema (chave/valor)
    - Log de auditoria
    - Usuários e autenticação (Módulo 2)
    - Salas e estatísticas do dashboard (Módulo 3)
    - Alunos e importação CSV (Módulo 4)
    - Chamadas em tempo real (Módulo 5)
    - Histórico e exportações (Módulo 8)
    - Usuários (gestão completa), backup e auditoria (Módulo 10)
"""

import io
import os
import shutil
from datetime import datetime

import pandas as pd
from PIL import Image
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from database.models import db_session

# Perfis de acesso válidos no sistema. Mantidos em um único lugar para
# que qualquer validação (formulário, decorator, etc.) reaproveite esta lista.
PERFIS_VALIDOS = ("administrador", "supervisor", "operador")


# ---------------------------------------------------------------------------
# Configurações (tabela chave/valor)
# ---------------------------------------------------------------------------
def get_configuracao(chave: str, padrao=None):
    """Lê uma configuração do banco. Retorna `padrao` se não existir."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
        ).fetchone()
        return row["valor"] if row else padrao


def set_configuracao(chave: str, valor, descricao: str = None):
    """Cria ou atualiza uma configuração (UPSERT)."""
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO configuracoes (chave, valor, descricao, atualizado_em)
            VALUES (?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(chave) DO UPDATE SET
                valor = excluded.valor,
                descricao = COALESCE(excluded.descricao, configuracoes.descricao),
                atualizado_em = datetime('now', 'localtime')
            """,
            (chave, str(valor), descricao),
        )


# ---------------------------------------------------------------------------
# Log de auditoria
# ---------------------------------------------------------------------------
def registrar_log(tipo: str, mensagem: str, usuario_id: int = None,
                   usuario_nome: str = None, ip: str = None):
    """
    Registra uma entrada de auditoria.

    Tipos usados pelo sistema: 'login', 'erro', 'chamada',
    'importacao', 'alteracao'. Mantido genérico de propósito, para que
    qualquer módulo futuro possa registrar eventos sem precisar alterar
    o schema do banco.
    """
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO logs_auditoria (tipo, mensagem, usuario_id, usuario_nome, ip)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tipo, mensagem, usuario_id, usuario_nome, ip),
        )


def listar_logs(tipo: str = None, limite: int = 200):
    """Lista as entradas de auditoria mais recentes, com filtro opcional por tipo."""
    with db_session() as conn:
        if tipo:
            cursor = conn.execute(
                "SELECT * FROM logs_auditoria WHERE tipo = ? ORDER BY criado_em DESC LIMIT ?",
                (tipo, limite),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM logs_auditoria ORDER BY criado_em DESC LIMIT ?",
                (limite,),
            )
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Usuários e autenticação
# ---------------------------------------------------------------------------
def contar_usuarios() -> int:
    """Usado no startup para saber se é necessário criar o usuário admin padrão."""
    with db_session() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM usuarios").fetchone()
        return row["total"]


def criar_usuario(nome: str, usuario: str, senha: str, perfil: str = "operador",
                   email: str = None, unidade_id: int = None) -> int:
    """
    Cria um novo usuário com a senha já criptografada (Werkzeug/PBKDF2).

    Nunca armazenamos a senha em texto puro — apenas o hash gerado por
    `generate_password_hash`. Retorna o id do usuário criado.
    """
    if perfil not in PERFIS_VALIDOS:
        raise ValueError(f"Perfil inválido: {perfil}. Use um de {PERFIS_VALIDOS}.")

    senha_hash = generate_password_hash(senha)
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO usuarios (nome, usuario, email, senha_hash, perfil, unidade_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, usuario, email, senha_hash, perfil, unidade_id),
        )
        return cursor.lastrowid


def obter_usuario_por_login(usuario: str):
    """Busca um usuário pelo campo de login (`usuario`). Retorna dict ou None."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
        return dict(row) if row else None


def obter_usuario_por_id(usuario_id: int):
    """Busca um usuário pelo id. Retorna dict ou None."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        return dict(row) if row else None


def autenticar_usuario(usuario: str, senha: str):
    """
    Valida usuário/senha.

    Retorna o dicionário do usuário em caso de sucesso, ou None se o
    login não existir, estiver inativo, ou a senha estiver incorreta.
    Nunca informa qual dos dois motivos causou a falha (login OU senha
    incorretos) — isso evita que alguém descubra quais logins existem
    no sistema por tentativa e erro.
    """
    dados = obter_usuario_por_login(usuario)
    if not dados or not dados["ativo"]:
        return None
    if not check_password_hash(dados["senha_hash"], senha):
        return None
    return dados


def atualizar_ultimo_login(usuario_id: int):
    """Registra o horário do login mais recente do usuário."""
    with db_session() as conn:
        conn.execute(
            "UPDATE usuarios SET ultimo_login = datetime('now', 'localtime') WHERE id = ?",
            (usuario_id,),
        )


def listar_usuarios():
    """Lista todos os usuários cadastrados (sem o hash de senha)."""
    with db_session() as conn:
        cursor = conn.execute(
            """
            SELECT id, nome, usuario, email, perfil, unidade_id, ativo, ultimo_login, criado_em
            FROM usuarios ORDER BY nome
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def contar_administradores_ativos(ignorar_id: int = None) -> int:
    """
    Conta quantos administradores ativos existem — usado para impedir que
    o último administrador do sistema seja desativado/excluído por engano
    (o que deixaria o sistema sem ninguém para gerenciá-lo).
    """
    with db_session() as conn:
        if ignorar_id:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM usuarios WHERE perfil = 'administrador' AND ativo = 1 AND id != ?",
                (ignorar_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM usuarios WHERE perfil = 'administrador' AND ativo = 1"
            ).fetchone()
        return row["n"]


def existe_login_usuario(usuario: str, ignorar_id: int = None) -> bool:
    """Verifica se já existe outro usuário com o mesmo login."""
    with db_session() as conn:
        if ignorar_id:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE usuario = ? AND id != ?", (usuario, ignorar_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        return row is not None


def atualizar_usuario(usuario_id: int, nome: str, email: str = None,
                       perfil: str = "operador", ativo: bool = True):
    """Atualiza os dados cadastrais de um usuário (não altera a senha)."""
    if perfil not in PERFIS_VALIDOS:
        raise ValueError(f"Perfil inválido: {perfil}. Use um de {PERFIS_VALIDOS}.")
    with db_session() as conn:
        conn.execute(
            "UPDATE usuarios SET nome = ?, email = ?, perfil = ?, ativo = ? WHERE id = ?",
            (nome, email, perfil, int(ativo), usuario_id),
        )


def alterar_senha_usuario(usuario_id: int, nova_senha: str):
    """Define uma nova senha para o usuário (sempre armazenada como hash)."""
    with db_session() as conn:
        conn.execute(
            "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
            (generate_password_hash(nova_senha), usuario_id),
        )


def excluir_usuario(usuario_id: int):
    """Remove um usuário do sistema (o histórico de chamadas preserva o nome do operador por snapshot)."""
    with db_session() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))


def seed_admin_padrao():
    """
    Cria o usuário administrador padrão na primeira execução do sistema
    (quando a tabela `usuarios` está vazia).

    Login:  admin
    Senha:  admin123

    Este login/senha DEVE ser trocado no primeiro acesso em um ambiente
    real — a tela de "Página de usuários" (módulo de extras) permitirá
    alterar a senha pela interface.
    """
    if contar_usuarios() == 0:
        criar_usuario(
            nome="Administrador",
            usuario="admin",
            senha="admin123",
            perfil="administrador",
        )
        registrar_log(
            tipo="alteracao",
            mensagem="Usuário administrador padrão criado automaticamente (login: admin).",
        )


# ---------------------------------------------------------------------------
# Salas
# ---------------------------------------------------------------------------
def listar_salas(apenas_ativas: bool = False):
    """
    Lista as salas cadastradas, ordenadas pelo campo `ordem` e depois pelo
    nome. Também traz a contagem de alunos aguardando em cada sala — útil
    tanto para a tela de administração quanto para o kiosk (Módulo 5).
    """
    with db_session() as conn:
        filtro = "WHERE s.ativa = 1" if apenas_ativas else ""
        cursor = conn.execute(
            f"""
            SELECT s.*,
                   COUNT(a.id) FILTER (WHERE a.status = 'aguardando') AS alunos_aguardando
            FROM salas s
            LEFT JOIN alunos a ON a.sala_id = s.id
            {filtro}
            GROUP BY s.id
            ORDER BY s.ordem ASC, s.nome ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def obter_sala(sala_id: int):
    """Busca uma sala pelo id. Retorna dict ou None."""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM salas WHERE id = ?", (sala_id,)).fetchone()
        return dict(row) if row else None


def criar_sala(nome: str, descricao: str = None, cor: str = "#164194",
                ordem: int = 0, ativa: bool = True, observacoes: str = None,
                unidade_id: int = None) -> int:
    """Cria uma nova sala. Retorna o id gerado."""
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO salas (nome, descricao, cor, ordem, ativa, observacoes, unidade_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nome, descricao, cor, ordem, int(ativa), observacoes, unidade_id),
        )
        return cursor.lastrowid


def atualizar_sala(sala_id: int, nome: str, descricao: str = None, cor: str = "#164194",
                    ordem: int = 0, ativa: bool = True, observacoes: str = None):
    """Atualiza os dados de uma sala existente."""
    with db_session() as conn:
        conn.execute(
            """
            UPDATE salas
               SET nome = ?, descricao = ?, cor = ?, ordem = ?, ativa = ?, observacoes = ?
             WHERE id = ?
            """,
            (nome, descricao, cor, ordem, int(ativa), observacoes, sala_id),
        )


def excluir_sala(sala_id: int):
    """
    Exclui uma sala. Os alunos vinculados NÃO são apagados — o campo
    `sala_id` deles simplesmente fica nulo (ON DELETE SET NULL no schema),
    evitando perda acidental de dados de alunos.
    """
    with db_session() as conn:
        conn.execute("DELETE FROM salas WHERE id = ?", (sala_id,))


def existe_nome_sala(nome: str, ignorar_id: int = None) -> bool:
    """Verifica se já existe outra sala com o mesmo nome (evita duplicidade)."""
    with db_session() as conn:
        if ignorar_id:
            row = conn.execute(
                "SELECT 1 FROM salas WHERE nome = ? AND id != ?", (nome, ignorar_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT 1 FROM salas WHERE nome = ?", (nome,)).fetchone()
        return row is not None


# ---------------------------------------------------------------------------
# Estatísticas do Dashboard
# ---------------------------------------------------------------------------
def obter_estatisticas_dashboard():
    """
    Reúne os indicadores exibidos no Dashboard administrativo:

        - total_alunos:        total de alunos cadastrados
        - total_salas:         total de salas ativas
        - alunos_aguardando:   alunos ainda não chamados
        - alunos_chamados:     alunos já chamados (histórico total)
        - chamadas_hoje:       quantas chamadas ocorreram hoje
        - tempo_medio_minutos: tempo médio (cadastro -> chamada) hoje, em minutos
        - ultimo_chamado:      dict com dados da chamada mais recente (ou None)
        - alunos_por_sala:     lista [{sala, cor, total}] para o gráfico simples
    """
    with db_session() as conn:
        total_alunos = conn.execute("SELECT COUNT(*) AS n FROM alunos").fetchone()["n"]
        total_salas = conn.execute("SELECT COUNT(*) AS n FROM salas WHERE ativa = 1").fetchone()["n"]
        alunos_aguardando = conn.execute(
            "SELECT COUNT(*) AS n FROM alunos WHERE status = 'aguardando'"
        ).fetchone()["n"]
        alunos_chamados = conn.execute(
            "SELECT COUNT(*) AS n FROM alunos WHERE status = 'chamado'"
        ).fetchone()["n"]
        chamadas_hoje = conn.execute(
            "SELECT COUNT(*) AS n FROM chamadas WHERE date(horario) = date('now', 'localtime')"
        ).fetchone()["n"]

        # Tempo médio de espera (do cadastro do aluno até a chamada), apenas de hoje.
        tempo_medio_row = conn.execute(
            """
            SELECT AVG(
                (julianday(c.horario) - julianday(a.data_cadastro)) * 24 * 60
            ) AS media_minutos
            FROM chamadas c
            JOIN alunos a ON a.id = c.aluno_id
            WHERE date(c.horario) = date('now', 'localtime')
            """
        ).fetchone()
        tempo_medio = tempo_medio_row["media_minutos"]

        ultimo = conn.execute(
            "SELECT aluno_nome, sala_nome, horario FROM chamadas ORDER BY horario DESC LIMIT 1"
        ).fetchone()

        alunos_por_sala = conn.execute(
            """
            SELECT s.nome AS sala, s.cor AS cor, COUNT(a.id) AS total
            FROM salas s
            LEFT JOIN alunos a ON a.sala_id = s.id AND a.status = 'aguardando'
            WHERE s.ativa = 1
            GROUP BY s.id
            ORDER BY s.ordem ASC
            """
        ).fetchall()

        return {
            "total_alunos": total_alunos,
            "total_salas": total_salas,
            "alunos_aguardando": alunos_aguardando,
            "alunos_chamados": alunos_chamados,
            "chamadas_hoje": chamadas_hoje,
            "tempo_medio_minutos": round(tempo_medio, 1) if tempo_medio else None,
            "ultimo_chamado": dict(ultimo) if ultimo else None,
            "alunos_por_sala": [dict(row) for row in alunos_por_sala],
        }


# ---------------------------------------------------------------------------
# Alunos
# ---------------------------------------------------------------------------
def listar_alunos(sala_id: int = None, status: str = None, busca: str = None,
                   ordenar_por: str = "nome"):
    """
    Lista alunos com filtros opcionais. Usada pela tela administrativa de
    alunos (Módulo 4) e reaproveitada pelas telas de Kiosk e Presença
    (Módulos 5 e 7).

    `ordenar_por`:
        - "nome" (padrão): ordem alfabética — ideal para telas de busca/admin.
        - "fila": prioridade e depois ordem de chegada (FIFO) — ideal para
          o Kiosk, onde a ordem de atendimento importa.
    """
    condicoes = []
    parametros = []

    if sala_id:
        condicoes.append("a.sala_id = ?")
        parametros.append(sala_id)
    if status:
        condicoes.append("a.status = ?")
        parametros.append(status)
    if busca:
        condicoes.append("(a.nome LIKE ? OR a.turma LIKE ? OR a.codigo LIKE ?)")
        termo = f"%{busca}%"
        parametros.extend([termo, termo, termo])

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    ordenacao = (
        "a.prioridade DESC, a.data_cadastro ASC"
        if ordenar_por == "fila"
        else "a.prioridade DESC, a.nome ASC"
    )

    with db_session() as conn:
        cursor = conn.execute(
            f"""
            SELECT a.*, s.nome AS sala_nome, s.cor AS sala_cor
            FROM alunos a
            LEFT JOIN salas s ON s.id = a.sala_id
            {where}
            ORDER BY {ordenacao}
            """,
            parametros,
        )
        return [dict(row) for row in cursor.fetchall()]


def obter_aluno(aluno_id: int):
    """Busca um aluno pelo id, já com o nome da sala. Retorna dict ou None."""
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT a.*, s.nome AS sala_nome, s.cor AS sala_cor
            FROM alunos a
            LEFT JOIN salas s ON s.id = a.sala_id
            WHERE a.id = ?
            """,
            (aluno_id,),
        ).fetchone()
        return dict(row) if row else None


def criar_aluno(nome: str, turma: str = None, sala_id: int = None, foto: str = None,
                 codigo: str = None, cpf: str = None, observacoes: str = None,
                 prioridade: int = 0) -> int:
    """Cria um novo aluno com status inicial 'aguardando'. Retorna o id gerado."""
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO alunos (nome, turma, sala_id, foto, codigo, cpf, observacoes, prioridade, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'aguardando')
            """,
            (nome, turma, sala_id, foto, codigo, cpf, observacoes, int(prioridade)),
        )
        return cursor.lastrowid


def atualizar_aluno(aluno_id: int, nome: str, turma: str = None, sala_id: int = None,
                     foto: str = None, codigo: str = None, cpf: str = None,
                     observacoes: str = None, prioridade: int = 0):
    """Atualiza os dados cadastrais de um aluno existente."""
    with db_session() as conn:
        conn.execute(
            """
            UPDATE alunos
               SET nome = ?, turma = ?, sala_id = ?, foto = ?, codigo = ?, cpf = ?,
                   observacoes = ?, prioridade = ?, atualizado_em = datetime('now', 'localtime')
             WHERE id = ?
            """,
            (nome, turma, sala_id, foto, codigo, cpf, observacoes, int(prioridade), aluno_id),
        )


def atualizar_foto_aluno(aluno_id: int, foto: str):
    """Atualiza apenas o nome do arquivo de foto de um aluno."""
    with db_session() as conn:
        conn.execute(
            "UPDATE alunos SET foto = ?, atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (foto, aluno_id),
        )


def excluir_aluno(aluno_id: int):
    """Remove um aluno permanentemente (o histórico de chamadas é preservado por snapshot)."""
    with db_session() as conn:
        conn.execute("DELETE FROM alunos WHERE id = ?", (aluno_id,))


def redefinir_fila_aluno(aluno_id: int):
    """Retorna um aluno já chamado para a fila de espera (usado em 'rechamar' no Módulo 5)."""
    with db_session() as conn:
        conn.execute(
            "UPDATE alunos SET status = 'aguardando', atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (aluno_id,),
        )


def buscar_aluno_por_nome_turma(nome: str, turma: str):
    """
    Localiza um aluno pelo par (nome, turma), ignorando maiúsculas/minúsculas
    e espaços nas pontas. Usado pela importação CSV para não duplicar alunos.
    """
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT * FROM alunos
            WHERE TRIM(LOWER(nome)) = TRIM(LOWER(?))
              AND TRIM(LOWER(COALESCE(turma, ''))) = TRIM(LOWER(COALESCE(?, '')))
            """,
            (nome, turma),
        ).fetchone()
        return dict(row) if row else None


def obter_ou_criar_sala_por_nome(nome_sala: str) -> int:
    """
    Usado pela importação CSV: retorna o id da sala com esse nome, criando
    automaticamente uma nova sala (ativa, cor padrão) caso ela ainda não exista.
    """
    nome_sala = (nome_sala or "").strip()
    with db_session() as conn:
        row = conn.execute(
            "SELECT id FROM salas WHERE TRIM(LOWER(nome)) = TRIM(LOWER(?))", (nome_sala,)
        ).fetchone()
        if row:
            return row["id"]

        # Próxima ordem disponível, para a nova sala aparecer no final da lista.
        maior_ordem = conn.execute("SELECT COALESCE(MAX(ordem), -1) AS m FROM salas").fetchone()["m"]
        cursor = conn.execute(
            "INSERT INTO salas (nome, cor, ordem, ativa) VALUES (?, ?, ?, 1)",
            (nome_sala, "#164194", maior_ordem + 1),
        )
        return cursor.lastrowid


def importar_alunos_csv(linhas: list) -> dict:
    """
    Importa alunos a partir de uma lista de dicionários já normalizados
    (chaves: 'aluno', 'serie', 'sala', 'foto'), no formato definido pela
    especificação do sistema:

        aluno;serie;sala;foto

    Regras:
        - Salas citadas que não existem são criadas automaticamente.
        - Alunos já existentes (mesmo nome + série) são ATUALIZADOS, não duplicados.
        - Linhas sem nome de aluno são ignoradas e contabilizadas como erro.

    Retorna um resumo: {criados, atualizados, salas_criadas, ignorados}.
    """
    resumo = {"criados": 0, "atualizados": 0, "salas_criadas": 0, "ignorados": 0}
    salas_existentes_antes = {s["nome"].strip().lower() for s in listar_salas()}

    for linha in linhas:
        nome = (linha.get("aluno") or "").strip()
        turma = (linha.get("serie") or "").strip() or None
        nome_sala = (linha.get("sala") or "").strip()
        foto = (linha.get("foto") or "").strip() or None

        if not nome:
            resumo["ignorados"] += 1
            continue

        sala_id = None
        if nome_sala:
            sala_id = obter_ou_criar_sala_por_nome(nome_sala)
            if nome_sala.lower() not in salas_existentes_antes:
                resumo["salas_criadas"] += 1
                salas_existentes_antes.add(nome_sala.lower())

        existente = buscar_aluno_por_nome_turma(nome, turma)
        if existente:
            atualizar_aluno(
                existente["id"], nome=nome, turma=turma, sala_id=sala_id,
                foto=foto or existente["foto"], codigo=existente["codigo"],
                cpf=existente["cpf"], observacoes=existente["observacoes"],
                prioridade=existente["prioridade"],
            )
            resumo["atualizados"] += 1
        else:
            criar_aluno(nome=nome, turma=turma, sala_id=sala_id, foto=foto)
            resumo["criados"] += 1

    return resumo


# ---------------------------------------------------------------------------
# Fotos dos alunos (upload, compressão e resolução de URL)
# ---------------------------------------------------------------------------
def extensao_permitida(nome_arquivo: str) -> bool:
    """Verifica se a extensão do arquivo enviado é uma das aceitas pelo sistema."""
    return (
        "." in nome_arquivo
        and nome_arquivo.rsplit(".", 1)[1].lower() in Config.EXTENSOES_PERMITIDAS
    )


def salvar_foto_aluno(arquivo_upload, aluno_id: int) -> str:
    """
    Recebe um arquivo enviado (werkzeug FileStorage), comprime/redimensiona
    com Pillow e salva em static/fotos/ com um nome padronizado e seguro.

    - No banco de dados é gravado APENAS o nome do arquivo (ex.: "aluno_7.jpg"),
      nunca o caminho completo — conforme exigido pela especificação.
    - Qualquer foto anterior desse aluno (com extensão diferente) é removida,
      para não acumular arquivos órfãos.

    Retorna o nome do arquivo salvo.
    """
    extensao_original = secure_filename(arquivo_upload.filename).rsplit(".", 1)[-1].lower()
    if extensao_original not in Config.EXTENSOES_PERMITIDAS:
        raise ValueError("Formato de imagem não suportado.")

    # Remove eventuais fotos antigas do aluno (extensões diferentes da atual).
    for extensao in Config.EXTENSOES_PERMITIDAS:
        caminho_antigo = Config.FOTOS_DIR / f"aluno_{aluno_id}.{extensao}"
        if caminho_antigo.exists():
            caminho_antigo.unlink()

    # Padroniza sempre para .jpg após a compressão (menor tamanho de arquivo).
    nome_arquivo = f"aluno_{aluno_id}.jpg"
    caminho_destino = Config.FOTOS_DIR / nome_arquivo

    imagem = Image.open(arquivo_upload.stream)
    imagem = imagem.convert("RGB")  # remove transparência/paleta antes de salvar como JPEG
    imagem.thumbnail(Config.FOTO_TAMANHO_MAX)  # redimensiona mantendo proporção
    imagem.save(caminho_destino, "JPEG", quality=Config.FOTO_QUALIDADE, optimize=True)

    return nome_arquivo


def excluir_foto_aluno(nome_arquivo: str):
    """Remove o arquivo de foto do disco, se existir. Usado ao excluir um aluno."""
    if not nome_arquivo:
        return
    caminho = Config.FOTOS_DIR / nome_arquivo
    if caminho.exists():
        try:
            caminho.unlink()
        except OSError:
            pass  # não interrompe a operação principal por falha ao apagar um arquivo


def resolver_caminho_foto(nome_arquivo: str) -> str:
    """
    Resolve o caminho (relativo a /static) usado no atributo `src` das
    imagens: a foto do aluno, se existir no disco, ou a imagem padrão.
    """
    if nome_arquivo and (Config.FOTOS_DIR / nome_arquivo).exists():
        return f"fotos/{nome_arquivo}"
    return Config.FOTO_PADRAO


# ---------------------------------------------------------------------------
# Chamadas (Kiosk — Módulo 5)
# ---------------------------------------------------------------------------
def chamar_aluno(aluno_id: int, operador_id: int = None, operador_nome: str = None,
                  ip: str = None, guiche: str = None):
    """
    Executa a "chamada" de um aluno: marca como chamado e grava um
    registro permanente no histórico, em uma única transação.

    Retorna um dicionário com os dados da chamada (usado para narração
    e exibição na tela de TV), ou None se o aluno não existir ou já
    tiver sido chamado (evita chamadas duplicadas em cliques simultâneos).
    """
    with db_session() as conn:
        aluno = conn.execute(
            """
            SELECT a.*, s.nome AS sala_nome
            FROM alunos a
            LEFT JOIN salas s ON s.id = a.sala_id
            WHERE a.id = ?
            """,
            (aluno_id,),
        ).fetchone()

        if not aluno or aluno["status"] != "aguardando":
            return None

        conn.execute(
            "UPDATE alunos SET status = 'chamado', atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (aluno_id,),
        )
        cursor = conn.execute(
            """
            INSERT INTO chamadas
                (aluno_id, aluno_nome, turma, sala_nome, foto, operador_id, operador_nome,
                 guiche, tipo, ip_operador)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'chamada', ?)
            """,
            (aluno_id, aluno["nome"], aluno["turma"], aluno["sala_nome"], aluno["foto"],
             operador_id, operador_nome, guiche, ip),
        )
        chamada = conn.execute(
            "SELECT * FROM chamadas WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(chamada)


# ---------------------------------------------------------------------------
# Exportações do histórico (CSV, Excel, PDF) — Módulo 8
# ---------------------------------------------------------------------------
COLUNAS_EXPORTACAO = {
    "aluno_nome": "Aluno",
    "turma": "Turma",
    "sala_nome": "Sala",
    "horario": "Horário",
    "operador_nome": "Operador",
    "tipo": "Tipo",
    "ip_operador": "IP",
}


def _dataframe_historico(registros: list) -> pd.DataFrame:
    """Converte a lista de chamadas em um DataFrame já com colunas amigáveis."""
    df = pd.DataFrame(registros, columns=list(COLUNAS_EXPORTACAO.keys()))
    return df.rename(columns=COLUNAS_EXPORTACAO)


def gerar_csv_historico(registros: list) -> bytes:
    """Gera o conteúdo de um arquivo CSV (separado por ';') a partir do histórico."""
    df = _dataframe_historico(registros)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
    return buffer.getvalue().encode("utf-8-sig")


def gerar_excel_historico(registros: list) -> bytes:
    """Gera o conteúdo de um arquivo .xlsx a partir do histórico."""
    df = _dataframe_historico(registros)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Histórico")
        planilha = writer.sheets["Histórico"]
        for indice, coluna in enumerate(df.columns, start=1):
            largura = max(df[coluna].astype(str).map(len).max() if not df.empty else 0, len(coluna)) + 4
            planilha.column_dimensions[planilha.cell(row=1, column=indice).column_letter].width = largura
    return buffer.getvalue()


def gerar_pdf_historico(registros: list, titulo: str = "Histórico de Chamadas") -> bytes:
    """Gera um relatório em PDF (tabela) a partir do histórico, usando ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(titulo, estilos["Title"]), Spacer(1, 12)]

    cabecalho = list(COLUNAS_EXPORTACAO.values())
    linhas = [
        [str(registro.get(chave) or "—") for chave in COLUNAS_EXPORTACAO.keys()]
        for registro in registros
    ]
    dados_tabela = [cabecalho] + linhas if linhas else [cabecalho, ["Nenhum registro encontrado."] + [""] * (len(cabecalho) - 1)]

    tabela = Table(dados_tabela, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#164194")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e5eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabela)
    documento.build(elementos)
    return buffer.getvalue()


def listar_historico(busca: str = None, sala_nome: str = None, tipo: str = None,
                      data_inicio: str = None, data_fim: str = None, limite: int = 1000):
    """
    Lista o histórico de chamadas com filtros opcionais, usado pela tela
    de Histórico (Módulo 8) e pelas exportações (CSV/Excel/PDF).

    `data_inicio` e `data_fim` são strings no formato "AAAA-MM-DD".
    """
    condicoes = []
    parametros = []

    if busca:
        condicoes.append("(aluno_nome LIKE ? OR turma LIKE ? OR operador_nome LIKE ?)")
        termo = f"%{busca}%"
        parametros.extend([termo, termo, termo])
    if sala_nome:
        condicoes.append("sala_nome = ?")
        parametros.append(sala_nome)
    if tipo:
        condicoes.append("tipo = ?")
        parametros.append(tipo)
    if data_inicio:
        condicoes.append("date(horario) >= date(?)")
        parametros.append(data_inicio)
    if data_fim:
        condicoes.append("date(horario) <= date(?)")
        parametros.append(data_fim)

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    with db_session() as conn:
        cursor = conn.execute(
            f"""
            SELECT * FROM chamadas
            {where}
            ORDER BY horario DESC
            LIMIT ?
            """,
            (*parametros, limite),
        )
        return [dict(row) for row in cursor.fetchall()]


def obter_nomes_salas_no_historico():
    """Lista os nomes de sala distintos já registrados no histórico (para o filtro)."""
    with db_session() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT sala_nome FROM chamadas WHERE sala_nome IS NOT NULL ORDER BY sala_nome"
        )
        return [row["sala_nome"] for row in cursor.fetchall()]


def obter_chamada(chamada_id: int):
    """Busca um registro de chamada pelo id. Retorna dict ou None."""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM chamadas WHERE id = ?", (chamada_id,)).fetchone()
        return dict(row) if row else None


def listar_ultimas_chamadas_sala(sala_nome: str, limite: int = 6):
    """
    Lista as chamadas mais recentes de uma sala (usado pelo Kiosk para
    mostrar "Últimos chamados desta sala", com foto e nome do aluno já
    preservados, e um botão para repetir a chamada — Módulo 11).
    """
    if not sala_nome:
        return []
    with db_session() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM chamadas
            WHERE sala_nome = ? AND aluno_id IS NOT NULL
            ORDER BY horario DESC
            LIMIT ?
            """,
            (sala_nome, limite),
        )
        return [dict(row) for row in cursor.fetchall()]


def rechamar_aluno(aluno_id: int, operador_id: int = None, operador_nome: str = None,
                    ip: str = None, guiche: str = None):
    """
    Repete a chamada de um aluno que JÁ foi chamado anteriormente (ex.: o
    aluno não apareceu). Não altera o status do aluno — apenas gera um
    novo registro de histórico do tipo 'rechamada', que dispara uma nova
    narração e nova exibição na TV.
    """
    with db_session() as conn:
        aluno = conn.execute(
            """
            SELECT a.*, s.nome AS sala_nome
            FROM alunos a
            LEFT JOIN salas s ON s.id = a.sala_id
            WHERE a.id = ?
            """,
            (aluno_id,),
        ).fetchone()

        if not aluno:
            return None

        cursor = conn.execute(
            """
            INSERT INTO chamadas
                (aluno_id, aluno_nome, turma, sala_nome, foto, operador_id, operador_nome,
                 guiche, tipo, ip_operador)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'rechamada', ?)
            """,
            (aluno_id, aluno["nome"], aluno["turma"], aluno["sala_nome"], aluno["foto"],
             operador_id, operador_nome, guiche, ip),
        )
        chamada = conn.execute(
            "SELECT * FROM chamadas WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(chamada)


# ---------------------------------------------------------------------------
# Backup e restauração do banco de dados (Módulo 10)
# ---------------------------------------------------------------------------
def criar_backup() -> str:
    """
    Cria uma cópia de segurança do banco de dados em `backups/`, usando a
    API de backup nativa do SQLite (segura mesmo com o servidor em uso —
    ao contrário de uma simples cópia de arquivo, que poderia capturar o
    banco no meio de uma escrita).

    Também aplica a política de retenção (`BACKUP_MANTER_ULTIMOS`),
    apagando os backups mais antigos além do limite configurado.

    Retorna o nome do arquivo de backup criado.
    """
    import sqlite3

    Config.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"alunos_{carimbo}.db"
    caminho_destino = Config.BACKUPS_DIR / nome_arquivo

    origem = sqlite3.connect(Config.DATABASE_PATH)
    destino = sqlite3.connect(str(caminho_destino))
    with destino:
        origem.backup(destino)
    origem.close()
    destino.close()

    _aplicar_retencao_backups()
    return nome_arquivo


def _aplicar_retencao_backups():
    """Mantém apenas os `BACKUP_MANTER_ULTIMOS` backups mais recentes."""
    backups = sorted(Config.BACKUPS_DIR.glob("alunos_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antigo in backups[Config.BACKUP_MANTER_ULTIMOS:]:
        try:
            antigo.unlink()
        except OSError:
            pass


def listar_backups() -> list:
    """Lista os backups existentes, mais recentes primeiro, com tamanho e data."""
    if not Config.BACKUPS_DIR.exists():
        return []
    backups = sorted(Config.BACKUPS_DIR.glob("alunos_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "nome": p.name,
            "tamanho_kb": round(p.stat().st_size / 1024, 1),
            "criado_em": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
        }
        for p in backups
    ]


def restaurar_backup(nome_arquivo: str):
    """
    Restaura o banco de dados a partir de um arquivo de backup existente
    em `backups/`. ATENÇÃO: substitui todos os dados atuais.

    Antes de restaurar, um backup de segurança do estado atual é criado
    automaticamente (para permitir desfazer, se necessário).
    """
    nome_seguro = secure_filename(nome_arquivo)
    caminho_backup = Config.BACKUPS_DIR / nome_seguro
    if not caminho_backup.exists():
        raise FileNotFoundError("Arquivo de backup não encontrado.")

    criar_backup()  # salvaguarda do estado atual antes de sobrescrever
    shutil.copy2(caminho_backup, Config.DATABASE_PATH)
