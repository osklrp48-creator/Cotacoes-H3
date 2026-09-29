# Imagem única: compila o frontend e o FastAPI serve a API + o site.

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FRONTEND_DIST=/app/static
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist /app/static
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
# Aplica as migrations, cria o admin inicial (se ADMIN_EMAIL/ADMIN_SENHA estiverem definidos e o banco
# estiver vazio) e sobe o servidor. A porta vem de $PORT (Render/Railway) ou 8000.
CMD ["sh", "-c", "alembic upgrade head && python -m app.cli criar-admin-inicial && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
