/**
 * screen.js
 * =========
 * Tela Screen (Módulo 6): painel de TV que exibe a foto e o nome do
 * aluno chamado, com narração por voz (SpeechSynthesis).
 *
 * Principais responsabilidades:
 *   - Ouvir o evento 'aluno_chamado' via Socket.IO e enfileirar as
 *     chamadas (para não sobrepor exibições/narrações se várias
 *     chamadas chegarem em sequência rápida).
 *   - Alternar entre o estado "ocioso" e o estado "chamada" com
 *     transições suaves (fade + zoom).
 *   - Narrar cada chamada com a Web Speech API, sempre cancelando
 *     qualquer narração anterior antes de começar uma nova.
 *   - Permitir configurar voz, idioma, velocidade, tom e volume — as
 *     preferências ficam salvas neste navegador/TV (localStorage),
 *     já que cada TV pode ter vozes diferentes instaladas.
 */

(function () {
    const CONFIG = window.CONFIG_SCREEN || {};
    const CHAVE_CONFIG_VOZ = "chamada_alunos_config_voz";

    const elOcioso = document.getElementById("screen-ocioso");
    const elChamada = document.getElementById("screen-chamada");
    const elFoto = document.getElementById("screen-foto");
    const elNome = document.getElementById("screen-nome");
    const elTurma = document.getElementById("screen-turma");
    const elSala = document.getElementById("screen-sala");
    const elRelogio = document.getElementById("screen-relogio");
    const elSidebarLista = document.getElementById("screen-sidebar-lista");
    const elSidebarVazio = document.getElementById("screen-sidebar-vazio");
    const MAX_SIDEBAR = 3;

    const TEMPO_EXIBICAO_MS = 9000;   // quanto tempo cada chamada fica em destaque
    const filaChamadas = [];
    let exibindoChamada = false;

    // -------------------------------------------------------------------
    // Relógio do estado ocioso
    // -------------------------------------------------------------------
    function atualizarRelogio() {
        if (!elRelogio) return;
        const agora = new Date();
        elRelogio.textContent = agora.toLocaleDateString("pt-BR") + " — " + agora.toLocaleTimeString("pt-BR");
    }
    atualizarRelogio();
    setInterval(atualizarRelogio, 1000);

    // -------------------------------------------------------------------
    // Conexão em tempo real
    // -------------------------------------------------------------------
    const socket = window.socketApp;

    socket.on("aluno_chamado", function (chamada) {
        // Módulo 13: se esta TV é dedicada a uma sala (CONFIG.salaNome
        // definido), ignora qualquer chamada que não seja dessa sala —
        // é assim que 20 TVs, uma por sala de aula, só mostram/narram a
        // própria chamada mesmo recebendo o mesmo evento de broadcast.
        if (CONFIG.salaNome && chamada.sala_nome !== CONFIG.salaNome) return;

        filaChamadas.push(chamada);
        processarFila();
        adicionarNaSidebar(chamada);
    });

    // -------------------------------------------------------------------
    // Barra lateral "Últimos chamados" (Módulo 12) — mantém no máximo 3
    // itens, sempre com o chamado mais recente no topo.
    // -------------------------------------------------------------------
    function adicionarNaSidebar(chamada) {
        if (!elSidebarLista) return;
        if (elSidebarVazio) elSidebarVazio.style.display = "none";

        const item = document.createElement("div");
        item.className = "screen-sidebar-item";

        const foto = chamada.foto ? (CONFIG.fotosBase + chamada.foto) : CONFIG.avatarPadrao;

        item.innerHTML =
            '<img src="' + foto + '" alt="' + chamada.aluno_nome + '" ' +
            'onerror="this.onerror=null;this.src=\'' + CONFIG.avatarPadrao + '\';">' +
            '<div class="screen-sidebar-info">' +
            '<span class="screen-sidebar-nome">' + chamada.aluno_nome + '</span>' +
            '<span class="screen-sidebar-detalhe">' + (chamada.turma || "") + '</span>' +
            '<span class="screen-sidebar-detalhe">' + (chamada.sala_nome || "") + '</span>' +
            '</div>';

        elSidebarLista.prepend(item);

        while (elSidebarLista.children.length > MAX_SIDEBAR) {
            elSidebarLista.removeChild(elSidebarLista.lastElementChild);
        }
    }

    function processarFila() {
        if (exibindoChamada || filaChamadas.length === 0) return;
        exibindoChamada = true;
        const chamada = filaChamadas.shift();
        exibirChamada(chamada);
    }

    // -------------------------------------------------------------------
    // Exibição da chamada (transição fade + zoom)
    // -------------------------------------------------------------------
    function exibirChamada(chamada) {
        elNome.textContent = chamada.aluno_nome || "";
        elTurma.textContent = chamada.turma || "";
        elSala.textContent = chamada.sala_nome ? ("Sala: " + chamada.sala_nome) : "";

        elFoto.src = chamada.foto ? (CONFIG.fotosBase + chamada.foto) : CONFIG.avatarPadrao;
        elFoto.onerror = function () {
            elFoto.onerror = null;
            elFoto.src = CONFIG.avatarPadrao;
        };

        elOcioso.classList.remove("visivel");
        elChamada.classList.add("visivel", "efeito-zoom");

        narrarChamada(chamada);

        setTimeout(function () {
            elChamada.classList.remove("visivel", "efeito-zoom");
            elOcioso.classList.add("visivel");
            exibindoChamada = false;
            processarFila();
        }, TEMPO_EXIBICAO_MS);
    }

    // -------------------------------------------------------------------
    // Narração (Web Speech API)
    // -------------------------------------------------------------------
    function montarMensagem(chamada) {
        const nome = chamada.aluno_nome || "";
        const turma = chamada.turma ? chamada.turma + ". " : "";
        const sala = chamada.sala_nome || "recepção";

        return (
            "Atenção. Chamando o aluno " + nome + ". " + turma +
            "Favor dirigir-se à " + sala + ". " +
            "Repetindo. " + nome + ". " + turma +
            "Favor dirigir-se à " + sala + "."
        );
    }

    function narrarChamada(chamada) {
        if (!("speechSynthesis" in window)) return;

        // Cancela qualquer narração anterior antes de iniciar uma nova.
        window.speechSynthesis.cancel();

        const config = carregarConfigVoz();
        const mensagem = montarMensagem(chamada);
        const utterance = new SpeechSynthesisUtterance(mensagem);

        utterance.lang = config.idioma || "pt-BR";
        utterance.rate = config.velocidade || 1;
        utterance.pitch = config.pitch || 1;
        utterance.volume = config.volume != null ? config.volume : 1;

        const vozes = window.speechSynthesis.getVoices();
        const voz = vozes.find(function (v) { return v.name === config.voz; });
        if (voz) utterance.voice = voz;

        const falar = function () { window.speechSynthesis.speak(utterance); };

        if (config.somAviso !== false) {
            tocarSomAviso(falar);
        } else {
            falar();
        }
    }

    // -------------------------------------------------------------------
    // Som de aviso antes da narração (Web Audio API — sem arquivo de áudio)
    // -------------------------------------------------------------------
    function tocarSomAviso(aoConcluir) {
        try {
            const contexto = new (window.AudioContext || window.webkitAudioContext)();
            const oscilador = contexto.createOscillator();
            const ganho = contexto.createGain();

            oscilador.type = "sine";
            oscilador.frequency.setValueAtTime(880, contexto.currentTime);
            ganho.gain.setValueAtTime(0.25, contexto.currentTime);
            ganho.gain.exponentialRampToValueAtTime(0.001, contexto.currentTime + 0.6);

            oscilador.connect(ganho);
            ganho.connect(contexto.destination);
            oscilador.start();
            oscilador.stop(contexto.currentTime + 0.6);

            setTimeout(aoConcluir, 700);
        } catch (e) {
            aoConcluir();
        }
    }

    // -------------------------------------------------------------------
    // Painel de configuração de narração
    // -------------------------------------------------------------------
    const painel = document.getElementById("painel-config-voz");
    const seletorVoz = document.getElementById("config-voz");
    const campoIdioma = document.getElementById("config-idioma");
    const campoVelocidade = document.getElementById("config-velocidade");
    const campoPitch = document.getElementById("config-pitch");
    const campoVolume = document.getElementById("config-volume");
    const campoSomAviso = document.getElementById("config-som-aviso");

    function carregarConfigVoz() {
        try {
            return JSON.parse(localStorage.getItem(CHAVE_CONFIG_VOZ)) || {};
        } catch (e) {
            return {};
        }
    }

    function salvarConfigVoz(config) {
        localStorage.setItem(CHAVE_CONFIG_VOZ, JSON.stringify(config));
    }

    function popularVozes() {
        if (!("speechSynthesis" in window)) return;
        const vozes = window.speechSynthesis.getVoices();
        const config = carregarConfigVoz();

        seletorVoz.innerHTML = "";
        vozes.forEach(function (v) {
            const opcao = document.createElement("option");
            opcao.value = v.name;
            opcao.textContent = v.name + " (" + v.lang + ")";
            if (v.name === config.voz) opcao.selected = true;
            seletorVoz.appendChild(opcao);
        });
    }

    function aplicarConfigNaTela() {
        const config = carregarConfigVoz();
        campoIdioma.value = config.idioma || "pt-BR";
        campoVelocidade.value = config.velocidade || 1;
        campoPitch.value = config.pitch || 1;
        campoVolume.value = config.volume != null ? config.volume : 1;
        campoSomAviso.checked = config.somAviso !== false;
        document.getElementById("valor-velocidade").textContent = campoVelocidade.value;
        document.getElementById("valor-pitch").textContent = campoPitch.value;
        document.getElementById("valor-volume").textContent = campoVolume.value;
    }

    if ("speechSynthesis" in window) {
        popularVozes();
        window.speechSynthesis.onvoiceschanged = popularVozes;
    }
    aplicarConfigNaTela();

    [campoVelocidade, campoPitch, campoVolume].forEach(function (campo) {
        campo.addEventListener("input", function () {
            document.getElementById("valor-" + campo.id.replace("config-", "")).textContent = campo.value;
        });
    });

    document.getElementById("btn-config-voz").addEventListener("click", function () {
        painel.classList.toggle("oculto");
    });

    document.getElementById("btn-fechar-voz").addEventListener("click", function () {
        painel.classList.add("oculto");
    });

    document.getElementById("btn-salvar-voz").addEventListener("click", function () {
        salvarConfigVoz({
            voz: seletorVoz.value,
            idioma: campoIdioma.value || "pt-BR",
            velocidade: parseFloat(campoVelocidade.value),
            pitch: parseFloat(campoPitch.value),
            volume: parseFloat(campoVolume.value),
            somAviso: campoSomAviso.checked,
        });
        painel.classList.add("oculto");
    });

    document.getElementById("btn-testar-voz").addEventListener("click", function () {
        narrarChamada({
            aluno_nome: "Aluno de teste",
            turma: "Turma de teste",
            sala_nome: "Secretaria",
        });
    });

    // -------------------------------------------------------------------
    // Tela cheia
    // -------------------------------------------------------------------
    document.getElementById("btn-tela-cheia").addEventListener("click", function () {
        const elemento = document.documentElement;
        if (!document.fullscreenElement) {
            if (elemento.requestFullscreen) elemento.requestFullscreen();
        } else {
            if (document.exitFullscreen) document.exitFullscreen();
        }
    });

    // Estado inicial: ocioso visível.
    elOcioso.classList.add("visivel");
})();
