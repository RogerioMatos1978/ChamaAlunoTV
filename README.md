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
│   ├── models.py               # Schema SQLite (CREATE TABLE)
│   ├── services.py             # Regras de negócio / acesso a dados
│   ├── socket_events.py        # Eventos Socket.IO
│   └── alunos.db                # Banco de dados (gerado automaticamente)
├── routes/                     # Blueprints Flask (um por área do sistema)
│   ├── auth.py                  # Login, logout, controle de permissões
│   ├── admin.py                  # Dashboard, salas, alunos, histórico,
│   │                              # usuários, configurações, auditoria, backup
│   ├── kiosk.py                  # Tela de chamada (operador)
│   ├── screen.py                 # Painel de TV
│   ├── presenca.py               # Painel de presença
│   └── api.py                    # API REST
├── templates/                  # Views Jinja2 (subpasta admin/ por tela)
├── static/
│   ├── css/style.css            # CSS puro (sem frameworks)
│   ├── js/                      # Um arquivo JS por tela
│   ├── img/logos/                # Logo da instituição
│   ├── img/icons/                # Ícones e avatar padrão
│   ├── fotos/                    # Fotos dos alunos (só o nome do arquivo é salvo no banco)
│   ├── fotos_salas/               # Fotos das salas (Módulo 12)
│   └── uploads/                  # Uploads temporários
├── backups/                    # Backups automáticos e manuais do banco
└── logs/                       # Logs de erro/aplicação (produção)
```

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
real.

## API REST

A API usa a mesma sessão de login das telas HTML (faça login em `/login`
com o mesmo navegador/cliente HTTP antes de chamar a API).

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/salas` | Lista salas |
| GET | `/api/salas/<id>` | Detalhe de uma sala |
| POST | `/api/salas` | Cria sala (administrador/supervisor) |
| PUT | `/api/salas/<id>` | Atualiza sala (administrador/supervisor) |
| DELETE | `/api/salas/<id>` | Exclui sala (administrador/supervisor) |
| GET | `/api/alunos` | Lista alunos (filtros: `sala_id`, `status`, `busca`) |
| GET | `/api/alunos/<id>` | Detalhe de um aluno |
| POST | `/api/alunos` | Cria aluno |
| PUT | `/api/alunos/<id>` | Atualiza aluno |
| DELETE | `/api/alunos/<id>` | Exclui aluno |
| GET | `/api/chamadas` | Fila atual (alunos aguardando) |
| POST | `/api/chamadas` | Chama um aluno (`{"aluno_id": 1}`) — sincroniza todas as telas |
| GET | `/api/historico` | Histórico de chamadas (filtros: `busca`, `sala_nome`, `tipo`, `data_inicio`, `data_fim`, `limite`) |

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
4. Para a tela de TV, abra `/screen` em tela cheia (botão ⛶ no canto
   superior direito) e mantenha o navegador aberto continuamente.

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
