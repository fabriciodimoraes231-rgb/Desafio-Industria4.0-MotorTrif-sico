"""
Configurações do serviço de ingestão MQTT.

Este módulo contém as configurações carregadas via variáveis de ambiente
para o serviço de ingestão MQTT.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações do serviço de ingestão MQTT.
    
    Attributes:
        mqtt_broker: Endereço do broker MQTT externo
        mqtt_port: Porta do broker MQTT
        mqtt_client_id: ID do cliente MQTT
        mqtt_topics: Lista de tópicos para subscrição
        rabbitmq_host: Host do RabbitMQ
        rabbitmq_port: Porta do RabbitMQ
        rabbitmq_user: Usuário do RabbitMQ
        rabbitmq_pass: Senha do RabbitMQ
        rabbitmq_exchange: Nome do exchange no RabbitMQ
        rabbitmq_queue: Nome da fila no RabbitMQ
    """
    
    # MQTT Configuration
    mqtt_broker: str = "lse.dev.br"
    mqtt_port: int = 1883
    mqtt_client_id: str = "motor50cv-mqtt-ingestor"
    mqtt_topics: list[str] = [
        "scgdi/motor/electrical",
        "scgdi/motor/environment", 
        "scgdi/motor/vibration"
    ]
    
    # RabbitMQ Configuration
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_pass: str = "admin123"
    rabbitmq_exchange: str = "motor_data"
    rabbitmq_queue: str = "motor_readings"
    
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
