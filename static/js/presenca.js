/**
 * presenca.js
 * ===========
 * Tela de Presença (Módulo 7): busca instantânea, filtro por sala e
 * remoção automática do aluno da lista assim que ele é chamado em
 * qualquer Kiosk (via Socket.IO), sem precisar recarregar a página.
 */

document.addEventListener("DOMContentLoaded", function () {
    const campoBusca = document.getElementById("busca-presenca");
    const grade = document.getElementById("grade-presenca");
    const estadoVazio = document.getElementById("estado-vazio-presenca");
    const contador = document.getElementById("contador-presenca");
    const filtros = document.getElementById("filtros-sala");

    let salaSelecionada = "todas";

    function aplicarFiltros() {
        const termo = campoBusca.value.trim().toLowerCase();
        let visiveis = 0;

        grade.querySelectorAll(".cartao-presenca").forEach(function (cartao) {
            const combinaBusca = !termo || cartao.dataset.busca.includes(termo);
            const combinaSala = salaSelecionada === "todas" || cartao.dataset.salaId === salaSelecionada;
            const visivel = combinaBusca && combinaSala;
            cartao.style.display = visivel ? "" : "none";
            if (visivel) visiveis++;
        });

        contador.textContent = visiveis + (visiveis === 1 ? " aguardando" : " aguardando");
        estadoVazio.style.display = visiveis === 0 ? "flex" : "none";
    }

    campoBusca.addEventListener("input", aplicarFiltros);

    filtros.addEventListener("click", function (evento) {
        const pilula = evento.target.closest(".pilula-filtro");
        if (!pilula) return;

        filtros.querySelectorAll(".pilula-filtro").forEach(function (p) { p.classList.remove("ativa"); });
        pilula.classList.add("ativa");
        salaSelecionada = pilula.dataset.salaId;
        aplicarFiltros();
    });

    // --- Modal de ações do aluno (Módulo 17): abre ao clicar num card ---
    const modalAcoes = document.getElementById("modal-acoes-aluno");
    const formFotoAcoes = document.getElementById("form-foto-acoes-aluno");
    const tituloAcoes = document.getElementById("acoes-aluno-titulo");
    const fotoAcoes = document.getElementById("acoes-aluno-foto");
    const linkEditarAcoes = document.getElementById("acoes-aluno-link-editar");
    const btnFecharAcoes = document.getElementById("btn-fechar-acoes-aluno");

    function abrirModalAcoes(cartao) {
        const alunoId = cartao.dataset.alunoId;
        formFotoAcoes.action = "/kiosk/gestao/alunos/" + alunoId + "/foto";
        tituloAcoes.textContent = cartao.dataset.alunoNome;
        fotoAcoes.src = cartao.dataset.fotoUrl;
        fotoAcoes.alt = cartao.dataset.alunoNome;

        if (cartao.dataset.editarUrl) {
            linkEditarAcoes.href = cartao.dataset.editarUrl;
            linkEditarAcoes.classList.remove("oculto");
        } else {
            linkEditarAcoes.classList.add("oculto");
        }

        modalAcoes.classList.remove("oculto");
    }

    if (grade && modalAcoes) {
        grade.addEventListener("click", function (evento) {
            const cartao = evento.target.closest(".cartao-presenca-clicavel");
            if (!cartao) return;
            abrirModalAcoes(cartao);
        });

        grade.addEventListener("keydown", function (evento) {
            if (evento.key !== "Enter" && evento.key !== " ") return;
            const cartao = evento.target.closest(".cartao-presenca-clicavel");
            if (!cartao) return;
            evento.preventDefault();
            abrirModalAcoes(cartao);
        });

        btnFecharAcoes.addEventListener("click", function () {
            modalAcoes.classList.add("oculto");
        });

        modalAcoes.addEventListener("click", function (evento) {
            if (evento.target === modalAcoes) modalAcoes.classList.add("oculto");
        });
    }

    // --- Sincronização em tempo real: remove o aluno assim que for chamado ---
    const socket = window.socketApp;
    socket.on("aluno_chamado", function (chamada) {
        const cartao = grade.querySelector('[data-aluno-id="' + chamada.aluno_id + '"]');
        if (!cartao) return;

        // Atualiza a contagem da pílula da sala correspondente, se existir.
        const salaId = cartao.dataset.salaId;
        if (salaId) {
            const pilula = filtros.querySelector('[data-sala-id="' + salaId + '"] span');
            if (pilula) {
                const atual = parseInt(pilula.textContent.replace(/\D/g, ""), 10) || 0;
                pilula.textContent = "(" + Math.max(atual - 1, 0) + ")";
            }
        }

        cartao.style.transition = "opacity 0.3s ease";
        cartao.style.opacity = "0";
        setTimeout(function () {
            cartao.remove();
            aplicarFiltros();
        }, 300);
    });

    aplicarFiltros();
});
