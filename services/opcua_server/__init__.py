"""
OPC UA Server Service

Este microsserviço é responsável por:
- Criar e manter o servidor OPC UA com Nodeset personalizado
- Consumir dados do RabbitMQ e atualizar variáveis
- Gerenciar alarmes e eventos
- Manter histórico de variáveis e eventos
- Registrar-se no LDS (Local Discovery Server)

Author: Motor50CV Team
"""

from server import OPCUAServer
from nodeset import NodesetBuilder
from alarms import AlarmManager
from historian import Historian
from rabbitmq_consumer import RabbitMQConsumer
from config import Settings

__all__ = [
    "OPCUAServer",
    "NodesetBuilder",
    "AlarmManager",
    "Historian",
    "RabbitMQConsumer",
    "Settings",
]
