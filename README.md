# Sistema de Chamada Inteligente de Alunos

Sistema web para gerenciamento de filas e chamada de alunos em instituições
de ensino (secretaria, recepção, coordenação e atendimento ao público).
Chamadas em tempo real, com narração por voz e painel de TV, sincronizadas
via WebSocket entre todas as telas — sem necessidade de atualizar o navegador.

## Stack

Python 3.13+, Flask, Flask-SocketIO, SQLite, Eventlet, Jinja2, HTML5/CSS3
puro, JavaScript, Web Speech API (`SpeechSynthesis`).

## Estrutura do projeto

```
sistema_chamada_alunos/
├── app.py                     # Ponto de entrada (application factory)
├── config.py                   # Configurações centrais (dev/produção)
├── requirements.txt
├── install.sh / install.bat    # Instalação (Linux/macOS / Windows)
├── run.sh / run.bat            # Execução em desenvolvimento
├── database/
│   ├── models.py               # Schema SQLite (CREATE TABLE) + migração
│   ├── services.py             # Regras de negócio / acesso a dados
│   ├── socket_events.py        # Eventos Socket.IO
│   └── alunos.db                # Banco de dados (gerado automaticamente)
├── routes/                     # Blueprints Flask (um por área do sistema)
│   ├── auth.py                  # Login, logout, controle de permissões
│   ├── admin.py                  # Dashboard, salas, alunos, anos letivos,
│   │                              # histórico, usuários, configurações,
│   │                              # auditoria, backup, QR Code
│   ├── kiosk.py                  # Terminal de chamada (público) + gestão
│   │                              # do usuário padrão (login)
│   ├── screen.py                 # Painel(is) de TV (público)
│   ├── presenca.py               # Painel de presença (login)
│   └── api.py                    # API REST (login)
├── templates/                  # Views Jinja2 (subpasta admin/ por tela)
├── static/
│   ├── css/style.css            # CSS puro (sem frameworks)
│   ├── js/                      # Um arquivo JS por tela
│   ├── img/logos/                # Logo da instituição
│   ├── img/icons/                # Ícones e avatar padrão
│   ├── fotos/                    # Fotos dos alunos (só o nome do arquivo é salvo no banco)
│   ├── fotos_salas/               # Fotos das salas
│   └── uploads/                  # Uploads temporários
├── backups/                    # Backups automáticos e manuais do banco
└── logs/                       # Logs de erro/aplicação (produção)
```

## Como acessar o sistema

O sistema tem três níveis de acesso. **Kiosk e painel de TV são públicos
de propósito** — são terminais físicos (portaria, salas de aula) que
precisam abrir sozinhos, sem ninguém digitar usuário/senha ali. Todo o
resto exige login.

| Nível | O que inclui | O que acontece sem login |
|---|---|---|
| **Público** | Home (`/`), Login, Kiosk de chamada, Painel de TV, healthcheck | Abre normalmente |
| **Login (qualquer perfil)** | Gestão do usuário padrão (Kiosk), Presença, API | Redireciona para `/login` |
| **Administrador/Supervisor** | Dashboard, Salas, Alunos, Anos letivos, Histórico, Auditoria, QR Code | Mensagem "sem permissão" + redireciona |
| **Somente Administrador** | Usuários, Configurações, Backup | Mensagem "sem permissão" + redireciona |

Se uma sessão perde a validade (ex.: a conta foi excluída ou desativada
enquanto ainda estava logada em outro dispositivo), o sistema encerra
essa sessão de forma limpa na próxima ação e pede login de novo, em vez
de quebrar com um erro técnico.

### Onde entrar com usuário e senha

- **`/login`** — tela de login "pura".
- **`/`** (Home) — quando ninguém está logado, mostra um convite para
  fazer login, com atalhos diretos para o Kiosk e o painel de TV
  (que continuam públicos). Quem já está logado nunca vê esta tela.
- **Botão "🔐 Entrar"** — tanto o Kiosk (inclusive no modo simplificado)
  quanto o painel de TV têm um botão discreto de login sempre visível
  para quem não está logado, para chegar ao resto do sistema a partir
  de qualquer terminal público.

Depois de logar, o sistema leva cada perfil para sua área principal:
administrador/supervisor → Dashboard administrativo; operador → Kiosk.

### Tabela completa de rotas

**`app.py` (raiz)**

| Método | Rota | Login? | Descrição |
|---|---|---|---|
| GET | `/` | Não | Home: convite para login (se anônimo) ou redireciona para a área do perfil logado |
| GET | `/healthcheck` | Não | Verificação rápida se o servidor está no ar |

**`routes/auth.py`** (sem prefixo)

| Método | Rota | Login? | Descrição |
|---|---|---|---|
| GET, POST | `/login` | Não | Autenticação |
| GET | `/logout` | — | Encerra a sessão atual |

**`routes/kiosk.py`** (prefixo `/kiosk`) — terminal da portaria

| Método | Rota | Login? | Descrição |
|---|---|---|---|
| GET | `/kiosk/` | **Não** | Seleção de sala a atender |
| GET | `/kiosk/<sala_id>` | **Não** | Fila de chamada da sala (botão CHAMAR) |
| GET | `/kiosk/gestao/alunos` | Sim | Usuário padrão: lista de alunos p/ gerenciar ativo/presença/foto |
| POST | `/kiosk/gestao/alunos/<id>/ativo` | Sim | Alterna aluno ativo ⇄ inativo |
| POST | `/kiosk/gestao/alunos/<id>/presenca` | Sim | Marca presente/faltante hoje |
| POST | `/kiosk/gestao/alunos/<id>/foto` | Sim | Troca a foto do aluno |
| GET | `/kiosk/gestao/salas` | Sim | Usuário padrão: lista de salas p/ trocar foto |
| POST | `/kiosk/gestao/salas/<id>/foto` | Sim | Troca a foto da sala |

**`routes/screen.py`** (prefixo `/screen`) — painel(is) de TV

| Método | Rota | Login? | Descrição |
|---|---|---|---|
| GET | `/screen/` | **Não** | Seleção de sala desta TV (ou pulo automático se já pareada) |
| GET | `/screen/geral` | **Não** | Painel "geral": mostra a chamada de qualquer sala |
| GET | `/screen/<sala_id>` | **Não** | Painel dedicado: só exibe/narra chamadas dessa sala |

**`routes/presenca.py`** (prefixo `/presenca`)

| Método | Rota | Login? | Descrição |
|---|---|---|---|
| GET | `/presenca/` | Sim (qualquer perfil) | Lista de alunos aguardando, com busca instantânea |

**`routes/admin.py`** (prefixo `/admin`) — todas exigem login; a maioria
aceita administrador **ou** supervisor; as marcadas "só admin" exigem
especificamente o perfil administrador.

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/admin/` , `/admin/dashboard` | admin/supervisor | Indicadores gerais |
| GET | `/admin/salas` | admin/supervisor | Lista de salas |
| GET, POST | `/admin/salas/nova` | admin/supervisor | Cadastro de sala |
| GET, POST | `/admin/salas/<id>/editar` | admin/supervisor | Edição de sala |
| POST | `/admin/salas/<id>/excluir` | admin/supervisor | Exclusão de sala |
| GET, POST | `/admin/salas/importar` | admin/supervisor | Importação de salas via CSV |
| GET | `/admin/salas/<id>/qrcode.png` | admin/supervisor | QR Code → tela de Presença da sala |
| GET | `/admin/salas/<id>/qrcode-tv.png` | admin/supervisor | QR Code → painel de TV dedicado da sala |
| GET | `/admin/alunos` | admin/supervisor | Lista de alunos, com busca/filtro |
| GET, POST | `/admin/alunos/novo` | admin/supervisor | Cadastro de aluno |
| GET, POST | `/admin/alunos/<id>/editar` | admin/supervisor | Edição de aluno |
| POST | `/admin/alunos/<id>/excluir` | admin/supervisor | Exclusão de aluno |
| GET, POST | `/admin/alunos/importar` | admin/supervisor | Importação de alunos via CSV |
| GET | `/admin/anos-letivos` | admin/supervisor | Lista de anos letivos |
| GET, POST | `/admin/anos-letivos/novo` | admin/supervisor | Cadastro de ano letivo |
| GET, POST | `/admin/anos-letivos/<id>/editar` | admin/supervisor | Edição de ano letivo |
| POST | `/admin/anos-letivos/<id>/excluir` | admin/supervisor | Exclusão de ano letivo |
| POST | `/admin/anos-letivos/<id>/definir-atual` | admin/supervisor | Define o ano letivo padrão |
| GET | `/admin/historico` | admin/supervisor | Histórico pesquisável de chamadas |
| GET | `/admin/historico/exportar/<csv\|xlsx\|pdf>` | admin/supervisor | Exportação do histórico filtrado |
| POST | `/admin/historico/<id>/rechamar` | admin/supervisor | Repete uma chamada do histórico |
| GET | `/admin/auditoria` | admin/supervisor | Log de auditoria (login, alterações, erros) |
| GET | `/admin/usuarios` | **só admin** | Lista de usuários do sistema |
| GET, POST | `/admin/usuarios/novo` | **só admin** | Cadastro de usuário |
| GET, POST | `/admin/usuarios/<id>/editar` | **só admin** | Edição de usuário / senha |
| POST | `/admin/usuarios/<id>/excluir` | **só admin** | Exclusão de usuário |
| GET, POST | `/admin/configuracoes` | **só admin** | Nome, logo, cores, narração, destino da chamada, modo Kiosk |
| GET | `/admin/backup` | **só admin** | Lista de backups |
| POST | `/admin/backup/novo` | **só admin** | Cria backup manual |
| GET | `/admin/backup/<arquivo>/baixar` | **só admin** | Baixa um arquivo de backup |
| POST | `/admin/backup/<arquivo>/restaurar` | **só admin** | Restaura o banco a partir de um backup |

**`routes/api.py`** (prefixo `/api`) — todas exigem login (sessão do
navegador); as rotas de escrita de salas exigem administrador/supervisor.

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/api/salas` | qualquer logado | Lista salas |
| GET | `/api/salas/<id>` | qualquer logado | Detalhe de uma sala |
| POST | `/api/salas` | admin/supervisor | Cria sala |
| PUT | `/api/salas/<id>` | admin/supervisor | Atualiza sala |
| DELETE | `/api/salas/<id>` | admin/supervisor | Exclui sala |
| GET | `/api/alunos` | qualquer logado | Lista alunos (filtros: `sala_id`, `status`, `busca`) |
| GET | `/api/alunos/<id>` | qualquer logado | Detalhe de um aluno |
| POST | `/api/alunos` | qualquer logado | Cria aluno |
| PUT | `/api/alunos/<id>` | qualquer logado | Atualiza aluno |
| DELETE | `/api/alunos/<id>` | qualquer logado | Exclui aluno |
| GET | `/api/chamadas` | qualquer logado | Fila atual (alunos aguardando) |
| POST | `/api/chamadas` | qualquer logado | Chama um aluno (`{"aluno_id": 1}`) — sincroniza todas as telas |
| GET | `/api/historico` | qualquer logado | Histórico (filtros: `busca`, `sala_nome`, `tipo`, `data_inicio`, `data_fim`, `limite`) |

A API usa a mesma sessão de login das telas HTML — faça login em
`/login` com o mesmo navegador/cliente HTTP antes de chamar a API.

## Instalação (desenvolvimento)

Pré-requisitos: Python 3.13+ instalado.

**Windows:** dê duplo clique em `install.bat` (ou rode-o no terminal) e,
depois, em `run.bat`.

**Linux/macOS:**
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

Isso cria um ambiente virtual (`.venv`), instala as dependências, gera o
arquivo `.env` a partir de `.env.example` e inicia o servidor.

Acesse: `http://localhost:5000`

Para acessar de outros dispositivos na mesma rede (ex.: a TV do painel ou
outro computador da secretaria), use o IP da máquina servidora, por
exemplo `http://192.168.0.10:5000`. Veja mais em
[Uso em rede local](#uso-em-rede-local).

> **Importante:** mantenha a pasta do projeto (e o arquivo
> `database/alunos.db`) em um disco local. Pastas sincronizadas na nuvem
> (OneDrive, Google Drive, Dropbox) ou compartilhamentos de rede podem
> causar erros de "disk I/O error" no SQLite, pois esse tipo de pasta nem
> sempre suporta corretamente o travamento de arquivo que o SQLite exige.

## Progresso dos módulos

- [x] **Módulo 1** — Estrutura base, configuração e banco de dados
- [x] **Módulo 2** — Autenticação e login
- [x] **Módulo 3** — Admin (dashboard e cadastro de salas)
- [x] **Módulo 4** — Alunos, fotos e importação CSV
- [x] **Módulo 5** — Kiosk e chamada em tempo real (Socket.IO)
- [x] **Módulo 6** — Tela Screen (TV) e narração por voz
- [x] **Módulo 7** — Tela de Presença
- [x] **Módulo 8** — Histórico e exportações (CSV/Excel/PDF)
- [x] **Módulo 9** — API REST
- [x] **Módulo 10** — Usuários, configurações, auditoria, backup, QR Code,
      tema claro/escuro, som de aviso, múltiplos guichês e scripts de implantação
- [x] **Módulo 11** — Repetir chamado (mantendo nome/foto) e aviso de
      atualização automática entre todas as telas
- [x] **Módulo 12** — Ano letivo, aluno ativo/inativo, presença diária e
      permissões refinadas (Admin x usuário padrão), foto e CSV de salas,
      sidebar de últimos chamados no Screen
- [x] **Módulo 13** — Kiosk em modo simplificado para terminal fixo da
      portaria (só o botão "Trocar sala") e painel de TV dedicado por
      sala de aula (`/screen/<sala_id>`), para o cenário de 1 Kiosk na
      recepção + 1 TV por sala
- [x] **Módulo 14** — Kiosk e painel de TV ficam **públicos** (sem
      login), pensados para abrir sozinhos no terminal da portaria e
      nas TVs das salas; o painel de TV ganha uma tela de seleção de
      sala (o professor escolhe, uma vez, qual sala é a da TV — fica
      salvo naquele navegador) e um botão para trocar depois
- [x] **Módulo 15** — Página inicial (`/`) volta a pedir login para
      quem não está logado (com atalhos diretos para o Kiosk e o
      painel de TV, que continuam públicos); a chamada passa a narrar/
      exibir sempre um destino fixo e configurável ("Portaria de
      Saída" por padrão), em vez do nome da sala/TV que disparou a chamada
- [x] **Módulo 16** — Botão de login sempre visível no Kiosk (mesmo no
      modo simplificado) e no painel de TV, para acessar o resto do
      sistema a partir de qualquer terminal público

## Correções e ajustes recentes

- **Sessão fantasma (erro `FOREIGN KEY constraint failed`)** — se uma
  conta era excluída enquanto ainda estava logada em outro
  dispositivo/terminal, a próxima ação dessa sessão (ex.: logout, uma
  chamada) quebrava com erro técnico. Corrigido em duas camadas: (1) o
  banco de dados agora valida, antes de qualquer gravação que referencie
  um usuário (log de auditoria, chamada, presença), se aquele usuário
  ainda existe; (2) `login_required` e a rota inicial (`/`) revalidam a
  sessão a cada acesso e encerram sessões inválidas de forma limpa, com
  a mensagem "Sua sessão não é mais válida... Faça login novamente." em
  vez de um erro técnico.
- **Rolagem travada no celular (painel de TV)** — a tela de seleção de
  sala do painel de TV (`/screen/`) herdava o estilo de tela fixa usado
  pela exibição de chamadas (correto para a TV, que mostra uma chamada
  por vez e não precisa rolar). Em telas pequenas de celular, com várias
  salas cadastradas, isso travava a rolagem e a página parecia
  "congelada". Corrigido: a tela de seleção de sala agora rola
  normalmente quando o conteúdo não cabe na tela; a exibição de
  chamadas na TV continua fixa, como deve ser.

## Funcionalidades

Autenticação com perfis (administrador, supervisor, operador) e senhas
criptografadas · Dashboard com indicadores e gráfico simples · CRUD de
salas e de alunos · Upload de fotos com compressão automática · Importação
de alunos via CSV (cria salas automaticamente, não duplica) · Kiosk com
chamada em tempo real via Socket.IO · Painel de TV com narração por voz
configurável (voz, idioma, velocidade, tom, volume) e som de aviso · Painel
de Presença com busca instantânea e filtros · Histórico pesquisável com
exportação em CSV, Excel e PDF · Repetir chamado com nome/foto sempre
corretos (lista "Últimos chamados" no Kiosk) · Aviso de dados atualizados
em tempo real (salas/alunos) em todas as telas, com botão para atualizar
sem perder o que está sendo feito · Controle de prioridade ·
Múltiplos guichês · API REST completa · Página de usuários e permissões ·
Página de configurações (nome, logo, cores, narração) · Página de
auditoria · QR Code por sala · Tema claro/escuro · Backup automático e
manual, com restauração · Proteção CSRF e sanitização de entradas ·
Alunos são cadastros fixos com situação ativo/inativo (para transferência
para outra escola) · Presença/falta diária do aluno, vinculada ao ano
letivo · Cadastro e seleção de anos letivos, com um "ano letivo atual"
usado por padrão nos novos cadastros · Fila do Kiosk respeita
automaticamente quem está inativo ou foi marcado como faltante no dia ·
Importação via CSV de alunos e de salas restrita ao Admin/Supervisor ·
Usuário padrão (operador) gerencia no dia a dia, sem acesso ao cadastro
completo: situação ativo/inativo do aluno, presença/falta do dia, foto do
aluno e foto da sala (telas em "Kiosk → Gerenciar alunos/salas") · Sidebar
com os últimos 3 alunos chamados na tela Screen (TV), atualizada em tempo
real · Kiosk em "modo simplificado" (ligado por padrão, ajustável em
Configurações): mostra apenas o botão "Trocar sala", pensado para um
terminal fixo na portaria (ex.: TV interativa de 86") operado pela
recepção · Painel de TV dedicado por sala de aula (`/screen/<sala_id>`):
cada uma das TVs das salas só exibe/narra as chamadas da própria sala,
mesmo recebendo o mesmo evento em tempo real que todas as outras telas —
o painel "geral" (`/screen/geral`) continua disponível para quem precisa
ver todas as chamadas · Link "Abrir TV" e QR Code por sala (tanto para a
tela de Presença quanto para o painel de TV dedicado), para facilitar
configurar cada uma das TVs das salas · Kiosk e painel de TV são
públicos (sem login) — abrem sozinhos em qualquer terminal/TV da rede;
as demais telas (administração, gestão do usuário padrão, Presença)
continuam exigindo login normalmente · Painel de TV com autosseleção
de sala: na primeira vez que uma TV abre, mostra uma grade de salas
(como no Kiosk) para o professor escolher a sala daquela TV; a escolha
fica salva no navegador da própria TV, então nas próximas vezes ela já
abre direto no painel da sala escolhida — com botão para trocar depois
· Proteção contra "sessão fantasma": se uma conta for excluída ou
desativada enquanto ainda está logada em algum dispositivo, o sistema
encerra essa sessão de forma limpa (sem erro técnico) na próxima ação ·
Página inicial (`/`) pede login para quem não está logado, com atalhos
diretos para o Kiosk e o painel de TV (que continuam públicos) ·
Destino da chamada configurável (padrão "Portaria de Saída"): a
narração e o texto exibido na TV sempre apontam para esse destino
fixo, independente de qual sala/TV disparou a chamada · Botão "🔐
Entrar" sempre visível no Kiosk (mesmo em modo simplificado) e no
painel de TV, para qualquer pessoa autorizada acessar o resto do
sistema a partir de um terminal público.

## Acesso padrão (troque em produção)

Na primeira execução, o sistema cria automaticamente um usuário administrador:

- **Usuário:** `admin`
- **Senha:** `admin123`

Troque essa senha em **Configurações administrativas → Usuários → Editar**
assim que possível.

## Backup e restauração

- Um backup automático é criado a cada `BACKUP_INTERVALO_HORAS` (padrão:
  24h), mantendo os `BACKUP_MANTER_ULTIMOS` mais recentes (padrão: 30).
- Backup manual, download e restauração ficam em **Painel administrativo →
  Backup** (apenas administradores).
- Os arquivos ficam em `backups/alunos_AAAAMMDD_HHMMSS.db`.

## Uso em rede local

1. Descubra o IP da máquina que está rodando o servidor:
   - Windows: `ipconfig` (campo "Endereço IPv4")
   - Linux/macOS: `ip a` ou `ifconfig`
2. Nos outros dispositivos (TV, tablets, outros computadores), acesse
   `http://<IP-DO-SERVIDOR>:5000` pelo navegador.
3. Libere a porta 5000 (ou a porta escolhida) no firewall da máquina
   servidora, se necessário.
4. **Kiosk da portaria**: configure o navegador do terminal para abrir
   direto em `http://<IP-DO-SERVIDOR>:5000/kiosk` — não pede login. Por
   padrão, mostra só o botão "Trocar sala" (modo simplificado,
   ajustável em Configurações → Kiosk) e um botão discreto "🔐 Entrar"
   para quem precisar acessar o resto do sistema dali mesmo.
5. **TV de cada sala de aula**: configure o navegador de cada TV para
   abrir em `http://<IP-DO-SERVIDOR>:5000/screen` (também sem login) e
   deixe em tela cheia (botão ⛶). Na primeira vez, aparece uma grade
   com as salas ativas — toque na sala em que aquela TV está instalada.
   A escolha fica salva no navegador da própria TV (não precisa repetir
   depois de reiniciar), e a partir daí ela só exibe/narra as chamadas
   dessa sala. Para trocar depois, use o botão 🏫 no canto da tela.
   Alternativamente, o Admin pode configurar o link direto de cada TV
   (`/screen/<id-da-sala>`) em **Painel administrativo → Salas →
   "Abrir TV"** ou pelo botão **"QR TV"** — o id de cada sala também
   aparece nos cards de seleção do próprio Kiosk ("📺 TV nº X").
6. **Se preferir uma única TV central** (em vez de uma por sala), abra
   `/screen/geral` nela — mostra a chamada de qualquer sala, sem se
   prender a uma específica (comportamento das versões anteriores ao
   Módulo 13).

## Kiosk e painel de TV são públicos — atenção à rede

`/kiosk` e `/screen` não pedem login de propósito (são terminais/TVs de
uso público). Isso significa que qualquer dispositivo com acesso à rede
onde o servidor está pode chamar alunos e ver a fila. Mantenha o
servidor em uma rede local confiável (Wi-Fi/LAN da instituição) e **não
exponha a porta do sistema diretamente para a internet** sem um proxy
reverso com controle de acesso — todas as telas administrativas
continuam exigindo login normalmente (veja a
[tabela completa de rotas](#tabela-completa-de-rotas)).

## Implantação em produção

Em produção, **não** use `python app.py` (é o modo de desenvolvimento).
Use um servidor WSGI de verdade com suporte a WebSocket (Gunicorn +
worker eventlet), atrás de um proxy reverso.

### Linux (Nginx + Gunicorn)

1. Instale as dependências do sistema e do projeto:
   ```bash
   sudo apt update && sudo apt install -y python3-venv nginx
   cd /opt/sistema_chamada_alunos
   ./install.sh
   ```
2. Configure o `.env` com `FLASK_ENV=production` e uma `SECRET_KEY` forte:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Rode com Gunicorn (worker eventlet, necessário para o Socket.IO):
   ```bash
   source .venv/bin/activate
   pip install gunicorn
   gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 app:app
   ```
   Recomenda-se manter **um único worker** (`-w 1`): o Socket.IO precisa
   que todas as conexões passem pelo mesmo processo para o broadcast
   funcionar corretamente sem um message queue externo (Redis).
4. Crie um serviço systemd (`/etc/systemd/system/chamada-alunos.service`):
   ```ini
   [Unit]
   Description=Sistema de Chamada Inteligente de Alunos
   After=network.target

   [Service]
   WorkingDirectory=/opt/sistema_chamada_alunos
   Environment="PATH=/opt/sistema_chamada_alunos/.venv/bin"
   ExecStart=/opt/sistema_chamada_alunos/.venv/bin/gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 app:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   sudo systemctl enable --now chamada-alunos
   ```
5. Configure o Nginx como proxy reverso, com suporte a WebSocket:
   ```nginx
   server {
       listen 80;
       server_name chamada.suaescola.local;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```
   ```bash
   sudo systemctl reload nginx
   ```

### Windows Server

1. Instale o Python 3.13+ (marque "Add to PATH" no instalador).
2. Copie a pasta do projeto para o servidor (ex.: `C:\sistemas\chamada_alunos`).
3. Rode `install.bat` uma vez para preparar o ambiente.
4. Configure o `.env` com `FLASK_ENV=production` e uma `SECRET_KEY` forte.
5. Para manter o sistema rodando continuamente (mesmo sem usuário logado),
   use o **NSSM** (Non-Sucking Service Manager) para registrar
   `run.bat` (ou diretamente `python.exe app.py`) como um serviço do
   Windows:
   ```bat
   nssm install ChamadaAlunos "C:\sistemas\chamada_alunos\.venv\Scripts\python.exe" "app.py"
   nssm set ChamadaAlunos AppDirectory "C:\sistemas\chamada_alunos"
   nssm start ChamadaAlunos
   ```
6. Para expor a outros computadores da rede, libere a porta 5000 no
   Firewall do Windows (Regras de Entrada → Nova Regra → Porta → TCP 5000).
7. Opcionalmente, use o **IIS** com o módulo **HttpPlatformHandler** como
   proxy reverso para a aplicação Python, de forma semelhante ao Nginx.

## Qualidade do código

PEP 8, separação em camadas (rotas / serviços / banco), funções pequenas,
tratamento de exceções, validação de entradas, proteção CSRF
(Flask-WTF) em todos os formulários HTML, sanitização de nomes de
arquivo (`secure_filename`) e senhas sempre armazenadas como hash
(Werkzeug/PBKDF2).

## Licença e uso

Projeto desenvolvido sob medida para uso interno da instituição.
