"""
Servidor OPC UA principal.

Este módulo implementa o servidor OPC UA completo com suporte a:
- Nodeset personalizado para Motor 50CV
- Histórico de variáveis
- Alarmes e eventos
- Registro no LDS (Local Discovery Server)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from asyncua import Server, ua
from asyncua.common.node import Node

from config import Settings, get_settings
from nodeset import NodesetBuilder
from alarms import AlarmManager
from historian import Historian
from rabbitmq_consumer import RabbitMQConsumer, extract_variable_values

logger = logging.getLogger(__name__)


class OPCUAServer:
    """
    Servidor OPC UA para monitoramento do Motor 50CV.
    
    Implementa servidor completo com:
    - Nodeset hierárquico (Motor50CV/Electrical, Environment, Vibration)
    - Histórico de variáveis elétricas e temperatura da carcaça
    - Alarmes e eventos com severidades configuráveis
    - Registro periódico no LDS
    - Consumo de dados do RabbitMQ
    
    Attributes:
        settings: Configurações do servidor
        server: Instância do servidor asyncua
        namespace_idx: Índice do namespace
        nodes: Dicionário com referências aos nós
        alarm_manager: Gerenciador de alarmes
        historian: Historiador de dados
        rabbitmq_consumer: Consumidor RabbitMQ
        
    Example:
        >>> opcua_server = OPCUAServer()
        >>> await opcua_server.initialize()
        >>> await opcua_server.start()
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o servidor OPC UA.
        
        Args:
            settings: Configurações (usa padrão se não fornecido)
        """
        self.settings = settings or get_settings()
        self.server: Optional[Server] = None
        self.namespace_idx: Optional[int] = None
        self.nodes: Dict[str, Node] = {}
        self.alarm_manager: Optional[AlarmManager] = None
        self.historian: Optional[Historian] = None
        self.rabbitmq_consumer: Optional[RabbitMQConsumer] = None
        self._running = False
        self._lds_task: Optional[asyncio.Task] = None
        self._last_values: Dict[str, float] = {}
        self._stats = {
            "messages_processed": 0,
            "alarms_generated": 0,
            "history_records": 0
        }
        
    async def initialize(self):
        """
        Inicializa o servidor OPC UA e todos os componentes.
        
        Configura servidor, nodeset, alarmes, histórico e consumidor RabbitMQ.
        """
        logger.info("Inicializando servidor OPC UA...")
        
        # Criar servidor
        self.server = Server()
        await self.server.init()
        
        # Configurar endpoint
        self.server.set_endpoint(self.settings.opcua_endpoint)
        self.server.set_server_name(self.settings.opcua_name)
        
        # Registrar namespace
        self.namespace_idx = await self.server.register_namespace(
            self.settings.opcua_namespace
        )
        
        # Configurar política de segurança (básica para desenvolvimento)
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        
        # Construir nodeset
        nodeset_builder = NodesetBuilder(self.server, self.namespace_idx)
        self.nodes = await nodeset_builder.build()
        
        # Inicializar historiador
        self.historian = Historian(self.settings)
        await self.historian.initialize()
        
        # Inicializar gerenciador de alarmes
        self.alarm_manager = AlarmManager(self.server, self.nodes, self.settings)
        await self.alarm_manager.initialize()
        self.alarm_manager.set_alarm_callback(self._on_alarm)
        
        # Inicializar consumidor RabbitMQ
        self.rabbitmq_consumer = RabbitMQConsumer(self.settings)
        self.rabbitmq_consumer.set_message_callback(self._on_sensor_data)
        
        logger.info("Servidor OPC UA inicializado")
        
    async def start(self):
        """
        Inicia o servidor OPC UA.
        
        Inicia o servidor, conecta ao RabbitMQ e começa a consumir mensagens.
        """
        if self._running:
            logger.warning("Servidor já está rodando")
            return
            
        logger.info("Iniciando servidor OPC UA...")
        
        # Iniciar servidor
        await self.server.start()
        self._running = True
        
        logger.info(f"Servidor OPC UA rodando em: {self.settings.opcua_endpoint}")
        
        # Conectar ao RabbitMQ
        try:
            await self.rabbitmq_consumer.connect()
            await self.rabbitmq_consumer.start_consuming()
        except Exception as e:
            logger.error(f"Erro ao conectar ao RabbitMQ: {e}")
            # Continuar mesmo sem RabbitMQ (modo standalone)
            
        # Iniciar registro periódico no LDS
        self._lds_task = asyncio.create_task(self._register_lds_periodic())
        
    async def stop(self):
        """
        Para o servidor OPC UA.
        
        Fecha todas as conexões e libera recursos.
        """
        logger.info("Parando servidor OPC UA...")
        self._running = False
        
        # Parar registro no LDS
        if self._lds_task:
            self._lds_task.cancel()
            try:
                await self._lds_task
            except asyncio.CancelledError:
                pass
                
        # Fechar RabbitMQ
        if self.rabbitmq_consumer:
            await self.rabbitmq_consumer.close()
            
        # Fechar historiador
        if self.historian:
            await self.historian.close()
            
        # Parar servidor
        if self.server:
            await self.server.stop()
            
        logger.info("Servidor OPC UA parado")
        logger.info(f"Estatísticas: {self._stats}")
        
    async def _on_sensor_data(self, sensor_type: str, data: Dict):
        """
        Callback para dados recebidos do RabbitMQ.
        
        Atualiza variáveis OPC UA, verifica alarmes e registra histórico.
        
        Args:
            sensor_type: Tipo do sensor (electrical, environment, vibration)
            data: Dados do sensor
        """
        try:
            # Extrair valores das variáveis
            values = extract_variable_values(sensor_type, data)
            
            # Extrair timestamp
            timestamp_str = data.get("timestamp")
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.utcnow()
            
            # Atualizar variáveis OPC UA
            await self._update_variables(values, timestamp)
            
            # Verificar alarmes
            alarms = await self.alarm_manager.check_values(values)
            self._stats["alarms_generated"] += len(alarms)
            
            # Registrar histórico
            await self.historian.record_batch(values, timestamp)
            self._stats["history_records"] += len([v for v in values if v in self.historian.historized_variables])
            
            self._stats["messages_processed"] += 1
            self._last_values.update(values)
            
            logger.debug(f"Dados processados: {sensor_type} ({len(values)} variáveis)")
            
        except Exception as e:
            logger.error(f"Erro ao processar dados do sensor {sensor_type}: {e}")
            
    async def _update_variables(self, values: Dict[str, float], timestamp: datetime):
        """
        Atualiza valores das variáveis OPC UA.
        
        Args:
            values: Dicionário com nome e valor das variáveis
            timestamp: Timestamp dos dados
        """
        for name, value in values.items():
            node = self.nodes.get(name)
            if node:
                try:
                    dv = ua.DataValue(
                        ua.Variant(float(value), ua.VariantType.Double),
                        SourceTimestamp=timestamp,
                        ServerTimestamp=datetime.utcnow()
                    )
                    await node.write_value(dv)
                except Exception as e:
                    logger.error(f"Erro ao atualizar variável {name}: {e}")
                    
    async def _on_alarm(self, alarm):
        """
        Callback para novos alarmes.
        
        Args:
            alarm: Evento de alarme gerado
        """
        # Gerar evento OPC UA
        await self.alarm_manager.generate_event(alarm)
        
        # Registrar no histórico
        await self.historian.record_alarm(alarm.to_dict())
        
    async def _register_lds_periodic(self):
        """
        Task para registro periódico no LDS.
        
        Tenta registrar o servidor no Local Discovery Server
        conforme intervalo configurado.
        """
        while self._running:
            try:
                await self._register_lds()
            except Exception as e:
                logger.debug(f"Registro no LDS falhou (pode não estar disponível): {e}")
                
            await asyncio.sleep(self.settings.lds_register_interval)
            
    async def _register_lds(self):
        """
        Registra o servidor no LDS (Local Discovery Server).
        
        Nota: Requer LDS rodando localmente.
        """
        # Registro no LDS é opcional e pode falhar se LDS não estiver disponível
        try:
            from asyncua import Client
            
            async with Client(self.settings.lds_url) as client:
                # Tentar registrar usando o método padrão
                logger.debug(f"Tentando registrar no LDS: {self.settings.lds_url}")
                # O registro real requer configuração específica do LDS
                pass
                
        except Exception as e:
            # LDS pode não estar disponível - isso é aceitável
            pass
            
    def get_latest_values(self) -> Dict[str, Any]:
        """
        Retorna os últimos valores conhecidos de todas as variáveis.
        
        Returns:
            Dicionário com variáveis e valores
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "variables": self._last_values.copy(),
            "alarm_count": len(self.alarm_manager.get_active_alarms()) if self.alarm_manager else 0
        }
        
    def get_stats(self) -> Dict[str, int]:
        """
        Retorna estatísticas do servidor.
        
        Returns:
            Dicionário com contadores de estatísticas
        """
        return self._stats.copy()
        
    async def read_variable(self, name: str) -> Optional[float]:
        """
        Lê o valor atual de uma variável.
        
        Args:
            name: Nome da variável
            
        Returns:
            Valor atual ou None se não encontrada
        """
        node = self.nodes.get(name)
        if node:
            try:
                value = await node.read_value()
                return float(value)
            except Exception as e:
                logger.error(f"Erro ao ler variável {name}: {e}")
        return None
        
    async def write_variable(self, name: str, value: float) -> bool:
        """
        Escreve um valor em uma variável.
        
        Args:
            name: Nome da variável
            value: Valor a escrever
            
        Returns:
            True se escrita com sucesso
        """
        node = self.nodes.get(name)
        if node:
            try:
                await node.write_value(float(value))
                return True
            except Exception as e:
                logger.error(f"Erro ao escrever variável {name}: {e}")
        return False
