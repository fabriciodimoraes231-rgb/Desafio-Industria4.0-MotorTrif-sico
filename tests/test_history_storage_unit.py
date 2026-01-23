"""
Testes unitários para history_storage.py.

Usa import direto pois conftest.py adiciona opcua_server ao sys.path.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

# Import direto - conftest.py adiciona opcua_server ao sys.path
from history_storage import HistoryStorageSQLite


class TestHistoryStorageSQLiteInit:
    """Testes de inicialização do HistoryStorageSQLite."""
    
    def test_storage_init(self):
        """Testa inicialização do storage."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        assert storage.db_path == "/path/to/db.sqlite"
        assert storage._db is None
        assert storage._datachanges_period == {}
        assert storage._events_period == {}
    
    def test_storage_init_with_max_size(self):
        """Testa inicialização com tamanho máximo de resposta."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite", max_history_data_response_size=5000)
        
        assert storage.db_path == "/path/to/db.sqlite"
        assert storage.max_history_data_response_size == 5000
    
    def test_storage_init_default_path(self):
        """Testa inicialização com caminho padrão."""
        storage = HistoryStorageSQLite()
        
        assert storage.db_path == "history.db"


class TestHistoryStorageSQLiteConnection:
    """Testes de conexão do HistoryStorageSQLite."""
    
    @pytest.mark.asyncio
    async def test_init_creates_tables(self):
        """Testa que init cria as tabelas necessárias."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        
        with patch('history_storage.aiosqlite') as mock_sqlite:
            mock_sqlite.connect = AsyncMock(return_value=mock_db)
            
            with patch('history_storage.Path'):
                await storage.init()
        
        # Verifica se as tabelas foram criadas
        assert mock_db.execute.call_count >= 3  # CREATE TABLE + INDEX
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_closes_connection(self):
        """Testa que stop fecha a conexão."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        await storage.stop()
        
        mock_db.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_without_connection(self):
        """Testa stop sem conexão ativa."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Sem conexão
        storage._db = None
        
        # Não deve lançar exceção
        await storage.stop()


class TestHistoryStorageSQLiteTableName:
    """Testes de geração de nomes de tabela."""
    
    def test_get_table_name(self):
        """Testa geração de nome de tabela."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        table_name = storage._get_table_name(node_id)
        
        assert "history_" in table_name
        assert "VoltageA" in table_name
        assert "2" in table_name
    
    def test_get_table_name_replaces_dashes(self):
        """Testa que hifens são substituídos por underscores."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        node_id = ua.NodeId(Identifier="Voltage-A-Phase", NamespaceIndex=2)
        table_name = storage._get_table_name(node_id)
        
        assert "-" not in table_name


class TestHistoryStorageSQLiteVariableMapping:
    """Testes de mapeamento de variáveis."""
    
    @pytest.mark.asyncio
    async def test_register_variable_mapping(self):
        """Testa registro de mapeamento de variável."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        await storage.register_variable_mapping("VoltageA", node_id)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_register_variable_mapping_error(self):
        """Testa registro com erro."""
        from asyncua import ua
        import aiosqlite
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("Test error"))
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        # Não deve lançar exceção
        await storage.register_variable_mapping("VoltageA", node_id)


class TestHistoryStorageSQLiteNewHistorizedNode:
    """Testes para new_historized_node."""
    
    @pytest.mark.asyncio
    async def test_new_historized_node_creates_table(self):
        """Testa criação de tabela para nó historizado."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        await storage.new_historized_node(node_id, timedelta(days=7), count=10000)
        
        # Verifica que criou tabela e índice
        assert mock_db.execute.call_count >= 2
        mock_db.commit.assert_called()
        
        # Verifica que registrou o período
        assert node_id in storage._datachanges_period
    
    @pytest.mark.asyncio
    async def test_new_historized_node_stores_period(self):
        """Testa armazenamento do período."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        period = timedelta(days=7)
        count = 10000
        
        await storage.new_historized_node(node_id, period, count=count)
        
        assert storage._datachanges_period[node_id] == (period, count)


class TestHistoryStorageSQLiteSaveNodeValue:
    """Testes para save_node_value."""
    
    @pytest.mark.asyncio
    async def test_save_node_value(self):
        """Testa salvamento de valor no histórico."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        # Criar DataValue manualmente
        datavalue = MagicMock()
        datavalue.Value = ua.Variant(220.0, ua.VariantType.Double)
        datavalue.SourceTimestamp = datetime.now(timezone.utc)
        datavalue.ServerTimestamp = datetime.now(timezone.utc)
        datavalue.StatusCode = ua.StatusCode(0)
        
        await storage.save_node_value(node_id, datavalue)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


class TestHistoryStorageSQLiteAlarmHistory:
    """Testes para histórico de alarmes."""
    
    @pytest.mark.asyncio
    async def test_save_alarm(self):
        """Testa salvamento de alarme."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        # API correta: save_alarm(alarm_data: Dict)
        alarm_data = {
            "alarm_id": "test-alarm-1",
            "timestamp": datetime.now(timezone.utc),
            "category": "Electrical",
            "severity": 700,
            "message": "High voltage detected",
            "source_name": "VoltageA",
            "value": 250.0
        }
        
        await storage.save_alarm(alarm_data)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_alarms_empty(self):
        """Testa busca de alarmes vazia."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        
        result = await storage.get_alarms(limit=100)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_get_alarms_with_data(self):
        """Testa busca de alarmes com dados."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        now = datetime.now(timezone.utc)
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("alarm-1", now.isoformat(), "Electrical", 700, "High voltage", "VoltageA", 250.0, False),
            ("alarm-2", now.isoformat(), "Temperature", 500, "High temp", "Temperature", 80.0, False),
        ])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        
        result = await storage.get_alarms(limit=100)
        
        assert result is not None
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_active_alarm_count(self):
        """Testa contagem de alarmes ativos."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(5,))
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        
        # API correta: get_active_alarm_count (singular)
        result = await storage.get_active_alarm_count()
        
        assert result == 5


class TestHistoryStorageSQLiteReadHistory:
    """Testes para leitura de histórico."""
    
    @pytest.mark.asyncio
    async def test_read_node_history(self):
        """Testa leitura de histórico de nó."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        
        result = await storage.read_node_history(node_id, start, end, 100)
        
        assert result is not None


class TestHistoryStorageSQLiteGetHistoryForApi:
    """Testes para get_history_for_api."""
    
    @pytest.mark.asyncio
    async def test_get_history_for_api(self):
        """Testa obtenção de histórico para API."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("2024-01-01T12:00:00+00:00", 220.0),
            ("2024-01-01T12:01:00+00:00", 221.0)
        ])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        
        # Mock do mapeamento
        from asyncua import ua
        storage._variable_mapping = {"VoltageA": ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)}
        
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        
        result = await storage.get_history_for_api("VoltageA", start, end, 100)
        
        assert result is not None


class TestHistoryStorageSQLiteStatisticsForApi:
    """Testes para get_statistics_for_api."""
    
    @pytest.mark.asyncio
    async def test_get_statistics_for_api(self):
        """Testa obtenção de estatísticas para API."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Mock cursor com estatísticas
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(
            100.0,  # min
            200.0,  # max
            150.0,  # avg
            100     # count
        ))
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        storage._db = mock_db
        storage._variable_mapping = {"VoltageA": ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)}
        
        result = await storage.get_statistics_for_api("VoltageA", 24)
        
        assert result is not None


class TestHistoryStorageSQLiteGetAllHistorizedVariables:
    """Testes para get_all_historized_variables."""
    
    @pytest.mark.asyncio
    async def test_get_all_historized_variables_success(self):
        """Testa listagem de variáveis historizadas."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("history_2_VoltageA",),
            ("history_2_CurrentA",),
            ("history_2_Temperature",)
        ])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        storage._db = mock_db
        
        result = await storage.get_all_historized_variables()
        
        assert "VoltageA" in result
        assert "CurrentA" in result
        assert "Temperature" in result
    
    @pytest.mark.asyncio
    async def test_get_all_historized_variables_error(self):
        """Testa tratamento de erro."""
        import aiosqlite
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("DB Error"))
        storage._db = mock_db
        
        result = await storage.get_all_historized_variables()
        
        assert result == []


class TestHistoryStorageSQLiteGetBounds:
    """Testes para o método estático _get_bounds."""
    
    def test_get_bounds_with_start_and_end(self):
        """Testa cálculo de limites com início e fim."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        
        start_time, end_time, order, limit = HistoryStorageSQLite._get_bounds(start, end, 100)
        
        # Retorna strings formatadas
        assert start_time is not None
        assert end_time is not None
        assert limit == 100
    
    def test_get_bounds_no_limit(self):
        """Testa cálculo de limites sem limite."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        start_time, end_time, order, limit = HistoryStorageSQLite._get_bounds(start, end, 0)
        
        # 0 vira -1 internamente
        assert limit == -1  # Sem limite
    
    def test_get_bounds_none_start(self):
        """Testa cálculo de limites sem início."""
        end = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        
        start_time, end_time, order, limit = HistoryStorageSQLite._get_bounds(None, end, 100)
        
        # Deve usar época do Windows como início
        assert start_time is not None


class TestHistoryStorageSQLiteReadHistoryDataFromTable:
    """Testes para leitura de dados históricos."""
    
    @pytest.mark.asyncio
    async def test_read_node_history_success(self):
        """Testa leitura de histórico de nó."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        result, cont = await storage.read_node_history(
            node_id,
            datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            100
        )
        
        assert result == []
        assert cont is None
    
    @pytest.mark.asyncio
    async def test_read_node_history_error(self):
        """Testa tratamento de erro."""
        import aiosqlite
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("DB Error"))
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        result, cont = await storage.read_node_history(
            node_id,
            datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            100
        )
        
        assert result == []


class TestHistoryStorageSQLiteNewHistorizedNode:
    """Testes para new_historized_node."""
    
    @pytest.mark.asyncio
    async def test_new_historized_node(self):
        """Testa criação de tabela para novo nó historizado."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="NewVariable", NamespaceIndex=2)
        period = timedelta(days=7)
        
        await storage.new_historized_node(node_id, period)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


class TestHistoryStorageSQLiteSaveNodeValue:
    """Testes para save_node_value."""
    
    @pytest.mark.asyncio
    async def test_save_node_value_success(self):
        """Testa salvamento de valor."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        datavalue = ua.DataValue(
            Value=ua.Variant(220.0, ua.VariantType.Double),
            SourceTimestamp=datetime.now(timezone.utc),
            ServerTimestamp=datetime.now(timezone.utc)
        )
        
        await storage.save_node_value(node_id, datavalue)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_save_node_value_with_period_cleanup(self):
        """Testa salvamento com limpeza por período."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        # Configurar período de limpeza
        storage._datachanges_period[node_id] = (timedelta(hours=24), 0)
        
        datavalue = ua.DataValue(
            Value=ua.Variant(220.0, ua.VariantType.Double),
            SourceTimestamp=datetime.now(timezone.utc),
            ServerTimestamp=datetime.now(timezone.utc)
        )
        
        await storage.save_node_value(node_id, datavalue)
        
        # Deve ter chamado INSERT e DELETE
        assert mock_db.execute.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_save_node_value_with_count_limit(self):
        """Testa salvamento com limite de contagem."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        # Configurar limite de contagem
        storage._datachanges_period[node_id] = (None, 100)
        
        datavalue = ua.DataValue(
            Value=ua.Variant(220.0, ua.VariantType.Double),
            SourceTimestamp=datetime.now(timezone.utc),
            ServerTimestamp=datetime.now(timezone.utc)
        )
        
        await storage.save_node_value(node_id, datavalue)
        
        assert mock_db.execute.call_count >= 2


class TestHistoryStorageSQLiteGetHistoryForApiExtended:
    """Testes estendidos para get_history_for_api."""
    
    @pytest.mark.asyncio
    async def test_get_history_for_api_without_mapping(self):
        """Testa obtenção de histórico sem mapeamento."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Mock para mapeamento não encontrado
        mock_mapping_cursor = AsyncMock()
        mock_mapping_cursor.fetchone = AsyncMock(return_value=None)
        
        # Mock para lista de tabelas
        mock_tables_cursor = AsyncMock()
        mock_tables_cursor.fetchall = AsyncMock(return_value=[
            ("history_2_VoltageA",)
        ])
        
        # Mock para dados
        mock_data_cursor = AsyncMock()
        mock_data_cursor.fetchall = AsyncMock(return_value=[])
        
        call_count = 0
        async def mock_execute(query, *args):
            nonlocal call_count
            call_count += 1
            if "variable_node_mapping" in query:
                return mock_mapping_cursor
            elif "sqlite_master" in query:
                return mock_tables_cursor
            else:
                return mock_data_cursor
        
        mock_db = AsyncMock()
        mock_db.execute = mock_execute
        storage._db = mock_db
        
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        
        result = await storage.get_history_for_api("VoltageA", start, end, 100)
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_history_for_api_error(self):
        """Testa tratamento de erro."""
        import aiosqlite
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("DB Error"))
        storage._db = mock_db
        
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        
        result = await storage.get_history_for_api("VoltageA", start, end, 100)
        
        assert result == []


class TestHistoryStorageSQLiteStatisticsForApiExtended:
    """Testes estendidos para get_statistics_for_api."""
    
    @pytest.mark.asyncio
    async def test_get_statistics_for_api_no_data(self):
        """Testa estatísticas sem dados."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_tables_cursor = AsyncMock()
        mock_tables_cursor.fetchall = AsyncMock(return_value=[
            ("history_2_VoltageA",)
        ])
        
        mock_data_cursor = AsyncMock()
        mock_data_cursor.fetchall = AsyncMock(return_value=[])
        
        async def mock_execute(query, *args):
            if "sqlite_master" in query:
                return mock_tables_cursor
            return mock_data_cursor
        
        mock_db = AsyncMock()
        mock_db.execute = mock_execute
        storage._db = mock_db
        
        result = await storage.get_statistics_for_api("VoltageA", 24)
        
        assert result is not None
        assert "variable_name" in result
    
    @pytest.mark.asyncio
    async def test_get_statistics_for_api_error(self):
        """Testa tratamento de erro."""
        import aiosqlite
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("DB Error"))
        storage._db = mock_db
        
        result = await storage.get_statistics_for_api("VoltageA", 24)
        
        assert result is not None


class TestHistoryStorageSQLiteEventMethods:
    """Testes para métodos de eventos."""
    
    @pytest.mark.asyncio
    async def test_new_historized_event(self):
        """Testa configuração de eventos para historização."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        source_id = ua.NodeId(Identifier="EventSource", NamespaceIndex=2)
        period = timedelta(days=1)
        
        await storage.new_historized_event(source_id, [], period, count=100)
        
        assert source_id in storage._events_period
        assert storage._events_period[source_id] == (period, 100)
    
    @pytest.mark.asyncio
    async def test_save_event(self):
        """Testa salvamento de evento (não implementado)."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Não deve lançar exceção
        await storage.save_event({})
    
    @pytest.mark.asyncio
    async def test_read_event_history(self):
        """Testa leitura de histórico de eventos (não implementado)."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        source_id = ua.NodeId(Identifier="EventSource", NamespaceIndex=2)
        
        results, cont = await storage.read_event_history(
            source_id, None, None, None, None
        )
        
        assert results == []
        assert cont is None


class TestHistoryStorageSQLiteAlarmSave:
    """Testes para salvamento de alarmes."""
    
    @pytest.mark.asyncio
    async def test_save_alarm(self):
        """Testa salvamento de alarme no banco."""
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        mock_db = AsyncMock()
        storage._db = mock_db
        
        alarm = {
            "alarm_type": "high_temperature",
            "variable": "CaseTemperature",
            "message": "Temperature too high",
            "severity": 500,
            "value": 85.5,
            "acknowledged": False
        }
        
        await storage.save_alarm(alarm)
        
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


class TestHistoryStorageSQLiteRegisterVariable:
    """Testes para registro de variáveis."""
    
    @pytest.mark.asyncio
    async def test_register_variable_mapping(self):
        """Testa registro de mapeamento variável -> node_id."""
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Mock do banco de dados
        mock_db = AsyncMock()
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        await storage.register_variable_mapping("VoltageA", node_id)
        
        # Verifica que executou INSERT e commit
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_register_variable_mapping_error(self):
        """Testa tratamento de erro no registro."""
        import aiosqlite
        from asyncua import ua
        
        storage = HistoryStorageSQLite("/path/to/db.sqlite")
        
        # Mock do banco de dados com erro
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=aiosqlite.Error("DB Error"))
        storage._db = mock_db
        
        node_id = ua.NodeId(Identifier="VoltageA", NamespaceIndex=2)
        
        # Não deve propagar exceção
        await storage.register_variable_mapping("VoltageA", node_id)
