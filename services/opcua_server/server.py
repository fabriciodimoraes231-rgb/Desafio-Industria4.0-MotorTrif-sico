"""
Servidor OPC UA para Motor 50CV.

Este modulo implementa o servidor OPC UA principal que expoe as
variaveis do motor trifasico 50CV para clientes OPC UA.

O servidor:
- Consome dados do RabbitMQ (provenientes do MQTT Ingestor)
- Atualiza as variaveis OPC UA em tempo real
- Historiza dados de variaveis selecionadas em SQLite
- Gera alarmes baseados em regras de limites

Classes:
    OPCUAServer: Servidor OPC UA principal

Example:
    >>> server = OPCUAServer()
    >>> await server.initialize()
    >>> await server.start()
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from datetime import timedelta
from asyncua import Server, ua
from asyncua.common.node import Node

from config import Settings, get_settings
from nodeset import NodesetBuilder
from alarms import AlarmManager
from history_storage import HistoryStorageSQLite
from rabbitmq_consumer import RabbitMQConsumer, extract_variable_values

logger = logging.getLogger(__name__)


class OPCUAServer:
    """
    Servidor OPC UA para monitoramento do Motor 50CV.
    
    Esta classe implementa o servidor OPC UA completo, incluindo:
    - Criacao da estrutura de nos (nodeset)
    - Consumo de dados do RabbitMQ
    - Atualizacao de variaveis OPC UA
    - Historização de dados em SQLite
    - Geracao de alarmes
    
    Attributes:
        settings: Configuracoes do servidor
        server: Instancia do servidor asyncua
        namespace_idx: Indice do namespace do motor
        nodes: Dicionario de nos OPC UA
        alarm_manager: Gerenciador de alarmes
        history_storage: Storage de historico SQLite
        rabbitmq_consumer: Consumidor RabbitMQ
        
    Example:
        >>> server = OPCUAServer()
        >>> await server.initialize()
        >>> await server.start()
        >>> # ... servidor rodando ...
        >>> await server.stop()
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o servidor OPC UA.
        
        Args:
            settings: Configuracoes do servidor (usa padrao se nao fornecido)
        """
        self.settings = settings or get_settings()
        self.server: Optional[Server] = None
        self.namespace_idx: Optional[int] = None
        self.nodes: Dict[str, Node] = {}
        self.alarm_manager: Optional[AlarmManager] = None
        self.history_storage: Optional[HistoryStorageSQLite] = None
        self.rabbitmq_consumer: Optional[RabbitMQConsumer] = None
        self._running = False
        self._lds_task: Optional[asyncio.Task] = None
        self._last_values: Dict[str, float] = {}
        self._historized_nodes: List[Node] = []
        self._stats = {
            "messages_processed": 0,
            "alarms_generated": 0,
            "history_records": 0
        }
        
    async def initialize(self):
        """
        Inicializa o servidor, nodeset, alarmes e historico.
        
        Configura todos os componentes necessarios para o funcionamento
        do servidor OPC UA.
        
        Raises:
            RuntimeError: Se falhar ao inicializar componentes
        """
        logger.info("Inicializando servidor OPC UA...")
        
        self.server = Server()
        await self.server.init()
        
        self.server.set_endpoint(self.settings.opcua_endpoint)
        self.server.set_server_name(self.settings.opcua_name)
        
        self.namespace_idx = await self.server.register_namespace(
            self.settings.opcua_namespace
        )
        
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        
        nodeset_builder = NodesetBuilder(self.server, self.namespace_idx)
        self.nodes = await nodeset_builder.build()
        
        self.history_storage = HistoryStorageSQLite(
            db_path=self.settings.database_path,
            max_history_data_response_size=10000
        )
        await self.history_storage.init()
        self.server.iserver.history_manager.set_storage(self.history_storage)
        
        self.alarm_manager = AlarmManager(self.server, self.nodes, self.settings)
        await self.alarm_manager.initialize()
        self.alarm_manager.set_alarm_callback(self._on_alarm)
        
        self.rabbitmq_consumer = RabbitMQConsumer(self.settings)
        self.rabbitmq_consumer.set_message_callback(self._on_sensor_data)
        
        logger.info("Servidor OPC UA inicializado")
        
    async def start(self):
        """
        Inicia o servidor e comeca a consumir mensagens do RabbitMQ.
        
        Apos o inicio, o servidor estara disponivel para conexoes
        de clientes OPC UA.
        """
        if self._running:
            return
            
        logger.info("Iniciando servidor OPC UA...")
        
        await self.server.start()
        self._running = True
        
        logger.info(f"Servidor rodando em: {self.settings.opcua_endpoint}")
        
        await self._enable_opcua_history()
        
        try:
            await self.rabbitmq_consumer.connect()
            await self.rabbitmq_consumer.start_consuming()
        except Exception as e:
            logger.error(f"Erro ao conectar ao RabbitMQ: {e}")
            
        self._lds_task = asyncio.create_task(self._register_lds_periodic())
        
    async def stop(self):
        """
        Para o servidor e fecha conexoes.
        
        Realiza shutdown graceful de todos os componentes.
        """
        logger.info("Parando servidor OPC UA...")
        self._running = False
        
        if self._lds_task:
            self._lds_task.cancel()
            try:
                await self._lds_task
            except asyncio.CancelledError:
                pass
                
        if self.rabbitmq_consumer:
            await self.rabbitmq_consumer.close()
            
        for node in self._historized_nodes:
            try:
                await self.server.dehistorize_node_data_change(node)
            except Exception:
                pass
                
        if self.history_storage:
            await self.history_storage.stop()
            
        if self.server:
            await self.server.stop()
            
        logger.info("Servidor OPC UA parado")
        logger.info(f"Estatisticas: {self._stats}")
        
    async def _enable_opcua_history(self):
        """
        Habilita historizacao para variaveis eletricas e temperatura.
        
        Configura as variaveis que terao seus valores armazenados
        no historico para consulta posterior.
        """
        historized_variables = [
            "VoltageA", "VoltageB", "VoltageC",
            "CurrentA", "CurrentB", "CurrentC",
            "PowerActive", "PowerReactive", "PowerApparent",
            "EnergyActive", "EnergyReactive", "EnergyApparent",
            "PowerFactor", "Frequency",
            "CaseTemperature"
        ]
        
        for var_name in historized_variables:
            node = self.nodes.get(var_name)
            if node:
                try:
                    await self.server.historize_node_data_change(
                        node,
                        period=timedelta(days=7),
                        count=0
                    )
                    self._historized_nodes.append(node)
                    await self.history_storage.register_variable_mapping(var_name, node.nodeid)
                except Exception as e:
                    logger.warning(f"Erro ao habilitar histórico para {var_name}: {e}")
                    
        logger.info(f"Historização habilitada para {len(self._historized_nodes)} variáveis")
        
    async def _on_sensor_data(self, sensor_type: str, data: Dict):
        """Processa dados recebidos do RabbitMQ."""
        try:
            values = extract_variable_values(sensor_type, data)
            
            timestamp_str = data.get("timestamp")
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.now(timezone.utc)
            
            await self._update_variables(values, timestamp)
            
            alarms = await self.alarm_manager.check_values(values)
            self._stats["alarms_generated"] += len(alarms)
            self._stats["messages_processed"] += 1
            self._last_values.update(values)
            
        except Exception as e:
            logger.error(f"Erro ao processar dados do sensor {sensor_type}: {e}")
            
    async def _update_variables(self, values: Dict[str, float], timestamp: datetime):
        """Atualiza valores das variáveis OPC UA."""
        for name, value in values.items():
            node = self.nodes.get(name)
            if node:
                try:
                    dv = ua.DataValue(
                        ua.Variant(float(value), ua.VariantType.Double),
                        SourceTimestamp=timestamp,
                        ServerTimestamp=datetime.now(timezone.utc)
                    )
                    await node.write_value(dv)
                except Exception as e:
                    logger.error(f"Erro ao atualizar {name}: {e}")
                    
    async def _on_alarm(self, alarm):
        """Processa e persiste alarme gerado."""
        await self.alarm_manager.generate_event(alarm)
        if self.history_storage:
            await self.history_storage.save_alarm(alarm.to_dict())
        
    async def _register_lds_periodic(self):
        """Registra periodicamente no LDS."""
        while self._running:
            try:
                await self._register_lds()
            except Exception:
                pass
            await asyncio.sleep(self.settings.lds_register_interval)
            
    async def _register_lds(self):
        """Registra servidor no Local Discovery Server."""
        try:
            from asyncua import Client
            
            async with Client(self.settings.lds_url, timeout=5) as lds_client:
                await lds_client.connect()
                
                server_info = ua.RegisteredServer()
                server_info.ServerUri = self.server.application_uri if self.server else f"urn:{self.settings.opcua_name}"
                server_info.ProductUri = "urn:motor50cv:opcua:server"
                server_info.ServerNames = [ua.LocalizedText("Motor50CV OPC UA Server")]
                server_info.ServerType = ua.ApplicationType.Server
                server_info.IsOnline = True
                server_info.DiscoveryUrls = [f"opc.tcp://{self.settings.opcua_host}:{self.settings.opcua_port}"]
                
                await lds_client.register_server(server_info)
                logger.info(f"Registrado no LDS: {self.settings.lds_url}")
                
        except Exception:
            pass
            
    def get_latest_values(self) -> Dict[str, Any]:
        """Retorna últimos valores das variáveis."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "variables": self._last_values.copy(),
            "alarm_count": len(self.alarm_manager.get_active_alarms()) if self.alarm_manager else 0
        }
        
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas do servidor."""
        return self._stats.copy()
        
    async def read_variable(self, name: str) -> Optional[float]:
        """Lê valor atual de uma variável."""
        node = self.nodes.get(name)
        if node:
            try:
                value = await node.read_value()
                return float(value)
            except Exception:
                pass
        return None
        
    async def write_variable(self, name: str, value: float) -> bool:
        """Escreve valor em uma variável."""
        node = self.nodes.get(name)
        if node:
            try:
                await node.write_value(float(value))
                return True
            except Exception:
                pass
        return False
