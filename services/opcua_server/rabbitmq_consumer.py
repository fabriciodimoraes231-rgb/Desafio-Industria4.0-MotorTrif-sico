"""
Consumidor RabbitMQ para o servidor OPC UA.

Este módulo implementa o consumidor que recebe dados do serviço
de ingestão MQTT e atualiza as variáveis do servidor OPC UA.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import aio_pika
from aio_pika import IncomingMessage

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """
    Consumidor assíncrono para RabbitMQ.
    
    Recebe mensagens das filas de dados do motor e processa
    para atualização do servidor OPC UA.
    
    Attributes:
        settings: Configurações do serviço
        connection: Conexão com o RabbitMQ
        channel: Canal de comunicação
        on_message_callback: Callback para processar mensagens
        
    Example:
        >>> consumer = RabbitMQConsumer()
        >>> consumer.set_message_callback(handler)
        >>> await consumer.connect()
        >>> await consumer.start_consuming()
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o consumidor RabbitMQ.
        
        Args:
            settings: Configurações (usa padrão se não fornecido)
        """
        self.settings = settings or get_settings()
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.on_message_callback: Optional[Callable] = None
        self._consuming = False
        self._queues = []
        
    def set_message_callback(self, callback: Callable[[str, Dict], Any]):
        """
        Define callback para processar mensagens.
        
        Args:
            callback: Função assíncrona que recebe (sensor_type, data)
        """
        self.on_message_callback = callback
        
    async def connect(self):
        """
        Conecta ao RabbitMQ.
        
        Raises:
            ConnectionError: Se não conseguir conectar
        """
        url = f"amqp://{self.settings.rabbitmq_user}:{self.settings.rabbitmq_pass}@{self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}/"
        
        logger.info(f"Conectando ao RabbitMQ: {self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}")
        
        try:
            self.connection = await aio_pika.connect_robust(url)
            self.channel = await self.connection.channel()
            
            # Configurar prefetch para controle de fluxo
            await self.channel.set_qos(prefetch_count=10)
            
            logger.info("Conectado ao RabbitMQ com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao RabbitMQ: {e}")
            raise ConnectionError(f"Falha na conexão RabbitMQ: {e}")
            
    async def close(self):
        """Fecha conexão com o RabbitMQ."""
        self._consuming = False
        
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Conexão RabbitMQ fechada")
            
    async def start_consuming(self):
        """
        Inicia o consumo de mensagens das filas.
        
        Subscreve a fila que recebe todas as mensagens do motor.
        """
        if not self.channel:
            raise RuntimeError("Não conectado ao RabbitMQ")
            
        # Nome da fila que recebe todas as mensagens
        queue_name = f"{self.settings.rabbitmq_queue}.all"
        
        try:
            # Declarar fila (será criada pelo publisher se não existir)
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                passive=True  # Não criar, apenas verificar existência
            )
        except aio_pika.exceptions.ChannelNotFoundEntity:
            # Se fila não existe, criar
            logger.warning(f"Fila {queue_name} não encontrada, criando...")
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True
            )
            
        # Consumir mensagens
        self._consuming = True
        self._queues.append(queue)
        
        await queue.consume(self._process_message)
        logger.info(f"Consumindo da fila: {queue_name}")
        
    async def _process_message(self, message: IncomingMessage):
        """
        Processa uma mensagem recebida.
        
        Args:
            message: Mensagem do RabbitMQ
        """
        async with message.process():
            try:
                # Decodificar JSON
                data = json.loads(message.body.decode())
                
                # Extrair tipo do sensor
                sensor_type = data.get('_sensor_type', 'unknown')
                
                logger.debug(f"Mensagem recebida: {sensor_type}")
                
                # Chamar callback
                if self.on_message_callback:
                    await self.on_message_callback(sensor_type, data)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON: {e}")
            except Exception as e:
                logger.error(f"Erro ao processar mensagem: {e}")
                
    async def consume_specific_queue(self, sensor_type: str):
        """
        Consome de uma fila específica.
        
        Args:
            sensor_type: Tipo do sensor (electrical, environment, vibration)
        """
        if not self.channel:
            raise RuntimeError("Não conectado ao RabbitMQ")
            
        queue_name = f"{self.settings.rabbitmq_queue}.{sensor_type}"
        
        try:
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                passive=True
            )
            
            self._queues.append(queue)
            await queue.consume(self._process_message)
            logger.info(f"Consumindo da fila: {queue_name}")
            
        except Exception as e:
            logger.error(f"Erro ao consumir fila {queue_name}: {e}")
            
    @property
    def is_connected(self) -> bool:
        """Retorna True se conectado ao RabbitMQ."""
        return self.connection is not None and not self.connection.is_closed
        
    @property
    def is_consuming(self) -> bool:
        """Retorna True se está consumindo mensagens."""
        return self._consuming


def extract_variable_values(sensor_type: str, data: Dict) -> Dict[str, float]:
    """
    Extrai valores de variáveis de uma mensagem de sensor.
    
    Converte a estrutura da mensagem MQTT para um dicionário
    plano com os nomes das variáveis OPC UA.
    
    Args:
        sensor_type: Tipo do sensor (electrical, environment, vibration)
        data: Dados da mensagem
        
    Returns:
        Dicionário com nome da variável OPC UA e valor
    """
    values = {}
    
    if sensor_type == "electrical":
        # Tensões
        voltage = data.get("voltage", {})
        values["VoltageA"] = voltage.get("a", 0)
        values["VoltageB"] = voltage.get("b", 0)
        values["VoltageC"] = voltage.get("c", 0)
        
        # Correntes
        current = data.get("current", {})
        values["CurrentA"] = current.get("a", 0)
        values["CurrentB"] = current.get("b", 0)
        values["CurrentC"] = current.get("c", 0)
        
        # Potências
        power = data.get("power", {})
        values["PowerActive"] = power.get("active", 0)
        values["PowerReactive"] = power.get("reactive", 0)
        values["PowerApparent"] = power.get("apparent", 0)
        
        # Energias
        energy = data.get("energy", {})
        values["EnergyActive"] = energy.get("active", 0)
        values["EnergyReactive"] = energy.get("reactive", 0)
        values["EnergyApparent"] = energy.get("apparent", 0)
        
        # Outros
        values["PowerFactor"] = data.get("powerFactor", 0)
        values["Frequency"] = data.get("frequency", 0)
        
    elif sensor_type == "environment":
        values["Temperature"] = data.get("temperature", 0)
        values["Humidity"] = data.get("humidity", 0)
        values["CaseTemperature"] = data.get("caseTemperature", 0)
        
    elif sensor_type == "vibration":
        values["Axial"] = data.get("axial", 0)
        values["Radial"] = data.get("radial", 0)
        
    return values
