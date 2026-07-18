"""
database/socket_events.py
==========================
Eventos Socket.IO (comunicação em tempo real entre servidor e telas).

Por que este arquivo mora em `database/` e não em `routes/`?
Porque os eventos aqui frequentemente disparam ações que leem/gravam
no banco (ex.: registrar uma chamada). Mantê-los junto da camada de
dados evita dependência circular com as rotas HTTP.

Eventos registrados:
    - connect / disconnect  -> ciclo de vida da conexão (Módulo 1)
    - chamar_aluno          -> executa a chamada de um aluno (Módulo 5)
    - rechamar_aluno        -> repete a chamada de um aluno (Módulo 5)

Todos os eventos que alteram dados fazem a alteração no banco e depois
usam `socketio.emit(...)` (sem `room=`) para transmitir o resultado a
TODAS as telas conectadas (Kiosk, Screen, Presença, Admin) — é assim
que o sistema fica sincronizado em tempo real, sem precisar recarregar
o navegador.
"""

from flask import request, session
from flask_socketio import SocketIO

from database.services import registrar_log, chamar_aluno, rechamar_aluno


def register_socket_events(socketio: SocketIO):
    """Registra todos os handlers de eventos Socket.IO na instância fornecida."""

    @socketio.on("connect")
    def handle_connect():
        """Disparado quando qualquer tela (kiosk, screen, admin, presença) conecta."""
        registrar_log(
            tipo="conexao",
            mensagem=f"Cliente conectado via WebSocket (sid={request.sid})",
        )

    @socketio.on("disconnect")
    def handle_disconnect():
        """Disparado quando uma tela perde a conexão ou é fechada."""
        # Não gravamos log de auditoria aqui para não poluir a tabela em
        # quedas de rede comuns (ex.: TV reiniciando). Mantido apenas
        # como ponto de extensão futuro.
        pass

    @socketio.on("chamar_aluno")
    def handle_chamar_aluno(dados):
        """
        Recebido do Kiosk quando o operador clica em "CHAMAR".

        `dados` esperado: {"aluno_id": <int>, "guiche": <str, opcional>}

        Fluxo (conforme especificação):
            1. Remove o aluno da fila (status -> 'chamado')
            2. Registra o histórico (tabela `chamadas`)
            3. Transmite o evento 'aluno_chamado' para TODAS as telas
               (Kiosk atualiza a lista, Screen exibe a foto e narra,
               Presença remove o aluno, Admin atualiza o dashboard)
        """
        aluno_id = dados.get("aluno_id") if dados else None
        if not aluno_id:
            socketio.emit("erro_chamada", {"mensagem": "Aluno inválido."}, to=request.sid)
            return

        operador_id = session.get("usuario_id")
        operador_nome = session.get("usuario_nome", "Operador")
        ip = request.remote_addr
        guiche = (dados or {}).get("guiche")

        chamada = chamar_aluno(aluno_id, operador_id, operador_nome, ip=ip, guiche=guiche)

        if chamada:
            registrar_log(
                tipo="chamada",
                mensagem=f"Aluno \"{chamada['aluno_nome']}\" chamado (sala: {chamada['sala_nome'] or '—'}).",
                usuario_id=operador_id, usuario_nome=operador_nome, ip=ip,
            )
            # Broadcast para todas as telas conectadas — é isto que faz o
            # sistema atualizar sem precisar recarregar o navegador.
            socketio.emit("aluno_chamado", chamada)
        else:
            socketio.emit(
                "erro_chamada",
                {"mensagem": "Aluno não encontrado ou já foi chamado por outra tela."},
                to=request.sid,
            )

    @socketio.on("rechamar_aluno")
    def handle_rechamar_aluno(dados):
        """
        Repete a chamada de um aluno que já foi chamado (o aluno não
        compareceu, por exemplo). Não remove ninguém da fila — apenas
        gera uma nova narração/exibição na TV.
        """
        aluno_id = dados.get("aluno_id") if dados else None
        if not aluno_id:
            socketio.emit("erro_chamada", {"mensagem": "Aluno inválido."}, to=request.sid)
            return

        operador_id = session.get("usuario_id")
        operador_nome = session.get("usuario_nome", "Operador")
        ip = request.remote_addr
        guiche = (dados or {}).get("guiche")

        chamada = rechamar_aluno(aluno_id, operador_id, operador_nome, ip=ip, guiche=guiche)

        if chamada:
            registrar_log(
                tipo="chamada",
                mensagem=f"Aluno \"{chamada['aluno_nome']}\" rechamado.",
                usuario_id=operador_id, usuario_nome=operador_nome, ip=ip,
            )
            socketio.emit("aluno_chamado", chamada)
        else:
            socketio.emit(
                "erro_chamada", {"mensagem": "Aluno não encontrado."}, to=request.sid
            )
