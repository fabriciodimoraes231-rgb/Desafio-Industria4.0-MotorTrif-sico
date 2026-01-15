"""
Historiador de dados OPC UA.

Este módulo implementa o armazenamento e recuperação de dados históricos
para variáveis do servidor OPC UA, utilizando SQLite como backend.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiosqlite
from dataclasses import dataclass
from pathlib import Path

from config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class HistoricalDataPoint:
    """
    Ponto de dado histórico.
    
    Attributes:
        timestamp: Data/hora do registro
        variable_name: Nome da variável
        value: Valor registrado
        quality: Qualidade do dado (Good, Bad, etc.)
    """
    timestamp: datetime
    variable_name: str
    value: float
    quality: str = "Good"
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "variable_name": self.variable_name,
            "value": self.value,
            "quality": self.quality
        }


class Historian:
    """
    Historiador para dados OPC UA.
    
    Armazena e recupera dados históricos de variáveis do motor
    utilizando SQLite como banco de dados.
    
    Attributes:
        settings: Configurações do serviço
        db_path: Caminho do banco de dados
        _db: Conexão com o banco de dados
        historized_variables: Lista de variáveis com histórico habilitado
        
    Example:
        >>> historian = Historian()
        >>> await historian.initialize()
        >>> await historian.record("VoltageA", 220.5)
        >>> history = await historian.get_history("VoltageA", hours=24)
    """
    
    # Variáveis que devem ter histórico conforme especificação
    HISTORIZED_VARIABLES = [
        # Elétricas
        "VoltageA", "VoltageB", "VoltageC",
        "CurrentA", "CurrentB", "CurrentC",
        "PowerActive", "PowerReactive", "PowerApparent",
        "EnergyActive", "EnergyReactive", "EnergyApparent",
        "PowerFactor", "Frequency",
        # Temperatura da carcaça
        "CaseTemperature"
    ]
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o historiador.
        
        Args:
            settings: Configurações (usa padrão se não fornecido)
        """
        self.settings = settings or get_settings()
        self.db_path = self.settings.database_path
        self._db: Optional[aiosqlite.Connection] = None
        self.historized_variables = set(self.HISTORIZED_VARIABLES)
        self._write_buffer: List[HistoricalDataPoint] = []
        self._buffer_size = 100
        self._buffer_flush_interval = 5  # segundos
        self._flush_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """
        Inicializa o historiador e cria tabelas necessárias.
        
        Cria o banco de dados e tabelas se não existirem.
        """
        # Criar diretório se necessário
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Conectar ao banco
        self._db = await aiosqlite.connect(self.db_path)
        
        # Criar tabelas
        await self._create_tables()
        
        # Iniciar task de flush do buffer
        self._flush_task = asyncio.create_task(self._periodic_flush())
        
        logger.info(f"Historiador inicializado: {self.db_path}")
        
    async def close(self):
        """Fecha conexão com o banco de dados."""
        # Parar task de flush
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
                
        # Flush final do buffer
        await self._flush_buffer()
        
        # Fechar conexão
        if self._db:
            await self._db.close()
            logger.info("Historiador fechado")
            
    async def _create_tables(self):
        """Cria tabelas do banco de dados."""
        # Tabela de histórico de variáveis
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS variable_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                variable_name TEXT NOT NULL,
                value REAL NOT NULL,
                quality TEXT DEFAULT 'Good',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para otimização de queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_var_history_name_time 
            ON variable_history(variable_name, timestamp)
        """)
        
        # Tabela de histórico de alarmes
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS alarm_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alarm_id TEXT UNIQUE NOT NULL,
                timestamp DATETIME NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                message TEXT NOT NULL,
                source_name TEXT NOT NULL,
                value REAL NOT NULL,
                acknowledged BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alarm_history_time 
            ON alarm_history(timestamp)
        """)
        
        await self._db.commit()
        logger.debug("Tabelas do historiador criadas")
        
    async def record(self, variable_name: str, value: float, timestamp: Optional[datetime] = None):
        """
        Registra um valor no histórico.
        
        Args:
            variable_name: Nome da variável
            value: Valor a registrar
            timestamp: Data/hora do registro (usa UTC agora se não fornecido)
        """
        # Verificar se variável deve ser historizada
        if variable_name not in self.historized_variables:
            return
            
        timestamp = timestamp or datetime.utcnow()
        
        # Adicionar ao buffer
        self._write_buffer.append(HistoricalDataPoint(
            timestamp=timestamp,
            variable_name=variable_name,
            value=value
        ))
        
        # Flush se buffer cheio
        if len(self._write_buffer) >= self._buffer_size:
            await self._flush_buffer()
            
    async def record_batch(self, values: Dict[str, float], timestamp: Optional[datetime] = None):
        """
        Registra múltiplos valores no histórico.
        
        Args:
            values: Dicionário com nome da variável e valor
            timestamp: Data/hora comum para todos os registros
        """
        timestamp = timestamp or datetime.utcnow()
        
        for variable_name, value in values.items():
            await self.record(variable_name, value, timestamp)
            
    async def record_alarm(self, alarm_data: Dict[str, Any]):
        """
        Registra um alarme no histórico.
        
        Args:
            alarm_data: Dicionário com dados do alarme
        """
        try:
            await self._db.execute("""
                INSERT OR REPLACE INTO alarm_history 
                (alarm_id, timestamp, category, severity, message, source_name, value, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alarm_data.get('id'),
                alarm_data.get('timestamp'),
                alarm_data.get('category'),
                alarm_data.get('severity'),
                alarm_data.get('message'),
                alarm_data.get('source_name'),
                alarm_data.get('value'),
                alarm_data.get('acknowledged', False)
            ))
            await self._db.commit()
            logger.debug(f"Alarme registrado: {alarm_data.get('id')}")
        except Exception as e:
            logger.error(f"Erro ao registrar alarme: {e}")
            
    async def _flush_buffer(self):
        """Grava buffer no banco de dados."""
        if not self._write_buffer:
            return
            
        try:
            await self._db.executemany("""
                INSERT INTO variable_history (timestamp, variable_name, value, quality)
                VALUES (?, ?, ?, ?)
            """, [
                (dp.timestamp.isoformat(), dp.variable_name, dp.value, dp.quality)
                for dp in self._write_buffer
            ])
            await self._db.commit()
            
            count = len(self._write_buffer)
            self._write_buffer.clear()
            logger.debug(f"Buffer gravado: {count} registros")
            
        except Exception as e:
            logger.error(f"Erro ao gravar buffer: {e}")
            
    async def _periodic_flush(self):
        """Task para flush periódico do buffer."""
        while True:
            try:
                await asyncio.sleep(self._buffer_flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no flush periódico: {e}")
                
    async def get_history(
        self,
        variable_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        hours: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Recupera histórico de uma variável.
        
        Args:
            variable_name: Nome da variável
            start_time: Início do período
            end_time: Fim do período
            hours: Últimas N horas (alternativa a start/end)
            limit: Número máximo de registros
            
        Returns:
            Lista de pontos históricos
        """
        # Determinar período
        if hours:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
        else:
            end_time = end_time or datetime.utcnow()
            start_time = start_time or (end_time - timedelta(hours=24))
            
        try:
            cursor = await self._db.execute("""
                SELECT timestamp, variable_name, value, quality
                FROM variable_history
                WHERE variable_name = ?
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (variable_name, start_time.isoformat(), end_time.isoformat(), limit))
            
            rows = await cursor.fetchall()
            
            return [
                {
                    "timestamp": row[0],
                    "variable_name": row[1],
                    "value": row[2],
                    "quality": row[3]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Erro ao recuperar histórico: {e}")
            return []
            
    async def get_alarm_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Recupera histórico de alarmes.
        
        Args:
            start_time: Início do período
            end_time: Fim do período
            category: Filtrar por categoria
            limit: Número máximo de registros
            
        Returns:
            Lista de alarmes
        """
        end_time = end_time or datetime.utcnow()
        start_time = start_time or (end_time - timedelta(days=7))
        
        try:
            query = """
                SELECT alarm_id, timestamp, category, severity, message, 
                       source_name, value, acknowledged
                FROM alarm_history
                WHERE timestamp BETWEEN ? AND ?
            """
            params = [start_time.isoformat(), end_time.isoformat()]
            
            if category:
                query += " AND category = ?"
                params.append(category)
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "category": row[2],
                    "severity": row[3],
                    "message": row[4],
                    "source_name": row[5],
                    "value": row[6],
                    "acknowledged": bool(row[7])
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Erro ao recuperar histórico de alarmes: {e}")
            return []
            
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Remove dados antigos do histórico.
        
        Args:
            days_to_keep: Número de dias de dados a manter
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        
        try:
            # Limpar histórico de variáveis
            await self._db.execute("""
                DELETE FROM variable_history WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            # Limpar histórico de alarmes
            await self._db.execute("""
                DELETE FROM alarm_history WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            await self._db.commit()
            logger.info(f"Dados anteriores a {cutoff} removidos")
            
        except Exception as e:
            logger.error(f"Erro ao limpar dados antigos: {e}")
            
    async def get_statistics(self, variable_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Calcula estatísticas de uma variável.
        
        Args:
            variable_name: Nome da variável
            hours: Período em horas
            
        Returns:
            Dicionário com min, max, avg, count
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        try:
            cursor = await self._db.execute("""
                SELECT 
                    MIN(value) as min_val,
                    MAX(value) as max_val,
                    AVG(value) as avg_val,
                    COUNT(*) as count
                FROM variable_history
                WHERE variable_name = ? AND timestamp > ?
            """, (variable_name, cutoff.isoformat()))
            
            row = await cursor.fetchone()
            
            return {
                "variable_name": variable_name,
                "period_hours": hours,
                "min": row[0],
                "max": row[1],
                "avg": row[2],
                "count": row[3]
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {}
