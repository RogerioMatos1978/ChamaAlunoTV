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
