"""
Configurações do servidor OPC UA.

Este módulo contém as configurações carregadas via variáveis de ambiente
para o servidor OPC UA.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações do servidor OPC UA.
    
    Attributes:
        opcua_endpoint: Endpoint do servidor OPC UA
        opcua_name: Nome do servidor
        opcua_namespace: Namespace URI do servidor
        rabbitmq_host: Host do RabbitMQ
        rabbitmq_port: Porta do RabbitMQ
        rabbitmq_user: Usuário do RabbitMQ
        rabbitmq_pass: Senha do RabbitMQ
        database_path: Caminho do banco SQLite para histórico
        lds_url: URL do Local Discovery Server
        lds_register_interval: Intervalo de registro no LDS (segundos)
    """
    
    # OPC UA Configuration
    opcua_endpoint: str = "opc.tcp://0.0.0.0:4840/motor50cv/server"
    opcua_name: str = "Motor50CV OPC UA Server"
    opcua_namespace: str = "http://motor50cv.industrial/ua"
    
    # RabbitMQ Configuration
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_pass: str = "admin123"
    rabbitmq_exchange: str = "motor_data"
    rabbitmq_queue: str = "motor_readings"
    
    # Historical Data Configuration
    database_path: str = "/app/data/history.db"
    history_max_records: int = 100000
    
    # Local Discovery Server
    lds_url: str = "opc.tcp://localhost:4840"
    lds_register_interval: int = 60
    
    # Alarm Configuration - Valores nominais para cálculo de desvios
    nominal_voltage: float = 220.0
    nominal_current: float = 10.0
    max_case_temperature: float = 60.0
    voltage_deviation_percent: float = 10.0
    current_deviation_percent: float = 10.0
    
    class Config:
        """Configuração do Pydantic."""
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    
    Returns:
        Settings: Objeto com as configurações do servidor
    """
    return Settings()
