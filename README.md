# Cotações H3

Histórico dos preços que os fornecedores passam para a **H3 Pharma Comércio e Serviços Ltda.**, usado por todas as unidades, com leitura de cotações por IA (Anthropic).

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** FastAPI + SQLAlchemy + Alembic (`backend/`)
- **Banco:** PostgreSQL
- **IA:** SDK oficial `anthropic` (Python). A chave fica só no servidor.

Em produção, o FastAPI também serve o site compilado. Por isso tudo roda num **único serviço** e num banco.

---

## 1. Rodar localmente com Docker (mais simples)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env            # preencha ANTHROPIC_API_KEY (e SECRET_KEY)
docker compose up -d --build
```

Abra **http://localhost:8000**. As migrations do banco são aplicadas automaticamente quando o serviço sobe.

Para criar o primeiro admin:

```bash
docker compose exec app python -m app.cli criar-admin \
  --nome "Seu Nome" --email voce@h3pharma.com.br --unidade "Matriz"
# a senha é pedida no terminal (mínimo 8 caracteres)
```

A unidade informada é criada se ainda não existir. As outras unidades e os usuários são cadastrados pela tela **Admin**.

Comandos úteis:

```bash
docker compose logs -f app      # ver os logs
docker compose down             # parar (os dados ficam guardados)
docker compose down -v          # parar e APAGAR o banco
```

O Postgres do Docker fica exposto na porta **5433** do seu computador, para não conflitar com um Postgres já instalado.

## 2. Rodar em modo desenvolvimento (com recarga automática)

Pré-requisitos: Python 3.11+, Node 20+ e um PostgreSQL. Pode ser o do Docker: `docker compose up -d db`.

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env            # ajuste DATABASE_URL (ex.: ...@localhost:5433/cotacoes se usar o banco do Docker)
alembic upgrade head
python -m app.cli criar-admin --nome "Seu Nome" --email voce@h3pharma.com.br --unidade "Matriz"
uvicorn app.main:app --reload
```

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Abra **http://localhost:5173**. O Vite repassa as chamadas `/api` para o backend na porta 8000.

## 3. Importar os dados atuais (`cotacoes-export.json`)

O script importa `{"cotacoes": [...], "fornecedores": [...]}` e liga todos os registros à unidade que você indicar.

1. Crie o admin (seção 1 ou 2) e confira o **id** da unidade na tela Admin → Unidades. A primeira unidade criada tem id 1.
2. Faça primeiro uma **simulação**, que mostra o resultado sem gravar nada:

```bash
# Docker (o arquivo é enviado pela entrada padrão, com "-"):
docker compose exec -T app python -m app.cli importar - --unidade-id 1 --simular < cotacoes-export.json

# Sem Docker (dentro de backend/, com o venv ativo):
python -m app.cli importar ../cotacoes-export.json --unidade-id 1 --simular
```

3. Se o resumo estiver certo, rode de novo **sem** `--simular`.

**Como a importação trata os dados:**
- **Autor dos registros:** o primeiro admin. Para outro usuário, use `--usuario-id N`.
- **Campos:** a importação aceita os nomes `data`, `fornecedor`, `pagamento`, `entrega`, `valorFrete`, `obs`, `itens[{produto, marca, unidade, qtd, valorUnit}]` e variações comuns. Números podem vir como `1234.5` ou `"1.234,50"`. Datas podem vir como `AAAA-MM-DD` ou `DD/MM/AAAA`.
- **Reimportação:** é segura. Registros já importados são pulados, pelo `id` da cotação ou, se ela não tiver `id`, por uma assinatura do conteúdo.
- **Cotações ignoradas:** as que não têm data ou não têm nenhum item com produto e valor. Elas aparecem em "Avisos" no resumo.

O `cotacoes-export.json` está no `.gitignore` para que os preços não sejam enviados ao GitHub por engano.

## 4. Testes

```bash
cd backend
source .venv/bin/activate
# precisa de um banco vazio só para testes (ele é apagado e recriado a cada execução)
createdb cotacoes_test   # ou crie pelo seu cliente Postgres
TEST_DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@localhost:5432/cotacoes_test pytest
```

Os testes cobrem:
- login e proteção das rotas
- permissões de admin
- registros: criação, validação, busca, filtros, edição e exclusão
- agrupamento de produtos, estatísticas e exclusões (incluindo registro que fica vazio)
- renomear e juntar fornecedores
- importação
- rota de IA com a API da Anthropic **mockada**: texto, PDF, imagem, .docx com tabelas, .xlsx com várias abas, CSV, recusa de `.doc`, limite de tamanho, erros em português e registro de uso

## 5. Colocar no ar (sugestão: Render)

O [Render](https://render.com) é uma opção simples: um **Web Service** (Docker) roda API e site juntos, e um **PostgreSQL** gerenciado guarda os dados. O repositório já tem o `render.yaml`.

1. Suba o código para o GitHub.
2. No Render, vá em **New → Blueprint**, escolha o repositório e confirme. O Render cria o banco e o serviço. Confira os planos e preços na hora de criar; para uso interno, os menores planos pagos bastam. Evite o banco gratuito, que expira.
3. No serviço `cotacoes-h3`, em **Environment**, preencha `ANTHROPIC_API_KEY`. O `SECRET_KEY` é gerado automaticamente e `COOKIE_SECURE=true` já vem definido.
4. Depois do primeiro deploy, crie o admin e importe os dados de um destes jeitos:
   - pela aba **Shell** do serviço no Render: `python -m app.cli criar-admin ...`
   - ou do seu computador, apontando para o banco do Render. Copie a *External Database URL* e, dentro de `backend/`, rode:
     ```bash
     DATABASE_URL="postgres://...render.com/cotacoes" python -m app.cli criar-admin --nome "..." --email ... --unidade "Matriz"
     DATABASE_URL="postgres://...render.com/cotacoes" python -m app.cli importar ../cotacoes-export.json --unidade-id 1
     ```
5. Se quiser, configure um domínio próprio (ex.: `cotacoes.h3pharma.com.br`) em **Settings → Custom Domains**. O HTTPS é automático.

**Alternativas equivalentes:**
- **Railway:** serviço a partir do `Dockerfile` + plugin PostgreSQL. A variável `DATABASE_URL` do Railway já é aceita.
- **Fly.io:** também funciona com o mesmo `Dockerfile`.

Em qualquer uma, defina as mesmas variáveis do `.env.example`.

## Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Conexão com o PostgreSQL. Aceita `postgres://`, `postgresql://` ou `postgresql+psycopg://`. |
| `SECRET_KEY` | Assina a sessão. Use 32+ caracteres aleatórios. Com `COOKIE_SECURE=true`, o servidor se recusa a subir sem uma chave assim. |
| `COOKIE_SECURE` | `true` em produção (HTTPS). |
| `JWT_EXPIRE_HOURS` | Duração da sessão, em horas (padrão 12). |
| `ANTHROPIC_API_KEY` | Chave da API da Anthropic. Sem ela, a leitura com IA mostra um aviso e o resto do sistema funciona normalmente. |
| `ANTHROPIC_MODEL` | Modelo usado na leitura (padrão `claude-sonnet-5-5`). |
| `IA_MAX_MB` | Tamanho máximo do arquivo enviado à IA (padrão 20). |
| `IA_PRECO_ENTRADA_MTOK` / `IA_PRECO_SAIDA_MTOK` | US$ por milhão de tokens, só para a **estimativa** de custo no Admin. Ajuste conforme a tabela de preços da Anthropic. |
| `CORS_ORIGINS` | Só é necessário se o site ficar em outro domínio que não o da API. |

## Como funciona

### Perfis de acesso
- **admin:** gerencia unidades e usuários, vê o uso da IA e edita tudo.
- **usuário:** registra e edita valores.
- **Todos** veem o histórico de todas as unidades.
- **Unidade do registro:** cada registro guarda a unidade e o usuário que o criou. O usuário comum registra sempre na própria unidade; o admin pode escolher a unidade.

### Sessão e senhas
A sessão fica em um cookie `httpOnly` (JWT) com `SameSite=Lax` e não é acessível por JavaScript. As senhas são guardadas com hash bcrypt.

### Fornecedores
- **Criação automática:** o "Quem passou o valor" é texto livre. Quando preenchido, o sistema liga o registro a um fornecedor com o mesmo nome, sem diferenciar acento e maiúsculas, e cria o fornecedor se ele ainda não existir.
- **Sem fornecedor:** registros sem fornecedor aparecem como *Não informado*.
- **Renomear:** atualiza o nome em todos os registros. Se o novo nome já existir, os dois cadastros são juntados, e o sistema avisa antes quantos registros serão alterados.

### Produtos
Não há tabela própria de produtos. Eles são agrupados por nome normalizado (sem acento, sem diferença de maiúsculas) + unidade de medida.

### Leitura com IA
- **O que a rota faz:** `POST /api/ia/ler-cotacao` recebe um arquivo ou um texto e devolve os campos para **pré-preencher** o formulário. **Nunca grava registros.**
- **Tipos de arquivo:**
  - PDF e imagens vão direto para a API.
  - `.docx` vira texto, com as tabelas linha a linha.
  - `.xlsx`, `.xls` e `.csv` viram CSV, uma aba por bloco.
  - `.doc` é recusado com orientação para salvar como `.docx` ou PDF.
- **Registro de uso:** cada uso fica registrado com usuário, unidade, data e tokens em `uso_ia`, e aparece em Admin → Uso da IA.

### Documentação da API
Com o sistema rodando, a documentação interativa fica em `/api/docs`.

## Estrutura

```
backend/
  app/
    main.py            # cria o app, rotas /api e serve o frontend
    models.py          # tabelas (unidades, usuarios, fornecedores, registros, itens, uso_ia)
    schemas.py         # validação de entrada/saída
    routers/           # auth, unidades, usuarios, registros, produtos, fornecedores, ia, admin
    services/          # regras de fornecedores/registros e leitura com IA
    importacao.py      # importação do cotacoes-export.json
    cli.py             # comandos criar-admin e importar
  alembic/             # migrations
  tests/               # testes (pytest)
frontend/
  src/paginas/         # Registros, RegistroForm, Produtos, ProdutoDetalhe, Fornecedores, FornecedorFicha, Admin, Login
  src/componentes/     # Layout, ImportarCotacao, confirmações/avisos
Dockerfile             # imagem única (compila o frontend + FastAPI)
docker-compose.yml     # app + PostgreSQL para rodar localmente
render.yaml            # blueprint para publicar no Render
```
