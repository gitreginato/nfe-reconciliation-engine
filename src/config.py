"""Configuracao central do sistema."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Banco de dados
    database_url: str = "postgresql+psycopg2://contabilidade:contabilidade_dev@localhost:5432/contabilidade"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Certificado digital
    certificado_a1_path: str = ""
    certificado_a1_senha: str = ""
    cnpj_consultado: str = "12345678000190"
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
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
