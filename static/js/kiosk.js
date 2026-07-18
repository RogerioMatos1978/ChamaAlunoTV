/**
 * kiosk.js
 * ========
 * Tela Kiosk (Módulo 5, ampliada no Módulo 11): dispara a chamada de um
 * aluno via Socket.IO e atualiza a fila em tempo real, sem recarregar a
 * página — tanto para quem clicou quanto para qualquer outra tela aberta
 * (Screen, Presença, outro Kiosk, Admin).
 *
 * Também mantém a lista "Últimos chamados desta sala" sempre atualizada
 * (com foto e nome do aluno) e permite repetir uma chamada com um clique
 * (usa o mesmo evento 'rechamar_aluno' que a tela de Histórico).
 */

document.addEventListener("DOMContentLoaded", function () {
    const socket = window.socketApp;
    const grade = document.getElementById("grade-alunos");
    const estadoVazio = document.getElementById("estado-vazio-fila");
    const campoGuiche = document.getElementById("campo-guiche");
    const listaRecentes = document.getElementById("lista-recentes");
    const semRecentes = document.getElementById("sem-recentes");
    const CONFIG = window.CONFIG_KIOSK || {};

    if (!grade) {
        // Estamos na tela de seleção de sala: nada a fazer aqui (o aviso
        // de "novas informações" de base.html já cobre esta tela).
        return;
    }

    // --- Clique no botão CHAMAR (delegação de evento) ---
    grade.addEventListener("click", function (evento) {
        const botao = evento.target.closest(".btn-chamar");
        if (!botao) return;

        const alunoId = parseInt(botao.dataset.alunoId, 10);
        botao.disabled = true;
        botao.textContent = "Chamando...";

        socket.emit("chamar_aluno", { aluno_id: alunoId, guiche: obterGuiche() });
    });

    // --- Clique em "Repetir chamado" (lista de recentes) ---
    if (listaRecentes) {
        listaRecentes.addEventListener("click", function (evento) {
            const botao = evento.target.closest(".btn-repetir");
            if (!botao) return;

            botao.disabled = true;
            const alunoId = parseInt(botao.dataset.alunoId, 10);
            socket.emit("rechamar_aluno", { aluno_id: alunoId, guiche: obterGuiche() });
            setTimeout(function () { botao.disabled = false; }, 1500);
        });
    }

    function obterGuiche() {
        return campoGuiche && campoGuiche.value.trim() ? campoGuiche.value.trim() : null;
    }

    // --- Um aluno foi chamado ou rechamado (por esta tela ou por outra) ---
    socket.on("aluno_chamado", function (chamada) {
        // Remove o card da fila de espera, se ele estiver nesta sala
        // (uma rechamada não afeta a fila, então normalmente não há card).
        const cartao = grade.querySelector('[data-aluno-id="' + chamada.aluno_id + '"]');
        if (cartao) {
            cartao.style.transition = "opacity 0.35s ease, transform 0.35s ease";
            cartao.style.opacity = "0";
            cartao.style.transform = "scale(0.9)";
            setTimeout(function () {
                cartao.remove();
                verificarFilaVazia();
            }, 350);
        }

        // Atualiza a lista de "últimos chamados" apenas se a chamada for
        // desta sala — mantém sempre o nome e a foto corretos do aluno.
        if (listaRecentes && chamada.sala_nome === CONFIG.salaNome) {
            adicionarNaListaRecentes(chamada);
        }

        const verbo = chamada.tipo === "rechamada" ? "rechamado(a)" : "chamado(a)";
        mostrarToast(chamada.aluno_nome + " foi " + verbo + ".", "sucesso");
    });

    // --- Erro ao tentar chamar (ex.: aluno já chamado por outra tela) ---
    socket.on("erro_chamada", function (erro) {
        mostrarToast(erro.mensagem || "Não foi possível chamar o aluno.", "erro");
        // Reabilita todos os botões, já que não sabemos qual falhou.
        grade.querySelectorAll(".btn-chamar:disabled").forEach(function (b) {
            b.disabled = false;
            b.textContent = "CHAMAR";
        });
    });

    function verificarFilaVazia() {
        if (estadoVazio && grade.children.length === 0) {
            estadoVazio.style.display = "flex";
        }
    }

    // --- Mantém a lista "Últimos chamados" com no máximo 6 itens ---
    function adicionarNaListaRecentes(chamada) {
        if (semRecentes) semRecentes.style.display = "none";

        const item = document.createElement("div");
        item.className = "cartao-recente";
        item.dataset.alunoId = chamada.aluno_id;

        const foto = chamada.foto ? (CONFIG.fotosBase + chamada.foto) : CONFIG.avatarPadrao;

        item.innerHTML =
            '<img class="foto-recente" src="' + foto + '" alt="' + chamada.aluno_nome + '" ' +
            'onerror="this.onerror=null;this.src=\'' + CONFIG.avatarPadrao + '\';">' +
            '<div class="info-recente">' +
            '<span class="nome-recente">' + chamada.aluno_nome + '</span>' +
            '<span class="turma-recente">' + (chamada.turma || "") + '</span>' +
            '</div>' +
            '<button type="button" class="btn btn-pequeno btn-repetir" data-aluno-id="' + chamada.aluno_id + '">🔁 Repetir</button>';

        listaRecentes.prepend(item);

        while (listaRecentes.children.length > 6) {
            listaRecentes.removeChild(listaRecentes.lastElementChild);
        }
    }

    // --- Pequenas notificações (toasts) reaproveitando o estilo de flash ---
    function mostrarToast(mensagem, categoria) {
        let container = document.querySelector(".flash-container");
        if (!container) {
            container = document.createElement("div");
            container.className = "flash-container";
            document.body.appendChild(container);
        }
        const toast = document.createElement("div");
        toast.className = "flash flash-" + categoria;
        toast.textContent = mensagem;
        container.appendChild(toast);

        setTimeout(function () {
            toast.style.transition = "opacity 0.4s ease";
            toast.style.opacity = "0";
            setTimeout(function () { toast.remove(); }, 400);
        }, 3500);
    }
});
