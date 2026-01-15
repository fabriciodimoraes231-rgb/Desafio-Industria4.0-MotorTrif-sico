"""
Gerenciador de Alarmes e Eventos OPC UA.

Este módulo implementa a lógica de alarmes e eventos do servidor OPC UA,
monitorando os valores das variáveis e gerando alertas conforme as regras.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import IntEnum
from asyncua import ua, Server
from asyncua.common.node import Node

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class Severity(IntEnum):
    """
    Níveis de severidade para alarmes OPC UA.
    
    Valores conforme especificação:
    - INFORMATIVE (100): Eventos de status, heartbeat
    - LOW (250): Vibração leve ou pequenas variações
    - MEDIUM (500): Temperatura levemente acima do esperado
    - HIGH (700): Sobrecorrente ou sobretensão moderada
    - CRITICAL (900): Temperatura da carcaça acima de 60°C
    """
    INFORMATIVE = 100
    LOW = 250
    MEDIUM = 500
    HIGH = 700
    CRITICAL = 900


@dataclass
class AlarmEvent:
    """
    Representa um evento de alarme.
    
    Attributes:
        timestamp: Data/hora do evento
        category: Categoria do alarme (Electrical, Environment, Vibration)
        severity: Nível de severidade
        message: Mensagem descritiva
        source_name: Nome da variável fonte
        value: Valor que disparou o alarme
        acknowledged: Se o alarme foi reconhecido
    """
    timestamp: datetime
    category: str
    severity: Severity
    message: str
    source_name: str
    value: float
    acknowledged: bool = False
    id: Optional[str] = None
    
    def __post_init__(self):
        """Gera ID único se não fornecido."""
        if self.id is None:
            self.id = f"{self.timestamp.isoformat()}_{self.source_name}"
            
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte para dicionário.
        
        Returns:
            Dicionário com dados do alarme
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "severity": self.severity.value,
            "severity_name": self.severity.name,
            "message": self.message,
            "source_name": self.source_name,
            "value": self.value,
            "acknowledged": self.acknowledged
        }


@dataclass
class AlarmRule:
    """
    Regra de alarme para monitoramento.
    
    Attributes:
        name: Nome da regra
        variable_name: Nome da variável a monitorar
        category: Categoria do alarme
        severity: Severidade quando disparado
        condition: Função que avalia se o alarme deve disparar
        message_template: Template da mensagem (usa {value})
    """
    name: str
    variable_name: str
    category: str
    severity: Severity
    message_template: str
    condition: callable
    
    def evaluate(self, value: float) -> bool:
        """
        Avalia se a condição de alarme foi atingida.
        
        Args:
            value: Valor atual da variável
            
        Returns:
            True se o alarme deve disparar
        """
        return self.condition(value)
        
    def get_message(self, value: float) -> str:
        """
        Gera mensagem do alarme.
        
        Args:
            value: Valor que disparou o alarme
            
        Returns:
            Mensagem formatada
        """
        return self.message_template.format(value=value)


class AlarmManager:
    """
    Gerenciador de alarmes e eventos OPC UA.
    
    Monitora variáveis, gera alarmes conforme regras definidas
    e mantém histórico de eventos.
    
    Attributes:
        server: Servidor OPC UA
        settings: Configurações
        rules: Lista de regras de alarme
        active_alarms: Alarmes ativos no momento
        alarm_history: Histórico de alarmes
        
    Example:
        >>> manager = AlarmManager(server, nodes)
        >>> await manager.initialize()
        >>> alarms = await manager.check_values({"VoltageA": 250.0})
    """
    
    def __init__(
        self,
        server: Server,
        nodes: Dict[str, Node],
        settings: Optional[Settings] = None
    ):
        """
        Inicializa o gerenciador de alarmes.
        
        Args:
            server: Instância do servidor OPC UA
            nodes: Dicionário com nós do servidor
            settings: Configurações (usa padrão se não fornecido)
        """
        self.server = server
        self.nodes = nodes
        self.settings = settings or get_settings()
        self.rules: List[AlarmRule] = []
        self.active_alarms: Dict[str, AlarmEvent] = {}
        self.alarm_history: List[AlarmEvent] = []
        self._event_type: Optional[Node] = None
        self._on_alarm_callback: Optional[callable] = None
        
        # Criar regras de alarme
        self._create_rules()
        
    def _create_rules(self):
        """Cria as regras de alarme conforme especificação."""
        nominal_voltage = self.settings.nominal_voltage
        nominal_current = self.settings.nominal_current
        voltage_deviation = self.settings.voltage_deviation_percent / 100
        current_deviation = self.settings.current_deviation_percent / 100
        max_case_temp = self.settings.max_case_temperature
        
        # Limites de tensão
        voltage_high = nominal_voltage * (1 + voltage_deviation)
        voltage_low = nominal_voltage * (1 - voltage_deviation)
        
        # Limites de corrente
        current_high = nominal_current * (1 + current_deviation)
        
        # Regras de Tensão (Sobretensão e Subtensão)
        for phase in ["A", "B", "C"]:
            # Sobretensão
            self.rules.append(AlarmRule(
                name=f"Overvoltage_{phase}",
                variable_name=f"Voltage{phase}",
                category="Electrical",
                severity=Severity.HIGH,
                message_template=f"Overvoltage detected on phase {phase}: {{value:.1f}}V",
                condition=lambda v, vh=voltage_high: v > vh
            ))
            
            # Subtensão
            self.rules.append(AlarmRule(
                name=f"Undervoltage_{phase}",
                variable_name=f"Voltage{phase}",
                category="Electrical",
                severity=Severity.HIGH,
                message_template=f"Undervoltage detected on phase {phase}: {{value:.1f}}V",
                condition=lambda v, vl=voltage_low: v > 0 and v < vl
            ))
            
        # Regras de Corrente (Sobrecorrente)
        for phase in ["A", "B", "C"]:
            self.rules.append(AlarmRule(
                name=f"Overcurrent_{phase}",
                variable_name=f"Current{phase}",
                category="Electrical",
                severity=Severity.HIGH,
                message_template=f"Overcurrent detected on phase {phase}: {{value:.1f}}A",
                condition=lambda v, ch=current_high: v > ch
            ))
            
        # Regra de Temperatura da Carcaça (Crítica)
        self.rules.append(AlarmRule(
            name="CaseTemperature_Critical",
            variable_name="CaseTemperature",
            category="Environment",
            severity=Severity.CRITICAL,
            message_template="Case temperature critical: {value:.1f}°C",
            condition=lambda v, mt=max_case_temp: v > mt
        ))
        
        logger.info(f"{len(self.rules)} regras de alarme configuradas")
        
    async def initialize(self):
        """
        Inicializa o sistema de alarmes no servidor OPC UA.
        
        Configura o tipo de evento para alarmes.
        """
        # Obter tipo de evento base
        base_event = self.server.nodes.base_event_type
        
        # Criar tipo de evento personalizado para alarmes do motor
        self._event_type = await self.server.nodes.objects.add_object_type(
            2,  # namespace index
            "Motor50CVAlarmType"
        )
        
        logger.info("Sistema de alarmes inicializado")
        
    def set_alarm_callback(self, callback: callable):
        """
        Define callback para notificação de alarmes.
        
        Args:
            callback: Função assíncrona chamada quando alarme é gerado
        """
        self._on_alarm_callback = callback
        
    async def check_values(self, values: Dict[str, float]) -> List[AlarmEvent]:
        """
        Verifica valores e gera alarmes se necessário.
        
        Args:
            values: Dicionário com nome da variável e valor atual
            
        Returns:
            Lista de alarmes gerados
        """
        new_alarms = []
        
        for rule in self.rules:
            if rule.variable_name not in values:
                continue
                
            value = values[rule.variable_name]
            
            # Verificar se condição de alarme é atingida
            if rule.evaluate(value):
                # Verificar se já existe alarme ativo para esta regra
                if rule.name not in self.active_alarms:
                    # Criar novo alarme
                    alarm = AlarmEvent(
                        timestamp=datetime.utcnow(),
                        category=rule.category,
                        severity=rule.severity,
                        message=rule.get_message(value),
                        source_name=rule.variable_name,
                        value=value
                    )
                    
                    self.active_alarms[rule.name] = alarm
                    self.alarm_history.append(alarm)
                    new_alarms.append(alarm)
                    
                    logger.warning(f"ALARME: {alarm.message} (Severidade: {alarm.severity.name})")
                    
                    # Chamar callback se definido
                    if self._on_alarm_callback:
                        await self._on_alarm_callback(alarm)
            else:
                # Condição não mais ativa - remover alarme ativo
                if rule.name in self.active_alarms:
                    logger.info(f"Alarme '{rule.name}' normalizado")
                    del self.active_alarms[rule.name]
                    
        return new_alarms
        
    async def generate_event(self, alarm: AlarmEvent):
        """
        Gera um evento OPC UA para o alarme.
        
        Args:
            alarm: Evento de alarme a ser publicado
        """
        try:
            # Criar evento
            event = await self.server.get_event_generator(
                self.server.nodes.base_event_type,
                self.nodes.get("Motor50CV")
            )
            
            event.event.Severity = alarm.severity.value
            event.event.Message = ua.LocalizedText(alarm.message)
            event.event.SourceName = alarm.source_name
            event.event.Time = alarm.timestamp
            
            await event.trigger()
            
            logger.debug(f"Evento OPC UA gerado para alarme: {alarm.message}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar evento OPC UA: {e}")
            
    def get_active_alarms(self) -> List[Dict]:
        """
        Retorna lista de alarmes ativos.
        
        Returns:
            Lista de dicionários com dados dos alarmes ativos
        """
        return [alarm.to_dict() for alarm in self.active_alarms.values()]
        
    def get_alarm_history(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        severity: Optional[Severity] = None
    ) -> List[Dict]:
        """
        Retorna histórico de alarmes com filtros opcionais.
        
        Args:
            limit: Número máximo de registros
            category: Filtrar por categoria
            severity: Filtrar por severidade mínima
            
        Returns:
            Lista de dicionários com dados dos alarmes
        """
        history = self.alarm_history.copy()
        
        # Aplicar filtros
        if category:
            history = [a for a in history if a.category == category]
            
        if severity:
            history = [a for a in history if a.severity.value >= severity.value]
            
        # Ordenar por timestamp decrescente e limitar
        history.sort(key=lambda a: a.timestamp, reverse=True)
        
        return [alarm.to_dict() for alarm in history[:limit]]
        
    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """
        Reconhece um alarme ativo.
        
        Args:
            alarm_id: ID do alarme a reconhecer
            
        Returns:
            True se reconhecido com sucesso
        """
        for name, alarm in self.active_alarms.items():
            if alarm.id == alarm_id:
                alarm.acknowledged = True
                logger.info(f"Alarme reconhecido: {alarm_id}")
                return True
                
        return False
        
    def clear_history(self):
        """Limpa o histórico de alarmes."""
        self.alarm_history.clear()
        logger.info("Histórico de alarmes limpo")
