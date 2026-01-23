"""
Testes adicionais para configurações dos serviços.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os


class TestMQTTIngestorConfig:
    """Testes de configuração do MQTT Ingestor."""
    
    def test_config_import(self):
        """Testa que o módulo de config pode ser importado."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))
        from config import Settings
        assert Settings is not None

    def test_settings_class_exists(self):
        """Testa que a classe Settings existe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'mqtt_ingestor'))
        from config import Settings
        assert callable(Settings)


class TestOPCUAServerConfig:
    """Testes de configuração do OPC UA Server."""
    
    def test_config_import(self):
        """Testa que o módulo de config pode ser importado."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'opcua_server'))
        from config import Settings
        assert Settings is not None

    def test_settings_class_exists(self):
        """Testa que a classe Settings existe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'opcua_server'))
        from config import Settings
        assert callable(Settings)


class TestAPIServiceConfig:
    """Testes de configuração da API."""
    
    def test_config_import(self):
        """Testa que o módulo de config pode ser importado."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api_service'))
        from config import Settings
        assert Settings is not None

    def test_settings_class_exists(self):
        """Testa que a classe Settings existe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api_service'))
        from config import Settings
        assert callable(Settings)
