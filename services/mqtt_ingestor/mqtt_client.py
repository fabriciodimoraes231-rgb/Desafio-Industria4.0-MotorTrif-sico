"""
Cliente MQTT assíncrono para recebimento de dados dos sensores.

Este módulo implementa o cliente MQTT que se conecta ao broker externo
e recebe os dados dos sensores do motor trifásico.
"""

import asyncio
import json
import logging
from typing import Callable, Optional, Any
from gmqtt import Client as GMQTTClient
from gmqtt.mqtt.constants import MQTTv311

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    Cliente MQTT assíncrono para conexão com broker externo.
    
    Esta classe gerencia a conexão com o broker MQTT, subscrição aos
    tópicos dos sensores e processamento das mensagens recebidas.
    
    Attributes:
        settings: Configurações do serviço
        client: Instância do cliente GMQTT
        on_message_callback: Callback para processar mensagens recebidas
        _connected: Flag de conexão
        
    Example:
        >>> async def handler(topic, data):
        ...     print(f"Recebido de {topic}: {data}")
        >>> client = MQTTClient()
        >>> client.set_message_callback(handler)
        >>> await client.connect()
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o cliente MQTT.
        
        Args:
            settings: Configurações do serviço (usa padrão se não fornecido)
        """
        self.settings = settings or get_settings()
        self.client: Optional[GMQTTClient] = None
        self.on_message_callback: Optional[Callable] = None
        self._connected = False
        self._reconnect_interval = 5
        
    def set_message_callback(self, callback: Callable[[str, dict], Any]):
        """
        Define o callback para processar mensagens recebidas.
        
        Args:
            callback: Função assíncrona que recebe (topic, data)
        """
        self.on_message_callback = callback
        
    async def connect(self):
        """
        Conecta ao broker MQTT e subscreve aos tópicos.
        
        Raises:
            ConnectionError: Se não conseguir conectar ao broker
        """
        self.client = GMQTTClient(self.settings.mqtt_client_id)
        
        # Configurar callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        
        logger.info(f"Conectando ao broker MQTT: {self.settings.mqtt_broker}:{self.settings.mqtt_port}")
        
        try:
            await self.client.connect(
                self.settings.mqtt_broker,
                self.settings.mqtt_port,
                version=MQTTv311
            )
            self._connected = True
        except Exception as e:
            logger.error(f"Erro ao conectar ao broker MQTT: {e}")
            raise ConnectionError(f"Falha na conexão MQTT: {e}")
            
    async def disconnect(self):
        """Desconecta do broker MQTT."""
        if self.client and self._connected:
            await self.client.disconnect()
            self._connected = False
            logger.info("Desconectado do broker MQTT")
            
    def _on_connect(self, client, flags, rc, properties):
        """
        Callback executado quando conecta ao broker.
        
        Args:
            client: Instância do cliente
            flags: Flags de conexão
            rc: Código de retorno
            properties: Propriedades da conexão
        """
        logger.info(f"Conectado ao broker MQTT (rc={rc})")
        
        # Subscrever aos tópicos
        for topic in self.settings.mqtt_topics:
            client.subscribe(topic, qos=1)
            logger.info(f"Subscrito ao tópico: {topic}")
            
    def _on_disconnect(self, client, packet, exc=None):
        """
        Callback executado quando desconecta do broker.
        
        Args:
            client: Instância do cliente
            packet: Pacote de desconexão
            exc: Exceção que causou a desconexão (se houver)
        """
        self._connected = False
        if exc:
            logger.warning(f"Desconectado do broker MQTT: {exc}")
        else:
            logger.info("Desconectado do broker MQTT")
            
    def _on_subscribe(self, client, mid, qos, properties):
        """
        Callback executado quando subscrição é confirmada.
        
        Args:
            client: Instância do cliente
            mid: ID da mensagem
            qos: QoS concedido
            properties: Propriedades da subscrição
        """
        logger.debug(f"Subscrição confirmada (mid={mid}, qos={qos})")
        
    def _on_message(self, client, topic, payload, qos, properties):
        """
        Callback executado quando recebe uma mensagem.
        
        Args:
            client: Instância do cliente
            topic: Tópico da mensagem
            payload: Conteúdo da mensagem
            qos: QoS da mensagem
            properties: Propriedades da mensagem
        """
        try:
            # Decodificar JSON
            data = json.loads(payload.decode('utf-8'))
            logger.debug(f"Mensagem recebida de {topic}: {data}")
            
            # Chamar callback se definido
            if self.on_message_callback:
                coro = self._process_message(topic, data)
                try:
                    asyncio.create_task(coro)
                except RuntimeError:
                    coro.close()
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON de {topic}: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem de {topic}: {e}")
            
        return 0  # Retornar 0 para indicar sucesso
        
    async def _process_message(self, topic: str, data: dict):
        """
        Processa a mensagem recebida de forma assíncrona.
        
        Args:
            topic: Tópico da mensagem
            data: Dados decodificados da mensagem
        """
        try:
            await self.on_message_callback(topic, data)
        except Exception as e:
            logger.error(f"Erro no callback de mensagem: {e}")
            
    @property
    def is_connected(self) -> bool:
        """Retorna True se conectado ao broker."""
        return self._connected
        
    async def run_forever(self):
        """
        Mantém a conexão ativa indefinidamente.
        
        Implementa reconexão automática em caso de desconexão.
        """
        while True:
            if not self._connected:
                try:
                    await self.connect()
                except Exception as e:
                    logger.error(f"Erro na reconexão: {e}")
                    await asyncio.sleep(self._reconnect_interval)
                    continue
                    
            await asyncio.sleep(1)
