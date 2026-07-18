/**
 * screen_selecionar.js
 * =====================
 * Tela de seleção de sala do painel de TV (Módulo 14): ponto de entrada
 * público (sem login) de qualquer TV interativa. O professor toca na
 * sala em que a TV está instalada; a escolha fica salva no navegador
 * dessa TV (localStorage), então da próxima vez que a página carregar
 * (TV religada, navegador reaberto), ela pula direto para o painel da
 * sala já escolhida, sem mostrar essa grade de novo.
 *
 * Chave usada no localStorage é a mesma lida/gravada por screen.js
 * (veja a constante CHAVE_TV_SALA lá), para que as duas telas
 * concordem sobre qual sala está "pareada" com esta TV.
 */

(function () {
    const CONFIG = window.CONFIG_SCREEN || {};
    const CHAVE_TV_SALA = "chamada_alunos_tv_sala_id";

    // --- Se esta TV já tem uma sala escolhida anteriormente, pula a grade ---
    const salaSalva = localStorage.getItem(CHAVE_TV_SALA);
    if (salaSalva) {
        window.location.href = CONFIG.urlBaseSala.replace(/\/$/, "") + "/" + salaSalva;
        return;
    }

    // --- Clique em uma sala da grade ---
    const grade = document.getElementById("grade-salas-tv");
    if (grade) {
        grade.addEventListener("click", function (evento) {
            const cartao = evento.target.closest(".cartao-sala-tv");
            if (!cartao) return;

            const salaId = cartao.dataset.salaId;
            localStorage.setItem(CHAVE_TV_SALA, salaId);
            window.location.href = CONFIG.urlBaseSala.replace(/\/$/, "") + "/" + salaId;
        });
    }
})();
