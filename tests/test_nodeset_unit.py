"""
Testes unitários para nodeset.py.

Testa a classe NodesetBuilder.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

# Import direto - conftest.py adiciona opcua_server ao sys.path
from nodeset import NodesetBuilder


class TestNodesetBuilderInit:
    """Testes de inicialização."""
    
    def test_init(self):
        """Testa inicialização do builder."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        assert builder.server == mock_server
        assert builder.namespace_idx == 2
        assert builder.nodes == {}
        assert builder._root_node is None


class TestNodesetBuilderGetNode:
    """Testes para get_node."""
    
    def test_get_node_exists(self):
        """Testa obtenção de nó existente."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        mock_node = MagicMock()
        builder.nodes["VoltageA"] = mock_node
        
        result = builder.get_node("VoltageA")
        
        assert result == mock_node
    
    def test_get_node_not_exists(self):
        """Testa obtenção de nó inexistente."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        result = builder.get_node("NonExistent")
        
        assert result is None


class TestNodesetBuilderGetAllNodes:
    """Testes para get_all_nodes."""
    
    def test_get_all_nodes_empty(self):
        """Testa obtenção de todos os nós quando vazio."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        result = builder.get_all_nodes()
        
        assert result == {}
    
    def test_get_all_nodes_with_nodes(self):
        """Testa obtenção de todos os nós."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        mock_node1 = MagicMock()
        mock_node2 = MagicMock()
        builder.nodes["VoltageA"] = mock_node1
        builder.nodes["CurrentA"] = mock_node2
        
        result = builder.get_all_nodes()
        
        assert len(result) == 2
        assert "VoltageA" in result
        assert "CurrentA" in result
    
    def test_get_all_nodes_returns_copy(self):
        """Testa que get_all_nodes retorna cópia."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        mock_node = MagicMock()
        builder.nodes["VoltageA"] = mock_node
        
        result = builder.get_all_nodes()
        result["NewNode"] = MagicMock()
        
        # Original não deve ser afetado
        assert "NewNode" not in builder.nodes


class TestNodesetBuilderGetVariableNodes:
    """Testes para get_variable_nodes."""
    
    def test_get_variable_nodes_excludes_folders(self):
        """Testa que exclui nós de pastas."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        # Adicionar pastas e variáveis
        builder.nodes["Motor50CV"] = MagicMock()
        builder.nodes["Electrical"] = MagicMock()
        builder.nodes["Environment"] = MagicMock()
        builder.nodes["Vibration"] = MagicMock()
        builder.nodes["VoltageA"] = MagicMock()
        builder.nodes["CurrentA"] = MagicMock()
        builder.nodes["Temperature"] = MagicMock()
        
        result = builder.get_variable_nodes()
        
        # Deve retornar apenas variáveis
        assert len(result) == 3
        assert "VoltageA" in result
        assert "CurrentA" in result
        assert "Temperature" in result
        assert "Motor50CV" not in result
        assert "Electrical" not in result
    
    def test_get_variable_nodes_empty(self):
        """Testa get_variable_nodes com nenhuma variável."""
        mock_server = MagicMock()
        builder = NodesetBuilder(mock_server, 2)
        
        # Adicionar apenas pastas
        builder.nodes["Motor50CV"] = MagicMock()
        builder.nodes["Electrical"] = MagicMock()
        
        result = builder.get_variable_nodes()
        
        assert result == {}


class TestNodesetBuilderBuild:
    """Testes para o método build."""
    
    @pytest.mark.asyncio
    async def test_build_creates_structure(self):
        """Testa que build cria estrutura de nós."""
        mock_server = AsyncMock()
        mock_objects = AsyncMock()
        mock_root_node = AsyncMock()
        
        mock_objects.add_folder = AsyncMock(return_value=mock_root_node)
        mock_root_node.add_folder = AsyncMock(return_value=AsyncMock())
        mock_root_node.add_variable = AsyncMock(return_value=AsyncMock())
        
        mock_server.nodes = MagicMock()
        mock_server.nodes.objects = mock_objects
        
        builder = NodesetBuilder(mock_server, 2)
        
        # Mock os métodos internos
        builder._build_electrical = AsyncMock()
        builder._build_environment = AsyncMock()
        builder._build_vibration = AsyncMock()
        
        result = await builder.build()
        
        assert "Motor50CV" in result
        builder._build_electrical.assert_called_once()
        builder._build_environment.assert_called_once()
        builder._build_vibration.assert_called_once()
