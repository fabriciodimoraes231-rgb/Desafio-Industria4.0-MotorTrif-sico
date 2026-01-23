"""
Gerenciador de Alarmes e Eventos OPC UA.

Este modulo implementa o sistema de alarmes do servidor OPC UA,
responsavel por:
- Definir regras de alarme baseadas em limites de variaveis
- Avaliar condicoes de alarme a cada nova leitura
- Gerar eventos OPC UA quando alarmes sao ativados
- Manter historico de alarmes

Classes:
    Severity: Enum com niveis de severidade
    AlarmEvent: Dataclass representando um evento de alarme
    AlarmRule: Regra de alarme para uma variavel
    AlarmManager: Gerenciador principal de alarmes

Constants:
    Limiares de tensao, corrente e temperatura conforme especificacao
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import IntEnum
from asyncua import ua, Server
from asyncua.common.node import Node

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class Severity(IntEnum):
    """
    Niveis de severidade para alarmes OPC UA.
    
    Segue a escala OPC UA de 0-1000, onde valores maiores
    indicam maior severidade.
    
    Attributes:
        INFORMATIVE: Informativo (100)
        LOW: Baixa severidade (250)
        MEDIUM: Media severidade (500)
        HIGH: Alta severidade (700)
        CRITICAL: Critico (900)
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
    
    Armazena todas as informacoes de um alarme gerado pelo sistema.
    
    Attributes:
        timestamp: Data/hora da ocorrencia
        category: Categoria (Electrical, Environment, Vibration)
        severity: Nivel de severidade
        message: Mensagem descritiva
        source_name: Nome da variavel que gerou o alarme
        value: Valor que disparou o alarme
        acknowledged: Se foi reconhecido pelo operador
        id: Identificador unico
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
        """Gera ID unico se nao fornecido."""
        if self.id is None:
            self.id = f"{self.timestamp.isoformat()}_{self.source_name}"
            
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte o alarme para dicionario.
        
        Returns:
            Dicionario com todos os campos do alarme
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
    Regra de alarme para monitoramento de variaveis.
    
    Define as condicoes e parametros para geracao de um tipo
    especifico de alarme.
    
    Attributes:
        name: Nome identificador da regra
        variable_name: Nome da variavel monitorada
        category: Categoria do alarme
        severity: Severidade quando ativado
        message_template: Template da mensagem (usa {value})
        condition: Funcao que avalia se o alarme deve ser ativado
        
    Example:
        >>> rule = AlarmRule(
        ...     name="Overvoltage_A",
        ...     variable_name="VoltageA",
        ...     category="Electrical",
        ...     severity=Severity.HIGH,
        ...     message_template="Overvoltage on phase A: {value:.1f}V",
        ...     condition=lambda v: v > 242
        ... )
    """
    name: str
    variable_name: str
    category: str
    severity: Severity
    message_template: str
    condition: callable
    
    def evaluate(self, value: float) -> bool:
        """
        Avalia se a condicao de alarme foi atingida.
        
        Args:
            value: Valor atual da variavel
            
        Returns:
            True se a condicao de alarme foi atingida
        """
        return self.condition(value)
        
    def get_message(self, value: float) -> str:
        """
        Gera mensagem do alarme com o valor atual.
        
        Args:
            value: Valor que disparou o alarme
            
        Returns:
            Mensagem formatada
        """
        return self.message_template.format(value=value)


class AlarmManager:
    """
    Gerenciador de alarmes e eventos OPC UA.
    
    Responsavel por avaliar regras de alarme, gerar eventos e
    manter o historico de alarmes do sistema.
    
    Attributes:
        server: Instancia do servidor OPC UA
        nodes: Dicionario de nos OPC UA
        settings: Configuracoes do sistema
        rules: Lista de regras de alarme
        active_alarms: Alarmes atualmente ativos
        alarm_history: Historico de alarmes
        
    Example:
        >>> manager = AlarmManager(server, nodes, settings)
        >>> await manager.initialize()
        >>> manager.set_alarm_callback(on_alarm_handler)
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
            server: Instancia do servidor OPC UA
            nodes: Dicionario de nos OPC UA
            settings: Configuracoes (usa padrao se nao fornecido)
        """
        self.server = server
        self.nodes = nodes
        self.settings = settings or get_settings()
        self.rules: List[AlarmRule] = []
        self.active_alarms: Dict[str, AlarmEvent] = {}
        self.alarm_history: List[AlarmEvent] = []
        self._event_type: Optional[Node] = None
        self._on_alarm_callback: Optional[callable] = None
        self._create_rules()
        
    def _create_rules(self):
        """
        Cria as regras de alarme conforme especificacao.
        
        Define regras para:
        - Sobretensao e subtensao nas 3 fases
        - Sobrecorrente nas 3 fases
        - Temperatura critica da carcaca
        """
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
        """Inicializa o sistema de alarmes no servidor OPC UA."""
        base_event = self.server.nodes.base_event_type
        
        self._event_type = await self.server.nodes.objects.add_object_type(
            2,
            "Motor50CVAlarmType"
        )
        logger.info("Sistema de alarmes inicializado")
        
    def set_alarm_callback(self, callback: callable):
        """Define callback para notificação de alarmes."""
        self._on_alarm_callback = callback
        
    async def check_values(self, values: Dict[str, float]) -> List[AlarmEvent]:
        """Verifica valores e gera alarmes se necessário."""
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
                        timestamp=datetime.now(timezone.utc),
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
        """Gera um evento OPC UA para o alarme."""
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
        """Retorna lista de alarmes ativos."""
        return [alarm.to_dict() for alarm in self.active_alarms.values()]
        
    def get_alarm_history(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        severity: Optional[Severity] = None
    ) -> List[Dict]:
        """Retorna histórico de alarmes com filtros opcionais."""
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
        """Reconhece um alarme ativo."""
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
