FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para lxml e psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro (cache de camada)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto
COPY src/ /app/src/
COPY tests/ /app/tests/
COPY schemas/ /app/schemas/
COPY docs/ /app/docs/
COPY .devin/ /app/.devin/

# Usuário não-root para segurança
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
