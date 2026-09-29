# Cotações H3

Histórico dos preços que os fornecedores passam para a **H3 Pharma Comércio e Serviços Ltda.**, usado por todas as unidades, com leitura de cotações por IA: **Google Gemini** (padrão, com camada gratuita) ou **Anthropic Claude** (pago por uso).

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** FastAPI + SQLAlchemy + Alembic (`backend/`)
- **Banco:** PostgreSQL
- **IA:** SDKs oficiais `google-genai` (Gemini) e `anthropic` (Claude). A chave fica só no servidor.

Em produção, o FastAPI também serve o site compilado. Por isso tudo roda num **único serviço** e num banco.

---

## 1. Rodar localmente com Docker (mais simples)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env            # preencha GEMINI_API_KEY (e SECRET_KEY)
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
- rota de IA com o Gemini e a Anthropic **mockados**: texto, PDF, imagem, .docx com tabelas, .xlsx com várias abas, CSV, recusa de `.doc`, limite de tamanho, erros em português e registro de uso

## 5. Colocar no ar de graça — sem instalar nada

Tudo é feito pelo navegador e sem custo:
- **Banco:** [Neon](https://neon.tech), PostgreSQL gratuito que não expira (0,5 GB).
- **Site:** [Render](https://render.com), plano **Free**.
- **IA:** Gemini, camada gratuita (seção 6).

**Limitação do plano Free do Render:** depois de uns 15 minutos sem ninguém usar, o site "dorme". O primeiro acesso seguinte demora cerca de 1 minuto para abrir; depois fica normal. Os dados não se perdem, porque ficam no Neon.

### 5.1 Criar o banco no Neon
1. Crie uma conta em **neon.tech** (pode entrar com o GitHub ou o Google). Não pede cartão.
2. Crie um projeto (ex.: `cotacoes-h3`), escolhendo a região mais próxima do Brasil que aparecer.
3. No painel do projeto, clique em **Connect** e copie a **connection string**. Ela começa com `postgresql://` e termina com `?sslmode=require`.

### 5.2 Publicar o site no Render
1. Crie uma conta no Render entrando com o GitHub e autorize o acesso ao repositório `Cotacoes-H3`.
2. Clique em **New → Blueprint**, escolha o repositório e confirme. O Render lê o `render.yaml`, que já usa o plano **Free** e não cria banco no Render (o banco gratuito de lá expira).
3. O Render pede os valores que não ficam no código:
   - `DATABASE_URL`: a connection string do Neon.
   - `GEMINI_API_KEY`: a chave do Google AI Studio (seção 6).
   - `ADMIN_NOME`, `ADMIN_EMAIL`, `ADMIN_SENHA` (mínimo 8 caracteres): o primeiro admin, criado automaticamente na primeira vez que o sistema sobe.
   - O `SECRET_KEY` é gerado sozinho e `COOKIE_SECURE=true` já vem definido.
4. Espere o deploy terminar (alguns minutos) e abra o endereço mostrado pelo Render, algo como `https://cotacoes-h3.onrender.com`. Entre com o e-mail e a senha do admin.
5. Em **Admin → Importar dados**, envie o `cotacoes-export.json`, escolha a unidade, clique em **Simular** e depois em **Importar de verdade**.
6. Em **Admin → Unidades** e **Usuários**, cadastre as outras unidades e as pessoas.
7. Se quiser, configure um domínio próprio (ex.: `cotacoes.h3pharma.com.br`) em **Settings → Custom Domains**. O HTTPS é automático.

Depois que o admin existir, as variáveis `ADMIN_*` não fazem mais nada (o sistema só cria o admin com o banco vazio). Pode apagar a `ADMIN_SENHA` do Render.

Cada vez que um código novo entra no branch do GitHub, o Render publica a nova versão sozinho.

**Se um dia o site dormindo incomodar:** um plano pago do Render (ou Railway/Fly.io, com o mesmo `Dockerfile`) mantém o site sempre acordado. O banco pode continuar no Neon. Em qualquer hospedagem, defina as mesmas variáveis do `.env.example`.

## 6. Leitura com IA: Gemini (grátis) ou Claude (pago)

**Gemini (padrão):**
1. Entre em **https://aistudio.google.com/apikey** com uma conta Google e clique em **Create API key**.
2. Coloque a chave em `GEMINI_API_KEY` (no `.env` ou no Environment do Render). Não precisa de cartão para a camada gratuita.
3. **Limites:** a camada gratuita tem limite de leituras por minuto e por dia. Quando estoura, o sistema mostra "O limite de uso gratuito do Gemini foi atingido".
4. **Privacidade:** na camada gratuita, o Google pode usar o que é enviado (as cotações) para melhorar os produtos dele. Se isso não for aceitável, ative o faturamento no Google (camada paga, que não usa os dados assim) ou troque para o Claude.

**Groq (reserva gratuita, recomendado):** o Gemini gratuito às vezes fica sem cota ou sobrecarregado. Com o Groq configurado, o sistema passa sozinho para ele nesses casos.
1. Crie uma conta em **https://console.groq.com** (pode entrar com o Google; não pede cartão).
2. Em **API Keys**, clique em **Create API Key** e copie a chave.
3. Cole em `GROQ_API_KEY` (no `.env` ou no Environment do Render).

O Groq só lê texto: cobre texto colado, Word, planilhas e PDFs com texto. PDF escaneado e fotos dependem do Gemini. Se o modelo configurado (`GROQ_MODEL`) for aposentado, o sistema escolhe outro sozinho.

**Claude (Anthropic):** mude `IA_PROVEDOR=anthropic` e preencha `ANTHROPIC_API_KEY` (crie em console.anthropic.com). Custa perto de 1 a 3 centavos de dólar por cotação; dá para definir um limite mensal de gasto no console.

A troca entre os dois é só nas variáveis de ambiente, reiniciando o serviço. O formulário e o resto do sistema não mudam.

## Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Conexão com o PostgreSQL. Aceita `postgres://`, `postgresql://` ou `postgresql+psycopg://`. |
| `SECRET_KEY` | Assina a sessão. Use 32+ caracteres aleatórios. Com `COOKIE_SECURE=true`, o servidor se recusa a subir sem uma chave assim. |
| `COOKIE_SECURE` | `true` em produção (HTTPS). |
| `ADMIN_NOME` / `ADMIN_EMAIL` / `ADMIN_SENHA` / `ADMIN_UNIDADE` | Primeiro admin, criado ao subir **só se o banco não tiver nenhum usuário**. |
| `JWT_EXPIRE_HOURS` | Duração da sessão, em horas (padrão 12). |
| `IA_PROVEDOR` | `gemini` (padrão) ou `anthropic`. |
| `GEMINI_API_KEY` | Chave do Google Gemini (veja a seção 6). Sem chave, a leitura com IA mostra um aviso e o resto do sistema funciona normalmente. |
| `GEMINI_MODEL` | Modelo do Gemini (padrão `gemini-flash-latest`, que o Google mantém apontando para o Flash atual). Se o modelo configurado for aposentado, o sistema escolhe sozinho o Flash disponível mais novo. |
| `GROQ_API_KEY` / `GROQ_MODEL` | Reserva gratuita (Groq) usada quando o Gemini falha por cota ou sobrecarga. Também dá para usar só ele com `IA_PROVEDOR=groq` (só texto). |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Só com `IA_PROVEDOR=anthropic`: chave e modelo do Claude (padrão `claude-sonnet-5-5`). |
| `IA_MAX_MB` | Tamanho máximo do arquivo enviado à IA (padrão 20). |
| `IA_PRECO_ENTRADA_MTOK` / `IA_PRECO_SAIDA_MTOK` | US$ por milhão de tokens, só para a **estimativa** de custo no Admin. Vazio = 0 no Gemini e 2 / 10 no Claude Sonnet 5.5. |
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
  - PDF com texto (gerado por sistema) tem o texto extraído no servidor (`pypdf`) e só o texto vai para a IA, o que é bem mais leve. PDF escaneado e imagens vão como arquivo.
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
