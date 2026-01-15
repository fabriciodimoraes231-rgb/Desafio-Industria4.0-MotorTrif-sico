"""
Ponto de entrada principal do serviço de ingestão MQTT.

Este módulo inicializa e executa o serviço de ingestão MQTT,
que recebe dados do broker externo e os publica no RabbitMQ.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from config import get_settings
from mqtt_client import MQTTClient
from rabbitmq_publisher import RabbitMQPublisher
from validators import get_validator_for_topic

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MQTTIngestorService:
    """
    Serviço principal de ingestão MQTT.
    
    Coordena a recepção de dados do broker MQTT externo,
    validação e publicação no RabbitMQ.
    
    Attributes:
        settings: Configurações do serviço
        mqtt_client: Cliente MQTT
        rabbitmq_publisher: Publisher RabbitMQ
        _running: Flag de execução
        
    Example:
        >>> service = MQTTIngestorService()
        >>> await service.start()
    """
    
    def __init__(self):
        """Inicializa o serviço de ingestão."""
        self.settings = get_settings()
        self.mqtt_client: Optional[MQTTClient] = None
        self.rabbitmq_publisher: Optional[RabbitMQPublisher] = None
        self._running = False
        self._stats = {
            "messages_received": 0,
            "messages_validated": 0,
            "messages_published": 0,
            "validation_errors": 0
        }
        
    async def start(self):
        """
        Inicia o serviço de ingestão.
        
        Conecta ao RabbitMQ e ao broker MQTT, configurando
        o fluxo de dados entre eles.
        """
        logger.info("Iniciando serviço de ingestão MQTT...")
        
        # Inicializar RabbitMQ Publisher
        self.rabbitmq_publisher = RabbitMQPublisher(self.settings)
        await self.rabbitmq_publisher.connect()
        
        # Inicializar MQTT Client
        self.mqtt_client = MQTTClient(self.settings)
        self.mqtt_client.set_message_callback(self._handle_message)
        await self.mqtt_client.connect()
        
        self._running = True
        logger.info("Serviço de ingestão MQTT iniciado com sucesso")
        
    async def stop(self):
        """
        Para o serviço de ingestão.
        
        Desconecta do broker MQTT e fecha a conexão com o RabbitMQ.
        """
        logger.info("Parando serviço de ingestão MQTT...")
        self._running = False
        
        if self.mqtt_client:
            await self.mqtt_client.disconnect()
            
        if self.rabbitmq_publisher:
            await self.rabbitmq_publisher.close()
            
        logger.info("Serviço de ingestão MQTT parado")
        logger.info(f"Estatísticas: {self._stats}")
        
    async def _handle_message(self, topic: str, data: dict):
        """
        Processa mensagens recebidas do MQTT.
        
        Valida os dados e publica no RabbitMQ se válidos.
        
        Args:
            topic: Tópico MQTT da mensagem
            data: Dados decodificados da mensagem
        """
        self._stats["messages_received"] += 1
        
        try:
            # Obter validador para o tópico
            validator = get_validator_for_topic(topic)
            
            # Validar dados
            validated_data = validator(data)
            
            if validated_data is None:
                self._stats["validation_errors"] += 1
                logger.warning(f"Dados inválidos recebidos de {topic}")
                return
                
            self._stats["messages_validated"] += 1
            
            # Extrair tipo do sensor do tópico
            sensor_type = topic.split("/")[-1]  # electrical, environment, vibration
            
            # Publicar no RabbitMQ
            await self.rabbitmq_publisher.publish(sensor_type, validated_data)
            self._stats["messages_published"] += 1
            
            logger.debug(f"Mensagem processada: {topic} -> motor.{sensor_type}")
            
        except ValueError as e:
            logger.error(f"Tópico desconhecido: {topic} - {e}")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem de {topic}: {e}")
            
    async def run_forever(self):
        """
        Executa o serviço indefinidamente.
        
        Mantém o serviço rodando e processa mensagens até ser interrompido.
        """
        await self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
                
                # Log periódico de estatísticas
                if self._stats["messages_received"] % 100 == 0 and self._stats["messages_received"] > 0:
                    logger.info(f"Estatísticas: {self._stats}")
                    
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
            
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do serviço.
        
        Returns:
            Dicionário com estatísticas de processamento
        """
        return self._stats.copy()


async def main():
    """
    Função principal de execução do serviço.
    
    Configura handlers de sinal e inicia o serviço.
    """
    service = MQTTIngestorService()
    
    # Configurar handlers de sinal para shutdown graceful
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Sinal de interrupção recebido")
        asyncio.create_task(service.stop())
        
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
        
    try:
        await service.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupção por teclado")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
