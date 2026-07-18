/**
 * admin.js
 * ========
 * Comportamento das telas administrativas (dashboard, salas, alunos).
 *
 * Mantido como JavaScript puro (sem frameworks), conforme a
 * especificação do projeto.
 */

document.addEventListener("DOMContentLoaded", function () {
    // --- Alterna o menu lateral em telas pequenas (celular/tablet) ---
    const btnMenu = document.getElementById("btn-menu");
    const sidebar = document.getElementById("sidebar");
    if (btnMenu && sidebar) {
        btnMenu.addEventListener("click", function () {
            sidebar.classList.toggle("aberta");
        });
    }

    // --- Relógio do rodapé (data e hora), atualizado a cada segundo ---
    const relogio = document.getElementById("relogio-rodape");
    if (relogio) {
        function atualizarRelogio() {
            const agora = new Date();
            relogio.textContent =
                agora.toLocaleDateString("pt-BR") + " às " + agora.toLocaleTimeString("pt-BR");
        }
        atualizarRelogio();
        setInterval(atualizarRelogio, 1000);
    }
});
