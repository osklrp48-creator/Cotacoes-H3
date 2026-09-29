# Cotações H3 — notas para quem mantém o projeto

## Preferência do dono do projeto
- **Sempre priorizar opções gratuitas** (hospedagem, banco, IA, bibliotecas, serviços). Só sugerir algo pago
  quando não houver alternativa gratuita viável, deixando claro o custo e o motivo.
- O dono não usa terminal nem Docker no computador: tudo deve poder ser feito pelo navegador
  (Render, Neon, GitHub, telas do próprio sistema).

## Stack atual (gratuita)
- Site + API: Render, plano Free (Docker, `render.yaml`).
- Banco: Neon, PostgreSQL gratuito (`DATABASE_URL`).
- IA: Google Gemini, camada gratuita (`IA_PROVEDOR=gemini`), com Groq gratuito como reserva automática
  (`GROQ_API_KEY`, só texto); Anthropic fica como opção paga.

## Comandos de desenvolvimento
- Backend: `cd backend && pytest` (precisa de um PostgreSQL de teste em `TEST_DATABASE_URL`).
- Frontend: `cd frontend && npm run build`.
- Textos da interface e mensagens de erro em português do Brasil.
