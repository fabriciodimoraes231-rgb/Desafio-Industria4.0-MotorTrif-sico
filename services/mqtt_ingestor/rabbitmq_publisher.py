"""
Publisher RabbitMQ para envio de dados dos sensores.

Este módulo implementa o publicador que envia os dados validados
dos sensores para as filas do RabbitMQ.
"""

import asyncio
import json
import logging
from typing import Optional, Any
from datetime import datetime
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """
    Publisher assíncrono para RabbitMQ.
    
    Esta classe gerencia a conexão com o RabbitMQ e o envio de mensagens
    para as filas de dados do motor.
    
    Attributes:
        settings: Configurações do serviço
        connection: Conexão com o RabbitMQ
        channel: Canal de comunicação
        exchange: Exchange para publicação de mensagens
        
    Example:
        >>> publisher = RabbitMQPublisher()
        >>> await publisher.connect()
        >>> await publisher.publish("electrical", {"voltage": 220})
        >>> await publisher.close()
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o publisher RabbitMQ.
        
        Args:
            settings: Configurações do serviço (usa padrão se não fornecido)
        """
        self.settings = settings or get_settings()
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self._connected = False
        
    async def connect(self):
        """
        Conecta ao RabbitMQ e configura exchange e filas.
        
        Raises:
            ConnectionError: Se não conseguir conectar ao RabbitMQ
        """
        url = f"amqp://{self.settings.rabbitmq_user}:{self.settings.rabbitmq_pass}@{self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}/"
        
        logger.info(f"Conectando ao RabbitMQ: {self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}")
        
        try:
            # Conexão robusta com reconexão automática
            self.connection = await aio_pika.connect_robust(url)
            self.channel = await self.connection.channel()
            
            # Declarar exchange do tipo topic
            self.exchange = await self.channel.declare_exchange(
                self.settings.rabbitmq_exchange,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Declarar filas para cada tipo de sensor
            queues = {
                "electrical": "motor.electrical",
                "environment": "motor.environment",
                "vibration": "motor.vibration",
                "all": "motor.#"  # Fila que recebe todas as mensagens
            }
            
            for name, routing_key in queues.items():
                queue = await self.channel.declare_queue(
                    f"{self.settings.rabbitmq_queue}.{name}",
                    durable=True
                )
                await queue.bind(self.exchange, routing_key)
                logger.info(f"Fila '{queue.name}' configurada com routing_key '{routing_key}'")
                
            self._connected = True
            logger.info("Conectado ao RabbitMQ com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao RabbitMQ: {e}")
            raise ConnectionError(f"Falha na conexão RabbitMQ: {e}")
            
    async def close(self):
        """Fecha a conexão com o RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            self._connected = False
            logger.info("Conexão RabbitMQ fechada")
            
    async def publish(self, sensor_type: str, data: Any, routing_key: Optional[str] = None):
        """
        Publica uma mensagem na fila do RabbitMQ.
        
        Args:
            sensor_type: Tipo do sensor (electrical, environment, vibration)
            data: Dados a serem publicados (dict ou Pydantic model)
            routing_key: Chave de roteamento (opcional, usa sensor_type se não fornecido)
            
        Raises:
            RuntimeError: Se não estiver conectado ao RabbitMQ
            
        Example:
            >>> await publisher.publish("electrical", {"voltage": {"a": 220, "b": 221, "c": 219}})
        """
        if not self._connected or not self.exchange:
            raise RuntimeError("Não conectado ao RabbitMQ")
            
        # Converter para dict se for Pydantic model
        if hasattr(data, 'model_dump'):
            message_data = data.model_dump(mode='json')
        elif hasattr(data, 'dict'):
            message_data = data.dict()
        else:
            message_data = data
            
        # Adicionar metadados
        message_data['_sensor_type'] = sensor_type
        message_data['_received_at'] = datetime.utcnow().isoformat()
        
        # Determinar routing key
        rk = routing_key or f"motor.{sensor_type}"
        
        # Criar mensagem
        message = Message(
            body=json.dumps(message_data, default=str).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        # Publicar
        await self.exchange.publish(message, routing_key=rk)
        logger.debug(f"Mensagem publicada: routing_key={rk}")
        
    @property
    def is_connected(self) -> bool:
        """Retorna True se conectado ao RabbitMQ."""
        return self._connected and self.connection is not None and not self.connection.is_closed
        
    async def health_check(self) -> bool:
        """
        Verifica a saúde da conexão com o RabbitMQ.
        
        Returns:
            True se a conexão está saudável, False caso contrário
        """
        try:
            if not self.is_connected:
                return False
            # Tentar declarar uma queue temporária para verificar conexão
            if self.channel:
                await self.channel.declare_queue("health_check", auto_delete=True)
                return True
        except Exception as e:
            logger.error(f"Health check falhou: {e}")
        return False
