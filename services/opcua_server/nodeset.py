"""
Construtor do Nodeset OPC UA.

Este módulo implementa a criação da estrutura de nós do servidor OPC UA
seguindo a hierarquia especificada para o motor 50CV.
"""

import logging
from typing import Dict, Any, Optional
from asyncua import ua, Server
from asyncua.common.node import Node

logger = logging.getLogger(__name__)


class NodesetBuilder:
    """
    Construtor da árvore de nós OPC UA para o motor 50CV.
    
    Cria a estrutura hierárquica de variáveis conforme especificação:
    Motor50CV/
    ├── Electrical/
    │   ├── VoltageA, VoltageB, VoltageC
    │   ├── CurrentA, CurrentB, CurrentC
    │   ├── PowerActive, PowerReactive, PowerApparent
    │   ├── EnergyActive, EnergyReactive, EnergyApparent
    │   ├── PowerFactor, Frequency
    ├── Environment/
    │   ├── Temperature, Humidity, CaseTemperature
    └── Vibration/
        ├── Axial, Radial
        
    Attributes:
        server: Instância do servidor OPC UA
        namespace_idx: Índice do namespace
        nodes: Dicionário com referências aos nós criados
    """
    
    def __init__(self, server: Server, namespace_idx: int):
        """
        Inicializa o construtor de nodeset.
        
        Args:
            server: Instância do servidor OPC UA
            namespace_idx: Índice do namespace para os nós
        """
        self.server = server
        self.namespace_idx = namespace_idx
        self.nodes: Dict[str, Node] = {}
        self._root_node: Optional[Node] = None
        
    async def build(self) -> Dict[str, Node]:
        """
        Constrói a estrutura completa de nós.
        
        Returns:
            Dicionário com todos os nós criados, indexados por nome
        """
        logger.info("Construindo estrutura de nós OPC UA...")
        
        # Obter nó raiz Objects
        objects = self.server.nodes.objects
        
        # Criar nó raiz Motor50CV
        self._root_node = await objects.add_folder(
            self.namespace_idx,
            "Motor50CV"
        )
        self.nodes["Motor50CV"] = self._root_node
        
        # Criar subpastas e variáveis
        await self._build_electrical()
        await self._build_environment()
        await self._build_vibration()
        
        logger.info(f"Estrutura de nós criada: {len(self.nodes)} nós")
        return self.nodes
        
    async def _build_electrical(self):
        """
        Constrói a pasta Electrical com suas variáveis.
        
        Variáveis:
        - VoltageA, VoltageB, VoltageC (V)
        - CurrentA, CurrentB, CurrentC (A)
        - PowerActive (W), PowerReactive (VAr), PowerApparent (VA)
        - EnergyActive (Wh), EnergyReactive (VArh), EnergyApparent (VAh)
        - PowerFactor (0-1), Frequency (Hz)
        """
        electrical = await self._root_node.add_folder(
            self.namespace_idx,
            "Electrical"
        )
        self.nodes["Electrical"] = electrical
        
        # Tensões (V)
        await self._add_variable(electrical, "VoltageA", 0.0, "V", historize=True)
        await self._add_variable(electrical, "VoltageB", 0.0, "V", historize=True)
        await self._add_variable(electrical, "VoltageC", 0.0, "V", historize=True)
        
        # Correntes (A)
        await self._add_variable(electrical, "CurrentA", 0.0, "A", historize=True)
        await self._add_variable(electrical, "CurrentB", 0.0, "A", historize=True)
        await self._add_variable(electrical, "CurrentC", 0.0, "A", historize=True)
        
        # Potências
        await self._add_variable(electrical, "PowerActive", 0.0, "W", historize=True)
        await self._add_variable(electrical, "PowerReactive", 0.0, "VAr", historize=True)
        await self._add_variable(electrical, "PowerApparent", 0.0, "VA", historize=True)
        
        # Energias
        await self._add_variable(electrical, "EnergyActive", 0.0, "Wh", historize=True)
        await self._add_variable(electrical, "EnergyReactive", 0.0, "VArh", historize=True)
        await self._add_variable(electrical, "EnergyApparent", 0.0, "VAh", historize=True)
        
        # Outros
        await self._add_variable(electrical, "PowerFactor", 0.0, "", historize=True)
        await self._add_variable(electrical, "Frequency", 0.0, "Hz", historize=True)
        
        logger.info("Pasta Electrical criada com 14 variáveis")
        
    async def _build_environment(self):
        """
        Constrói a pasta Environment com suas variáveis.
        
        Variáveis:
        - Temperature (°C)
        - Humidity (%)
        - CaseTemperature (°C)
        """
        environment = await self._root_node.add_folder(
            self.namespace_idx,
            "Environment"
        )
        self.nodes["Environment"] = environment
        
        await self._add_variable(environment, "Temperature", 0.0, "°C", historize=False)
        await self._add_variable(environment, "Humidity", 0.0, "%", historize=False)
        await self._add_variable(environment, "CaseTemperature", 0.0, "°C", historize=True)
        
        logger.info("Pasta Environment criada com 3 variáveis")
        
    async def _build_vibration(self):
        """
        Constrói a pasta Vibration com suas variáveis.
        
        Variáveis:
        - Axial (mm/s)
        - Radial (mm/s)
        """
        vibration = await self._root_node.add_folder(
            self.namespace_idx,
            "Vibration"
        )
        self.nodes["Vibration"] = vibration
        
        await self._add_variable(vibration, "Axial", 0.0, "mm/s", historize=False)
        await self._add_variable(vibration, "Radial", 0.0, "mm/s", historize=False)
        
        logger.info("Pasta Vibration criada com 2 variáveis")
        
    async def _add_variable(
        self,
        parent: Node,
        name: str,
        initial_value: float,
        unit: str,
        historize: bool = False
    ) -> Node:
        """
        Adiciona uma variável ao nodeset.
        
        Args:
            parent: Nó pai onde adicionar a variável
            name: Nome da variável
            initial_value: Valor inicial
            unit: Unidade de engenharia
            historize: Se True, habilita historização
            
        Returns:
            Node: Referência ao nó da variável criada
        """
        var = await parent.add_variable(
            self.namespace_idx,
            name,
            initial_value,
            varianttype=ua.VariantType.Double
        )
        
        # Tornar variável gravável (para atualizações do RabbitMQ)
        await var.set_writable()
        
        # Configurar historização se necessário
        if historize:
            await var.set_attr_bit(ua.AttributeIds.AccessLevel, ua.AccessLevel.HistoryRead)
            
        # Armazenar referência
        self.nodes[name] = var
        
        logger.debug(f"Variável '{name}' criada (historize={historize})")
        return var
        
    def get_node(self, name: str) -> Optional[Node]:
        """
        Obtém referência a um nó pelo nome.
        
        Args:
            name: Nome do nó
            
        Returns:
            Node ou None se não encontrado
        """
        return self.nodes.get(name)
        
    def get_all_nodes(self) -> Dict[str, Node]:
        """
        Retorna todos os nós criados.
        
        Returns:
            Dicionário com todos os nós
        """
        return self.nodes.copy()
        
    def get_variable_nodes(self) -> Dict[str, Node]:
        """
        Retorna apenas os nós de variáveis (excluindo pastas).
        
        Returns:
            Dicionário com nós de variáveis
        """
        folder_names = ["Motor50CV", "Electrical", "Environment", "Vibration"]
        return {k: v for k, v in self.nodes.items() if k not in folder_names}
