"""
Configurações do serviço de API.

Este módulo contém as configurações carregadas via variáveis de ambiente
para o serviço de API REST.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações do serviço de API.
    
    Attributes:
        api_host: Host da API
        api_port: Porta da API
        api_title: Título da documentação
        api_version: Versão da API
        opcua_endpoint: Endpoint do servidor OPC UA
        database_url: URL do banco de dados SQLite
        rabbitmq_host: Host do RabbitMQ
        rabbitmq_port: Porta do RabbitMQ
        rabbitmq_user: Usuário do RabbitMQ
        rabbitmq_pass: Senha do RabbitMQ
    """
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Motor50CV API"
    api_version: str = "1.0.0"
    api_description: str = "API REST para monitoramento de motor trifásico 50CV"
    
    # OPC UA Configuration
    opcua_endpoint: str = "opc.tcp://opcua-server:4840/motor50cv/server"
    
    # Database Configuration
    database_url: str = "sqlite:///./data/motor.db"
    
    # RabbitMQ Configuration (para consumo direto se necessário)
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_pass: str = "admin123"
    rabbitmq_exchange: str = "motor_data"
    
    class Config:
        """Configuração do Pydantic."""
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    
    Returns:
        Settings: Objeto com as configurações do serviço
    """
    return Settings()
