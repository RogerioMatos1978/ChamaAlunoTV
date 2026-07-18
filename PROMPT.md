# PROMPT.md — Especificação para desenvolvimento assistido por IA

> Este arquivo é um **prompt de contexto completo** sobre o projeto
> "Sistema de Chamada Inteligente de Alunos". Foi escrito para ser colado
> no início de uma conversa com qualquer IA de desenvolvimento (Claude,
> ChatGPT, Gemini, Copilot Chat, etc.) para que ela entenda a aplicação
> inteira — objetivo, stack, arquitetura, modelo de dados, regras de
> negócio, rotas e convenções — sem precisar reler todo o código-fonte.
>
> **Regra do projeto: sempre que o código mudar, atualize também o
> `README.md` (documentação para humanos/uso), este `PROMPT.md`
> (contexto para IA) e o `.LOGICA.md` (fluxos e regras de negócio
> passo a passo) na mesma tarefa.** Nunca deixe os três divergirem do
> código real.

---

## 1. O que é o sistema

Uma aplicação web para gerenciar filas de atendimento e chamar alunos
por nome (com foto e voz) em instituições de ensino — secretaria,
coordenação, recepção, salas de aula. Um responsável/aluno é chamado
por um operador no terminal (Kiosk) e a chamada aparece, com foto e
narração por voz, em um painel de TV (Screen), em tempo real, via
WebSocket — sem recarregar a página em nenhuma tela.

Cenário real que o sistema atende (implementado nos Módulos 12–16):
um terminal Kiosk fixo na portaria (TV interativa de 86", tocada pela
recepção) e até 20 salas de aula, cada uma com sua própria TV,
nomeadas por disciplina (Matemática, Ciências, Robótica etc.). O
responsável chega, seleciona o aluno, chama — e a chamada só aparece/
narra na TV da sala correspondente (não em todas as TVs ao mesmo
tempo). Tanto o Kiosk quanto as TVs (Screen) são **públicos** (sem
login), pensados para abrir sozinhos nesses terminais físicos; o resto
do sistema (administração, gestão de alunos/salas, presença, API)
exige login.

## 2. Stack técnica

- **Backend:** Python 3.13+, Flask (application factory pattern),
  Flask-SocketIO (com `eventlet` como worker assíncrono — necessário
  para WebSocket funcionar corretamente), Flask-WTF (CSRF).
- **Banco de dados:** SQLite puro (sem ORM), `sqlite3` da stdlib,
  acesso via `sqlite3.Row` (colunas por nome). Desenhado para permitir
  migração futura para MySQL/MariaDB/PostgreSQL sem reescrever tudo
  (SQL padrão, poucos recursos exclusivos do SQLite).
- **Frontend:** Jinja2 (templates server-side), HTML5/CSS3 puro (sem
  framework CSS), JavaScript puro (sem framework/bundler), Web Speech
  API (`SpeechSynthesis`) para narração por voz.
- **Tempo real:** Socket.IO, padrão "broadcast + filtro no cliente" —
  o servidor não usa "rooms" do Socket.IO; ele emite um evento para
  TODAS as telas conectadas, e cada tela decide no JavaScript se aquele
  evento é relevante para ela (ex.: a TV da sala "Robótica" ignora
  chamadas de outras salas comparando `chamada.sala_nome` com o nome
  da sua própria sala).
- **Senhas:** hash com Werkzeug/PBKDF2 (nunca texto puro).
- **Sem dependências de nuvem/serviços externos** — tudo roda local/on
  -premise, pensado para a rede local da instituição.

## 3. Estrutura de pastas

```
sistema_chamada_alunos/
├── app.py                  # application factory, rota "/", healthcheck
├── config.py                # Config / DevelopmentConfig / ProductionConfig
├── requirements.txt
├── install.sh / install.bat
├── run.sh / run.bat
├── run_rede.bat             # Windows: detecta e exibe o IP da rede antes de iniciar
├── database/
│   ├── models.py             # schema SQL (TABLES_SQL, INDEXES_SQL, migração)
│   ├── services.py            # TODA a lógica de negócio e acesso a dados
│   ├── socket_events.py        # handlers Socket.IO (connect, chamar_aluno, rechamar_aluno)
│   └── alunos.db                # banco SQLite (gerado automaticamente)
├── routes/                  # um blueprint por área
│   ├── auth.py                # login_required, perfil_required, /login, /logout
│   ├── admin.py                 # dashboard, salas, alunos, anos letivos, histórico,
│   │                             # usuários, configurações, auditoria, backup, QR Code
│   ├── kiosk.py                  # terminal de chamada (público) + gestão (login)
│   ├── screen.py                  # painel(is) de TV (público)
│   ├── presenca.py                # painel de presença (login)
│   └── api.py                      # API REST (login)
├── templates/                # Jinja2 (base.html + subpasta admin/)
├── static/
│   ├── css/style.css           # CSS único do projeto, seções numeradas em comentário
│   ├── js/                      # 1 arquivo JS por tela (kiosk.js, screen.js, ...)
│   ├── img/logos/ , img/icons/
│   ├── fotos/                    # fotos de alunos (só o nome do arquivo vai pro banco)
│   ├── fotos_salas/                # fotos de salas
│   └── uploads/
├── backups/                  # backups automáticos/manuais do .db
├── logs/
├── README.md                 # documentação para humanos (instalação, uso, rotas)
├── PROMPT.md                 # este arquivo (contexto para IA)
└── .LOGICA.md                # fluxos e regras de negócio passo a passo
```

## 4. Modelo de dados (SQLite)

Ver definição completa em `database/models.py` (`TABLES_SQL`). Resumo:

- **`unidades`** — suporte a múltiplas unidades/campi (pouco explorado
  na UI ainda, mas já existe no schema e em `usuarios`/`salas`).
- **`usuarios`** — `perfil` é um de `administrador | supervisor | operador`;
  `ativo` (0/1); senha em `senha_hash`.
- **`anos_letivos`** — `nome` único (ex.: "2026"), `ativo`; um deles é
  o "ano letivo atual" (guardado em `configuracoes.ano_letivo_atual_id`),
  usado como padrão ao cadastrar aluno novo.
- **`salas`** — `nome`, `cor` (hex, usada na UI), `ordem`, `ativa`,
  `foto` (nome do arquivo em `static/fotos_salas/`), `unidade_id`.
- **`alunos`** — `sala_id`, `foto`, `codigo` (matrícula, usado na
  importação CSV para não duplicar), `prioridade` (0/1), `status`
  (`aguardando | chamado`), **`ativo`** (0 = inativo/transferido para
  outra escola — Módulo 12), **`ano_letivo_id`** (vínculo obrigatório
  ao ano letivo — Módulo 12).
- **`presencas`** — presença/falta diária, `UNIQUE(aluno_id, data)`
  (upsert), `status` (`presente | faltante`). **A ausência de registro
  em um dia = presente por padrão** — só é preciso marcar quem faltou,
  não confirmar todo mundo todo dia.
- **`chamadas`** — histórico permanente; guarda um *snapshot* de
  `aluno_nome`/`turma`/`sala_nome`/`foto` no momento da chamada (não
  depende do aluno continuar existindo/igual depois). `tipo` é um de
  `chamada | rechamada | manual`.
- **`configuracoes`** — tabela chave/valor genérica (nome da
  instituição, cores, narração, `destino_chamada`,
  `kiosk_modo_simplificado`, `ano_letivo_atual_id`, etc.) — usada para
  não precisar alterar o schema a cada novo parâmetro configurável.
- **`logs_auditoria`** — `tipo` (`login | erro | chamada | importacao |
  alteracao | conexao`), `usuario_id`, mensagem, ip.

**Migração segura:** `init_db()` roda `TABLES_SQL` (todas com
`CREATE TABLE IF NOT EXISTS`, nunca apaga dados) → `_migrar_colunas_novas()`
(tenta `ALTER TABLE ... ADD COLUMN` para cada coluna nova adicionada
depois da v1, ignorando erro se a coluna já existir) → `INDEXES_SQL`
(por último, porque alguns índices referenciam colunas que só existem
depois da migração rodar). **Ao adicionar uma coluna nova a uma tabela
existente, sempre seguir esse padrão** (nunca colocar a coluna direto
em `TABLES_SQL` sem também adicionar em `_COLUNAS_NOVAS`, ou instalações
antigas quebram).

## 5. Regras de negócio importantes

- **Fila de chamada:** só entram na fila do Kiosk alunos com
  `ativo = 1`, `status = 'aguardando'` e que **não** estejam marcados
  como `faltante` na `presencas` do dia corrente.
- **Chamar um aluno:** muda `status` para `chamado`, grava um registro
  em `chamadas` (snapshot) e emite `aluno_chamado` via Socket.IO para
  todas as telas. **Rechamar** repete o evento sem alterar `status`
  (o aluno já estava chamado; é só repetir a exibição/narração).
- **Roteamento por sala (Módulo 13/14):** o evento `aluno_chamado` é
  sempre um broadcast global (sem "rooms" do Socket.IO). Cada tela
  Screen decide se deve reagir: se `CONFIG.salaNome` estiver definido
  (TV dedicada a uma sala) e for diferente de `chamada.sala_nome`, o
  evento é ignorado — é assim que "o chamado não sai em todas as TVs".
  A tela `/screen/geral` não tem `salaNome` e reage a tudo.
  Auto-pareamento sala↔TV é feito com `localStorage` no navegador da
  própria TV (chave `chamada_alunos_tv_sala_id`), não no servidor —
  ao abrir `/screen/` pela primeira vez, a TV mostra uma grade de
  salas para escolher; escolhida uma, salva no `localStorage` e navega
  para `/screen/<sala_id>`, e da próxima vez pula direto para lá.
- **Destino da chamada (Módulo 15):** a narração/texto exibido na TV
  sempre mostra um destino fixo e configurável (`configuracoes.destino_chamada`,
  padrão **"Portaria de Saída"**), independente de qual sala/TV
  disparou a chamada — não mostra mais o nome da sala nesse texto.
- **Sessão fantasma:** uma conta pode ser excluída/desativada enquanto
  ainda está logada em outro dispositivo (ex.: terminal do Kiosk com
  login antigo esquecido aberto). Qualquer gravação que referencie
  `usuarios.id` como FK (log de auditoria, chamada, presença) valida
  primeiro se aquele id ainda existe (helper `_id_usuario_valido()` em
  `services.py`) antes de inserir — senão o SQLite derruba a operação
  com `IntegrityError: FOREIGN KEY constraint failed`. Além disso,
  `login_required` (rotas HTTP) e a rota `/` revalidam a sessão a cada
  acesso (não só a presença da chave `usuario_id`) e encerram sessões
  inválidas de forma limpa, com mensagem amigável.
- **Permissões (3 perfis):** `administrador` > `supervisor` >
  `operador`. Cadastro completo de alunos/salas e importação CSV são
  restritos a administrador/supervisor. O perfil `operador` (usuário
  padrão do dia a dia) só pode, nas telas de "Gestão" do Kiosk (que
  exigem login mesmo o Kiosk sendo público): ativar/desativar aluno,
  marcar presença/falta do dia, trocar foto do aluno e foto da sala —
  nunca o cadastro completo. Só `administrador` acessa Usuários,
  Configurações e Backup (nem `supervisor` pode).
- **Kiosk "modo simplificado" (Módulo 13):** controlado por
  `configuracoes.kiosk_modo_simplificado` (ligado por padrão),
  pensado para o terminal fixo da portaria — esconde tudo, exceto o
  botão "Trocar sala" (e, desde o Módulo 16, sempre um botão discreto
  de login).
- **Importação CSV:** alunos (`nome;turma;sala;codigo;cpf;...`, cria
  salas automaticamente se não existirem, não duplica por `codigo`) e
  salas (`nome;descricao;cor`) — ambas restritas a administrador/
  supervisor, feitas em `/admin/alunos/importar` e `/admin/salas/importar`.

## 6. Camadas e convenções de código

- **`routes/*.py`** só lida com HTTP: parse de request, chamada a
  `database/services.py`, render de template ou redirect. Nenhuma
  query SQL direta em `routes/`.
- **`database/services.py`** concentra toda a lógica de negócio e todo
  SQL. Funções pequenas, nomeadas em português (`listar_alunos`,
  `criar_aluno`, `chamar_aluno`, `marcar_presenca`, ...). Sempre que
  uma escrita referenciar `usuarios.id`, `sala_id` etc. como FK,
  validar existência antes de gravar.
- **`database/socket_events.py`** é a única outra camada que grava no
  banco (via `services.py`) fora do fluxo HTTP normal, porque os
  eventos Socket.IO não passam pelo decorator `login_required`.
- **Templates:** todos estendem `templates/base.html`. Reutilize
  classes CSS já existentes em vez de criar novas quando o visual for
  parecido (ex.: `.tela-login`/`.cartao-login` reaproveitado em
  `home.html`).
- **CSS:** um único arquivo `static/css/style.css`, organizado em
  seções numeradas por comentário (`/* ---------- N. Nome da seção ---------- */`).
  Ao adicionar CSS novo, adicione uma seção nova ou complemente uma
  existente, mantendo a numeração/comentários.
- **Um arquivo JS por tela**, sem bundler — `static/js/kiosk.js`,
  `screen.js`, `screen_selecionar.js`, etc. Configuração vinda do
  servidor (URLs, flags) é injetada via `<script>window.CONFIG_X = {...}</script>`
  inline no template, lido pelo JS externo em seguida.
- **CSRF:** todo formulário HTML usa Flask-WTF; a API REST
  (`routes/api.py`) é isenta de CSRF (`csrf.exempt(api_bp)`) porque é
  pensada para ser chamada via `fetch`/JSON autenticado por sessão, não
  por formulário HTML.
- **Rotas públicas vs. protegidas:** não existe mais `before_request`
  de blueprint inteiro para exigir login (Kiosk e Screen são públicos
  por padrão) — cada rota que precisa de login usa o decorator
  `@login_required` (e, quando cabível, `@perfil_required(...)`)
  individualmente. Cuidado ao adicionar uma rota nova em `kiosk.py`
  ou `screen.py`: decida explicitamente se ela deve ou não pedir login.

## 7. Rotas (visão geral — tabela completa está no README.md)

| Blueprint | Prefixo | Público? |
|---|---|---|
| `app.py` (raiz) | — | `/` e `/healthcheck` públicos |
| `routes/auth.py` | — | `/login` público, `/logout` — |
| `routes/kiosk.py` | `/kiosk` | seleção de sala e fila **públicas**; `/kiosk/gestao/*` exige login |
| `routes/screen.py` | `/screen` | **todas públicas** (seleção, geral, por sala) |
| `routes/presenca.py` | `/presenca` | exige login (qualquer perfil) |
| `routes/admin.py` | `/admin` | exige login; maioria admin/supervisor, algumas só admin |
| `routes/api.py` | `/api` | exige login (sessão do navegador) |

Consulte o README.md (seção "Tabela completa de rotas") para a lista
rota a rota, método HTTP e nível de permissão — mantenha as duas
tabelas (README e este resumo) coerentes com o código real de
`routes/*.py` sempre que uma rota for adicionada/alterada/removida.

## 8. Eventos Socket.IO

| Evento | Direção | Payload | Efeito |
|---|---|---|---|
| `connect` / `disconnect` | cliente ↔ servidor | — | log de conexão (connect); disconnect não loga (evita ruído) |
| `chamar_aluno` | cliente → servidor | `{aluno_id, guiche?}` | muda status, grava histórico, responde com broadcast `aluno_chamado` |
| `rechamar_aluno` | cliente → servidor | `{aluno_id, guiche?}` | repete a chamada (sem mudar status), broadcast `aluno_chamado` |
| `aluno_chamado` | servidor → todos os clientes | dado completo da chamada (snapshot) | Kiosk atualiza lista/recentes; Screen filtra por sala e exibe+narra; Presença remove aluno; Admin atualiza dashboard |
| `erro_chamada` | servidor → cliente que disparou | `{mensagem}` | erro pontual (aluno inválido/já chamado) |
| `dados_atualizados` | servidor → todos | `{tipo}` | aviso de que salas/alunos mudaram (CRUD no admin), para as telas oferecerem "atualizar" sem perder o que o usuário está fazendo |

## 9. Estado atual — módulos já implementados

1. Estrutura base, config e banco de dados
2. Autenticação e login (perfis, sessão, hash de senha)
3. Admin — Dashboard e Salas
4. Alunos, fotos (compressão automática) e importação CSV
5. Kiosk e chamada em tempo real (Socket.IO)
6. Tela Screen (TV) e narração por voz (Web Speech API)
7. Tela de Presença
8. Histórico e exportações (CSV, Excel, PDF)
9. API REST completa
10. Usuários, configurações, auditoria, backup (auto + manual/restauração), QR Code, tema claro/escuro, som de aviso, múltiplos guichês, scripts de instalação/execução
11. Repetir chamado (mantendo nome/foto originais) + aviso de atualização automática entre telas
12. Ano letivo, aluno ativo/inativo, presença diária vinculada ao ano letivo, permissões refinadas (Admin cadastra x operador gerencia dia a dia), foto e CSV de salas, sidebar "últimos 3 chamados" na tela Screen
13. Kiosk em modo simplificado (terminal fixo da portaria) + painel de TV dedicado por sala (`/screen/<sala_id>`, roteamento client-side por `sala_nome`)
14. Kiosk e Screen tornados públicos (sem login); auto-pareamento sala↔TV via `localStorage`
15. Home pública (`/`) convidando ao login para quem não está logado; destino de chamada fixo e configurável ("Portaria de Saída")
16. Botão de login sempre visível no Kiosk e no Screen; README completo reescrito
17. Painel de Presença: card de aluno clicável abre modal para trocar foto (qualquer perfil logado, reaproveitando a rota `kiosk.gestao_aluno_foto`) e, para administrador/supervisor, atalho para o cadastro completo (`admin.alunos_editar`)

**Correções relevantes já aplicadas** (ver detalhes no README, seção
"Correções e ajustes recentes"): bug de sessão fantasma
(`FOREIGN KEY constraint failed`) e bug de rolagem travada no celular
na tela de seleção de sala do Screen (`.tela-screen` era
`position: fixed; overflow: hidden` de propósito para a TV, mas isso
travava a rolagem da lista de salas em telas pequenas — corrigido com
uma regra específica para `.screen-selecionar`).

## 10. Padrão de teste usado neste projeto (se for pedir para uma IA testar)

- Scripts de teste Python devem sobrescrever `Config.DATABASE_PATH`,
  `Config.FOTOS_DIR`, `Config.SALAS_DIR`, `Config.BACKUPS_DIR` para
  caminhos temporários **antes** de importar `app`, para não sujar o
  banco de dados real do projeto durante testes automatizados.
- Use `app.test_client()` para HTTP e
  `flask_socketio.socketio.test_client(app, flask_test_client=client)`
  (importando a instância `socketio` de `app.py`, não do módulo
  `flask_socketio`) para WebSocket, compartilhando cookies de sessão
  entre os dois.
- Formulários HTML exigem token CSRF — ao testar um POST, primeiro
  faça um GET da página e extraia o `csrf_token` do HTML antes de
  enviar o POST.
- Depois de qualquer alteração de código: rode `python3 -m py_compile`
  nos `.py` alterados e `node --check` nos `.js` alterados; limpe
  `__pycache__` e quaisquer scripts/pastas de teste temporários criados
  em `/tmp`.

## 11. Como usar este arquivo com outra IA

Cole o conteúdo deste `PROMPT.md` (ou aponte para o arquivo, se a IA
tiver acesso ao repositório) no início da conversa, junto com o pedido
específico de desenvolvimento. Ele substitui a necessidade de reler
todo o código-fonte para entender o "porquê" das decisões de
arquitetura — mas o código-fonte em si (`routes/`, `database/`,
`templates/`, `static/`) continua sendo a fonte da verdade para
detalhes de implementação linha a linha. Para alterar uma **regra de
negócio** (não só uma tela), leia também o `.LOGICA.md` antes — ele
descreve os fluxos passo a passo (ciclo de vida da chamada, máquina de
estados do aluno, permissões, pareamento sala↔TV, sessão fantasma
etc.) que este `PROMPT.md` só resume.

**Lembrete permanente para quem mantém este projeto (humano ou IA):
toda mudança de funcionalidade, rota, regra de negócio ou correção de
bug relevante deve atualizar `README.md`, este `PROMPT.md` e o
`.LOGICA.md`, mantendo os três em sincronia com o código.**
