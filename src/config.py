"""Configuracao central do sistema."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Banco de dados (default aponta para dev local; em producao usar DATABASE_URL)
    database_url: str = "postgresql+psycopg2://contabilidade:contabilidade_dev@localhost:5432/contabilidade"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Certificado digital (sempre via env, nunca commitar)
    certificado_a1_path: str = ""
    certificado_a1_senha: str = ""
    cnpj_consultado: str = ""  # obrigatorio em producao via env
    destinatario_nome: str = "Minha Empresa Ltda"

    # SEFAZ
    sefaz_ambiente: str = "homologacao"
    mock_sefaz: bool = True
    sefaz_rate_limit: int = 3  # maximo de consultas por segundo
    sefaz_mock_url: str = "http://localhost:9000"
    sefaz_timeout: int = 30  # timeout em segundos para chamadas SEFAZ

    # Tolerancias de reconciliacao
    tolerancia_preco_percent: float = 2.0
    tolerancia_qtd_percent: float = 5.0
    tolerancia_data_dias: int = 15

    # Dashboard
    dashboard_host: str = "127.0.0.1"  # so localhost por default
    dashboard_port: int = 8000

    # CORS: lista de origens permitidas (separadas por virgula no env)
    cors_allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # Rate limit da API do dashboard (requisicoes por minuto por IP)
    api_rate_limit: int = 60

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
