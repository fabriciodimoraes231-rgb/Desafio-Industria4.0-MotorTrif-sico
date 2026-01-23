"""
Testes unitários para services/api_service/services.py.

Testa a classe DataService com todas as dependências mockadas.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

# Importar usando caminho completo do pacote
from services.api_service.services import DataService, get_data_service, close_data_service
import services.api_service.services as services_module


class TestDataServiceInit:
    """Testes de inicialização do DataService."""
    
    def test_data_service_init_with_settings(self):
        """Testa inicialização com settings fornecidas."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        service = DataService(mock_settings)
        
        assert service.settings == mock_settings
        assert service._db is None
        assert service._rabbitmq_conn is None
        assert service._latest_values == {}
        assert service._last_update is None
        assert service._consuming is False
    
    def test_data_service_init_default_settings(self):
        """Testa inicialização com settings padrão."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        with patch('services.api_service.services.get_settings', return_value=mock_settings):
            service = DataService()
            
            assert service.settings is not None


class TestDataServiceClose:
    """Testes do método close."""
    
    @pytest.mark.asyncio
    async def test_close_with_connections(self):
        """Testa close com conexões ativas."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        service = DataService(mock_settings)
        
        # Mock conexões
        mock_db = AsyncMock()
        mock_rabbitmq = AsyncMock()
        mock_rabbitmq.is_closed = False
        
        service._db = mock_db
        service._rabbitmq_conn = mock_rabbitmq
        service._consuming = True
        
        await service.close()
        
        assert service._consuming is False
        mock_db.close.assert_called_once()
        mock_rabbitmq.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_without_connections(self):
        """Testa close sem conexões."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.rabbitmq_host = "localhost"
        
        service = DataService(mock_settings)
        
        # Sem conexões ativas
        await service.close()
        
        assert service._consuming is False
    
    @pytest.mark.asyncio
    async def test_close_with_closed_rabbitmq(self):
        """Testa close com RabbitMQ já fechado."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        mock_db = AsyncMock()
        mock_rabbitmq = AsyncMock()
        mock_rabbitmq.is_closed = True  # Já fechado
        
        service._db = mock_db
        service._rabbitmq_conn = mock_rabbitmq
        
        await service.close()
        
        mock_db.close.assert_called_once()
        mock_rabbitmq.close.assert_not_called()


class TestDataServiceGetLatest:
    """Testes do método get_latest."""
    
    @pytest.mark.asyncio
    async def test_get_latest_from_cache(self):
        """Testa get_latest com valores em cache."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        # Configurar cache com o formato correto (dict com value)
        service._latest_values = {
            "VoltageA": {"value": 220.0},
            "VoltageB": {"value": 219.5},
            "VoltageC": {"value": 220.5},
            "CurrentA": {"value": 10.0},
            "CurrentB": {"value": 10.5},
            "CurrentC": {"value": 9.8},
            "PowerActive": {"value": 5000.0},
            "PowerReactive": {"value": 1000.0},
            "PowerApparent": {"value": 5100.0},
            "PowerFactor": {"value": 0.98},
            "Frequency": {"value": 60.0},
            "Temperature": {"value": 45.0},
            "Humidity": {"value": 55.0},
            "Axial": {"value": 0.5},
            "Radial": {"value": 0.3},
        }
        service._last_update = datetime.now(timezone.utc)
        
        result = await service.get_latest()
        
        assert result is not None
        assert "electrical" in result
        assert "environment" in result
        assert "vibration" in result
        assert "active_alarms" in result
        assert result["electrical"]["voltage"]["a"] == 220.0
        assert result["environment"]["temperature"] == 45.0
        assert result["vibration"]["axial"] == 0.5
    
    @pytest.mark.asyncio
    async def test_get_latest_from_database(self):
        """Testa get_latest buscando do banco."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        # Cache vazio - deve buscar do banco
        service._latest_values = {}
        service._last_update = None
        
        # Mock do banco
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("VoltageA", 220.0, datetime.now(timezone.utc).isoformat()),
        ])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        service._db = mock_db
        
        result = await service.get_latest()
        
        assert result is not None


class TestDataServiceGetHistory:
    """Testes do método get_history."""
    
    @pytest.mark.asyncio
    async def test_get_history_returns_dict(self):
        """Testa get_history retorna dicionário."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        # Mock do banco
        now = datetime.now(timezone.utc)
        
        # Cursor para mapeamento de variáveis
        mock_mapping_cursor = AsyncMock()
        mock_mapping_cursor.fetchone = AsyncMock(return_value=None)
        
        # Cursor para tabelas
        mock_tables_cursor = AsyncMock()
        mock_tables_cursor.fetchall = AsyncMock(return_value=[])
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[
            mock_mapping_cursor,
            mock_tables_cursor,
        ])
        
        service._db = mock_db
        
        result = await service.get_history(
            variable="voltage_a",
            start_time=now - timedelta(hours=1),
            end_time=now,
            limit=100
        )
        
        assert result is not None
        assert "variable" in result
        assert result["variable"] == "voltage_a"


class TestDataServiceGetStatistics:
    """Testes do método get_statistics."""
    
    @pytest.mark.asyncio
    async def test_get_statistics_returns_dict(self):
        """Testa get_statistics retorna dicionário."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        # Mock do banco
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(
            220.0,  # min
            225.0,  # max
            222.5,  # avg
            100,    # count
        ))
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        service._db = mock_db
        
        result = await service.get_statistics(
            variable="voltage_a",
            hours=24
        )
        
        assert result is not None
        assert "variable" in result
        assert result["variable"] == "voltage_a"


class TestDataServiceGetAlarms:
    """Testes do método get_alarms."""
    
    @pytest.mark.asyncio
    async def test_get_alarms_empty(self):
        """Testa get_alarms sem alarmes."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        # Mock do banco
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        
        service._db = mock_db
        
        result = await service.get_alarms()
        
        assert result is not None
        assert "alarms" in result
        assert result["alarms"] == []
    
    @pytest.mark.asyncio
    async def test_get_alarms_with_data(self):
        """Testa get_alarms com alarmes."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        now = datetime.now(timezone.utc)
        
        mock_alarms_cursor = AsyncMock()
        mock_alarms_cursor.fetchall = AsyncMock(return_value=[
            ("alarm-1", now.isoformat(), "Electrical", 700, "High voltage", "voltage_a", 250.0, False),
            ("alarm-2", now.isoformat(), "Temperature", 500, "High temp", "temperature", 80.0, False),
        ])
        
        mock_count_cursor = AsyncMock()
        mock_count_cursor.fetchone = AsyncMock(return_value=(2,))
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[
            mock_alarms_cursor,
            mock_count_cursor,
        ])
        
        service._db = mock_db
        
        result = await service.get_alarms()
        
        assert result is not None
        assert "alarms" in result
        assert len(result["alarms"]) == 2


class TestDataServiceAcknowledgeAlarm:
    """Testes do método acknowledge_alarm."""
    
    @pytest.mark.asyncio
    async def test_acknowledge_alarm_success(self):
        """Testa acknowledge_alarm com sucesso."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        
        service._db = mock_db
        
        result = await service.acknowledge_alarm("alarm-1")
        
        assert result is True
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_acknowledge_alarm_error(self):
        """Testa acknowledge_alarm com erro."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB Error"))
        
        service._db = mock_db
        
        result = await service.acknowledge_alarm("alarm-1")
        
        assert result is False


class TestDataServiceInternalMethods:
    """Testes dos métodos internos do DataService."""
    
    def test_format_latest_response(self):
        """Testa _format_latest_response."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        
        service = DataService(mock_settings)
        service._last_update = datetime.now(timezone.utc)
        
        values = {
            "VoltageA": {"value": 220.0},
            "CurrentA": {"value": 10.0},
            "Temperature": {"value": 45.0},
        }
        
        result = service._format_latest_response(values)
        
        assert result is not None
        assert "electrical" in result
        assert "environment" in result
        assert "vibration" in result
        assert result["electrical"]["voltage"]["a"] == 220.0
        assert result["electrical"]["current"]["a"] == 10.0
        assert result["environment"]["temperature"] == 45.0


class TestGetDataServiceFunction:
    """Testes da função get_data_service."""
    
    @pytest.mark.asyncio
    async def test_get_data_service_singleton(self):
        """Testa que get_data_service retorna singleton."""
        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.rabbitmq_host = "localhost"
        mock_settings.rabbitmq_port = 5672
        mock_settings.rabbitmq_user = "guest"
        mock_settings.rabbitmq_pass = "guest"
        
        # Reset singleton
        services_module._data_service = None
        
        with patch('services.api_service.services.get_settings', return_value=mock_settings):
            with patch.object(DataService, 'initialize', new_callable=AsyncMock):
                service1 = await get_data_service()
                service2 = await get_data_service()
                
                assert service1 is service2


class TestCloseDataServiceFunction:
    """Testes da função close_data_service."""
    
    @pytest.mark.asyncio
    async def test_close_data_service(self):
        """Testa close_data_service."""
        mock_service = AsyncMock()
        services_module._data_service = mock_service
        
        await close_data_service()
        
        mock_service.close.assert_called_once()
        assert services_module._data_service is None
    
    @pytest.mark.asyncio
    async def test_close_data_service_no_service(self):
        """Testa close_data_service sem serviço."""
        services_module._data_service = None
        
        await close_data_service()
        
        assert services_module._data_service is None


class TestDataServiceExtractValues:
    """Testes para o método _extract_values."""
    
    def test_extract_electrical_values(self):
        """Testa extração de valores elétricos."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "voltage": {"a": 220.0, "b": 221.0, "c": 222.0},
            "current": {"a": 10.0, "b": 11.0, "c": 12.0},
            "power": {"active": 5000.0, "reactive": 1000.0, "apparent": 5100.0},
            "energy": {"active": 100.0, "reactive": 20.0, "apparent": 102.0},
            "powerFactor": 0.95,
            "frequency": 60.0
        }
        
        values = service._extract_values("electrical", data)
        
        assert values["VoltageA"] == 220.0
        assert values["VoltageB"] == 221.0
        assert values["VoltageC"] == 222.0
        assert values["CurrentA"] == 10.0
        assert values["CurrentB"] == 11.0
        assert values["CurrentC"] == 12.0
        assert values["PowerActive"] == 5000.0
        assert values["PowerReactive"] == 1000.0
        assert values["PowerApparent"] == 5100.0
        assert values["EnergyActive"] == 100.0
        assert values["EnergyReactive"] == 20.0
        assert values["EnergyApparent"] == 102.0
        assert values["PowerFactor"] == 0.95
        assert values["Frequency"] == 60.0
    
    def test_extract_environment_values(self):
        """Testa extração de valores ambientais."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "temperature": 25.5,
            "humidity": 60.0,
            "caseTemperature": 45.0
        }
        
        values = service._extract_values("environment", data)
        
        assert values["Temperature"] == 25.5
        assert values["Humidity"] == 60.0
        assert values["CaseTemperature"] == 45.0
    
    def test_extract_vibration_values(self):
        """Testa extração de valores de vibração."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "axial": 0.5,
            "radial": 0.8
        }
        
        values = service._extract_values("vibration", data)
        
        assert values["Axial"] == 0.5
        assert values["Radial"] == 0.8
    
    def test_extract_unknown_sensor_type(self):
        """Testa extração para tipo de sensor desconhecido."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {"some_key": 123}
        
        values = service._extract_values("unknown", data)
        
        assert values == {}
    
    def test_extract_electrical_missing_keys(self):
        """Testa extração elétrica com chaves faltando."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {}  # Sem dados
        
        values = service._extract_values("electrical", data)
        
        assert values["VoltageA"] == 0
        assert values["PowerFactor"] == 0


class TestDataServiceUpdateCache:
    """Testes para o método _update_cache."""
    
    @pytest.mark.asyncio
    async def test_update_cache_electrical(self):
        """Testa atualização do cache com dados elétricos."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "_sensor_type": "electrical",
            "timestamp": "2024-01-01T12:00:00",
            "voltage": {"a": 220.0, "b": 221.0, "c": 222.0}
        }
        
        await service._update_cache(data)
        
        assert "VoltageA" in service._latest_values
        assert service._latest_values["VoltageA"]["value"] == 220.0
        assert service._last_update is not None
    
    @pytest.mark.asyncio
    async def test_update_cache_environment(self):
        """Testa atualização do cache com dados ambientais."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "_sensor_type": "environment",
            "timestamp": "2024-01-01T12:00:00",
            "temperature": 25.5,
            "humidity": 60.0
        }
        
        await service._update_cache(data)
        
        assert "Temperature" in service._latest_values
        assert service._latest_values["Temperature"]["value"] == 25.5
    
    @pytest.mark.asyncio
    async def test_update_cache_vibration(self):
        """Testa atualização do cache com dados de vibração."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        data = {
            "_sensor_type": "vibration",
            "axial": 0.5,
            "radial": 0.8
        }
        
        await service._update_cache(data)
        
        assert "Axial" in service._latest_values
        assert service._latest_values["Axial"]["value"] == 0.5


class TestDataServiceReadHistoryData:
    """Testes para o método _read_history_data."""
    
    @pytest.mark.asyncio
    async def test_read_history_data_success(self):
        """Testa leitura de dados históricos com sucesso."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        # Mock database
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("2024-01-01 12:00:00", 220.0),
            ("2024-01-01 12:01:00", 221.0)
        ])
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(return_value=mock_cursor)
        
        start_dt = datetime(2024, 1, 1, 11, 0, 0)
        end_dt = datetime(2024, 1, 1, 13, 0, 0)
        
        data = await service._read_history_data("history_voltage", start_dt, end_dt, 100)
        
        assert len(data) == 2
        assert data[0]["value"] == 220.0
    
    @pytest.mark.asyncio
    async def test_read_history_data_error(self):
        """Testa tratamento de erro na leitura de histórico."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(side_effect=Exception("DB Error"))
        
        start_dt = datetime(2024, 1, 1, 11, 0, 0)
        end_dt = datetime(2024, 1, 1, 13, 0, 0)
        
        data = await service._read_history_data("history_voltage", start_dt, end_dt, 100)
        
        assert data == []
    
    @pytest.mark.asyncio
    async def test_read_history_data_with_invalid_rows(self):
        """Testa leitura com linhas inválidas."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        mock_cursor = AsyncMock()
        # Primeira linha válida, segunda com valor None
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("2024-01-01 12:00:00", 220.0),
            ("2024-01-01 12:01:00", None)
        ])
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(return_value=mock_cursor)
        
        start_dt = datetime(2024, 1, 1, 11, 0, 0)
        end_dt = datetime(2024, 1, 1, 13, 0, 0)
        
        data = await service._read_history_data("history_voltage", start_dt, end_dt, 100)
        
        # Deve processar ambas linhas (None vira 0.0)
        assert len(data) == 2


class TestDataServiceGetHistoryExtended:
    """Testes estendidos para get_history."""
    
    @pytest.mark.asyncio
    async def test_get_history_without_mapping(self):
        """Testa histórico quando não há mapeamento."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        # Mock: mapeamento não encontrado
        mock_mapping_cursor = AsyncMock()
        mock_mapping_cursor.fetchone = AsyncMock(return_value=None)
        
        # Mock: lista de tabelas
        mock_tables_cursor = AsyncMock()
        mock_tables_cursor.fetchall = AsyncMock(return_value=[
            ("history_voltage",)
        ])
        
        # Mock: dados da tabela
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
        
        service._db = AsyncMock()
        service._db.execute = mock_execute
        
        result = await service.get_history("VoltageA")
        
        assert result["variable"] == "VoltageA"


class TestDataServiceGetAlarmsExtended:
    """Testes estendidos para get_alarms."""
    
    @pytest.mark.asyncio
    async def test_get_alarms_severity_mapping(self):
        """Testa mapeamento correto de severidades."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("alarm-1", "2024-01-01", "ELECTRICAL", 100, "Info", "VoltageA", 220.0, 0),
            ("alarm-2", "2024-01-01", "ELECTRICAL", 500, "Medium", "VoltageA", 230.0, 0),
            ("alarm-3", "2024-01-01", "ELECTRICAL", 900, "Critical", "VoltageA", 250.0, 1)
        ])
        mock_cursor.fetchone = AsyncMock(return_value=(2,))
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(return_value=mock_cursor)
        
        result = await service.get_alarms()
        
        assert len(result["alarms"]) == 3
        assert result["alarms"][0]["severity_name"] == "INFORMATIVE"
        assert result["alarms"][1]["severity_name"] == "MEDIUM"
        assert result["alarms"][2]["severity_name"] == "CRITICAL"
        assert result["alarms"][2]["acknowledged"] is True


class TestDataServiceGetLatestFromDb:
    """Testes para _get_latest_from_db."""
    
    @pytest.mark.asyncio
    async def test_get_latest_from_db_success(self):
        """Testa obtenção do banco com sucesso."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("VoltageA", 220.0, "2024-01-01T12:00:00"),
            ("Temperature", 25.0, "2024-01-01T12:01:00")
        ])
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(return_value=mock_cursor)
        
        result = await service._get_latest_from_db()
        
        assert "electrical" in result
        assert service._latest_values["VoltageA"]["value"] == 220.0
    
    @pytest.mark.asyncio
    async def test_get_latest_from_db_error(self):
        """Testa tratamento de erro."""
        mock_settings = MagicMock()
        service = DataService(mock_settings)
        
        service._db = AsyncMock()
        service._db.execute = AsyncMock(side_effect=Exception("DB Error"))
        
        result = await service._get_latest_from_db()
        
        assert "electrical" in result
        assert result["electrical"]["voltage"]["a"] == 0
