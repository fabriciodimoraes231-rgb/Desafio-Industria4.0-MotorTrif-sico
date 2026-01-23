"""
Serviço de acesso a dados do motor 50CV.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import aiosqlite
import aio_pika
from pathlib import Path

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class DataService:
    """Serviço para consultar estado atual, histórico e alarmes do motor."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._db: Optional[aiosqlite.Connection] = None
        self._rabbitmq_conn: Optional[aio_pika.Connection] = None
        self._latest_values: Dict[str, Any] = {}
        self._last_update: Optional[datetime] = None
        self._consuming = False
        
    async def initialize(self):
        """Inicializa conexões."""
        await self._connect_database()
        await self._connect_rabbitmq()
        logger.info("DataService inicializado")
        
    async def close(self):
        """Fecha todas as conexões."""
        self._consuming = False
        
        if self._db:
            await self._db.close()
            
        if self._rabbitmq_conn and not self._rabbitmq_conn.is_closed:
            await self._rabbitmq_conn.close()
            
        logger.info("DataService fechado")
        
    async def _connect_database(self):
        """Conecta ao banco de dados SQLite."""
        db_path = self.settings.database_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        self._db = await aiosqlite.connect(db_path)
        await self._create_tables()
        logger.info(f"Conectado ao banco: {db_path}")
        
    async def _create_tables(self):
        """Cria tabelas necessárias no banco."""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS variable_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                variable_name TEXT NOT NULL,
                value REAL NOT NULL,
                quality TEXT DEFAULT 'Good'
            )
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_var_history_name_time 
            ON variable_history(variable_name, timestamp)
        """)
        
        # Tabela de alarmes
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
                acknowledged BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Tabela de cache de valores atuais
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS current_values (
                variable_name TEXT PRIMARY KEY,
                value REAL NOT NULL,
                timestamp DATETIME NOT NULL
            )
        """)
        
        await self._db.commit()
        
    async def _connect_rabbitmq(self):
        """Conecta ao RabbitMQ e inicia consumo de mensagens."""
        try:
            url = f"amqp://{self.settings.rabbitmq_user}:{self.settings.rabbitmq_pass}@{self.settings.rabbitmq_host}:{self.settings.rabbitmq_port}/"
            
            self._rabbitmq_conn = await aio_pika.connect_robust(url)
            channel = await self._rabbitmq_conn.channel()
            
            # Consumir da fila que recebe todas as mensagens (motor.# routing key)
            queue_name = "motor_readings.all"
            
            try:
                queue = await channel.declare_queue(queue_name, durable=True, passive=True)
            except aio_pika.exceptions.ChannelNotFoundEntity:
                queue = await channel.declare_queue(queue_name, durable=True)
                
            self._consuming = True
            
            # Iniciar consumo em background
            asyncio.create_task(self._consume_messages(queue))
            
            logger.info("Conectado ao RabbitMQ")
            
        except Exception as e:
            logger.warning(f"Não foi possível conectar ao RabbitMQ: {e}")
            # API pode funcionar sem RabbitMQ usando apenas histórico
            
    async def _consume_messages(self, queue):
        """Consome mensagens do RabbitMQ e atualiza cache."""
        import json
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._consuming:
                    break
                    
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        await self._update_cache(data)
                    except Exception as e:
                        logger.error(f"Erro ao processar mensagem: {e}")
                        
    async def _update_cache(self, data: Dict):
        """Atualiza cache de valores atuais."""
        sensor_type = data.get('_sensor_type', '')
        timestamp = data.get('timestamp', datetime.now(timezone.utc).isoformat())
        
        values = self._extract_values(sensor_type, data)
        
        for name, value in values.items():
            self._latest_values[name] = {
                'value': value,
                'timestamp': timestamp
            }
            
        self._last_update = datetime.now(timezone.utc)
        
    def _extract_values(self, sensor_type: str, data: Dict) -> Dict[str, float]:
        """Extrai valores das variáveis de uma mensagem."""
        values = {}
        
        if sensor_type == "electrical":
            voltage = data.get("voltage", {})
            values["VoltageA"] = voltage.get("a", 0)
            values["VoltageB"] = voltage.get("b", 0)
            values["VoltageC"] = voltage.get("c", 0)
            
            current = data.get("current", {})
            values["CurrentA"] = current.get("a", 0)
            values["CurrentB"] = current.get("b", 0)
            values["CurrentC"] = current.get("c", 0)
            
            power = data.get("power", {})
            values["PowerActive"] = power.get("active", 0)
            values["PowerReactive"] = power.get("reactive", 0)
            values["PowerApparent"] = power.get("apparent", 0)
            
            energy = data.get("energy", {})
            values["EnergyActive"] = energy.get("active", 0)
            values["EnergyReactive"] = energy.get("reactive", 0)
            values["EnergyApparent"] = energy.get("apparent", 0)
            
            values["PowerFactor"] = data.get("powerFactor", 0)
            values["Frequency"] = data.get("frequency", 0)
            
        elif sensor_type == "environment":
            values["Temperature"] = data.get("temperature", 0)
            values["Humidity"] = data.get("humidity", 0)
            values["CaseTemperature"] = data.get("caseTemperature", 0)
            
        elif sensor_type == "vibration":
            values["Axial"] = data.get("axial", 0)
            values["Radial"] = data.get("radial", 0)
            
        return values
        
    async def get_latest(self) -> Dict[str, Any]:
        """Retorna os últimos valores de todas as variáveis."""
        if self._latest_values:
            return self._format_latest_response(self._latest_values)
            
        # Se cache vazio, tentar obter do banco
        return await self._get_latest_from_db()
        
    def _format_latest_response(self, values: Dict) -> Dict[str, Any]:
        """Formata valores para resposta da API."""
        def get_val(name: str) -> float:
            v = values.get(name, {})
            return v.get('value', 0) if isinstance(v, dict) else 0
            
        return {
            "timestamp": self._last_update or datetime.now(timezone.utc),
            "electrical": {
                "voltage": {
                    "a": get_val("VoltageA"),
                    "b": get_val("VoltageB"),
                    "c": get_val("VoltageC")
                },
                "current": {
                    "a": get_val("CurrentA"),
                    "b": get_val("CurrentB"),
                    "c": get_val("CurrentC")
                },
                "power": {
                    "active": get_val("PowerActive"),
                    "reactive": get_val("PowerReactive"),
                    "apparent": get_val("PowerApparent")
                },
                "energy": {
                    "active": get_val("EnergyActive"),
                    "reactive": get_val("EnergyReactive"),
                    "apparent": get_val("EnergyApparent")
                },
                "powerFactor": get_val("PowerFactor"),
                "frequency": get_val("Frequency")
            },
            "environment": {
                "temperature": get_val("Temperature"),
                "humidity": get_val("Humidity"),
                "caseTemperature": get_val("CaseTemperature")
            },
            "vibration": {
                "axial": get_val("Axial"),
                "radial": get_val("Radial")
            },
            "active_alarms": 0  # Será atualizado pelo alarm service
        }
        
    async def _get_latest_from_db(self) -> Dict[str, Any]:
        """Obtém últimos valores do banco de dados."""
        try:
            cursor = await self._db.execute("""
                SELECT variable_name, value, timestamp
                FROM current_values
            """)
            rows = await cursor.fetchall()
            
            values = {}
            latest_ts = None
            
            for row in rows:
                values[row[0]] = {'value': row[1], 'timestamp': row[2]}
                ts = datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2]
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
                    
            self._latest_values = values
            self._last_update = latest_ts
            
            return self._format_latest_response(values)
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do banco: {e}")
            return self._format_latest_response({})
            
    async def get_history(
        self,
        variable: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """Retorna histórico de uma variável."""
        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(hours=24))
        
        # Remover timezone para compatibilidade com SQLite
        start_dt = start_time.replace(tzinfo=None) if hasattr(start_time, 'replace') else start_time
        end_dt = end_time.replace(tzinfo=None) if hasattr(end_time, 'replace') else end_time
        
        data = []
        
        try:
            # Primeiro, tentar buscar usando a tabela de mapeamento
            cursor = await self._db.execute(
                "SELECT table_name FROM variable_node_mapping WHERE variable_name = ?",
                (variable,)
            )
            mapping = await cursor.fetchone()
            
            if mapping:
                # Tabela específica encontrada
                table_name = mapping[0]
                data = await self._read_history_data(table_name, start_dt, end_dt, limit)
            else:
                # Fallback: buscar em todas as tabelas de histórico
                cursor = await self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'history_%'"
                )
                tables = await cursor.fetchall()
                
                for (table_name,) in tables:
                    table_data = await self._read_history_data(table_name, start_dt, end_dt, limit)
                    data.extend(table_data)
            
            # Ordenar por timestamp ascendente para gráficos
            data.sort(key=lambda x: x["timestamp"], reverse=False)
            
            return {
                "variable": variable,
                "start_time": start_time,
                "end_time": end_time,
                "count": len(data),
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter histórico: {e}")
            return {
                "variable": variable,
                "start_time": start_time,
                "end_time": end_time,
                "count": 0,
                "data": []
            }
    
    async def _read_history_data(
        self,
        table_name: str,
        start_dt: datetime,
        end_dt: datetime,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Lê dados históricos de uma tabela específica."""
        data = []
        
        try:
            query = f'''
                SELECT SourceTimestamp, Value
                FROM "{table_name}"
                WHERE SourceTimestamp BETWEEN ? AND ?
                ORDER BY SourceTimestamp DESC
                LIMIT ?
            '''
            cursor = await self._db.execute(
                query, 
                (start_dt.isoformat(" "), end_dt.isoformat(" "), limit)
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                try:
                    ts = row[0]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts)
                    
                    value = float(row[1]) if row[1] else 0.0
                    
                    # Timestamp ISO8601 com Z para Grafana JSON datasource
                    ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if hasattr(ts, 'strftime') else str(ts)
                    
                    data.append({
                        "timestamp": ts_iso,
                        "value": value,
                        "quality": "Good"
                    })
                except Exception as e:
                    logger.debug(f"Erro ao processar registro: {e}")
                    
        except Exception as e:
            logger.debug(f"Erro ao consultar tabela {table_name}: {e}")
        
        return data
            
    async def get_alarms(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        category: Optional[str] = None,
        active_only: bool = False,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Retorna histórico de alarmes."""
        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(days=7))
        
        # Remover timezone para compatibilidade com SQLite
        start_dt = start_time.replace(tzinfo=None) if hasattr(start_time, 'replace') and start_time.tzinfo else start_time
        end_dt = end_time.replace(tzinfo=None) if hasattr(end_time, 'replace') and end_time.tzinfo else end_time
        
        try:
            query = """
                SELECT alarm_id, timestamp, category, severity, message,
                       source_name, value, acknowledged
                FROM alarm_history
                WHERE timestamp BETWEEN ? AND ?
            """
            params = [start_dt.isoformat(" "), end_dt.isoformat(" ")]
            
            if category:
                query += " AND category = ?"
                params.append(category)
                
            if active_only:
                query += " AND acknowledged = 0"
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
            
            # Mapear severidade para nome
            severity_names = {
                100: "INFORMATIVE",
                250: "LOW",
                500: "MEDIUM",
                700: "HIGH",
                900: "CRITICAL"
            }
            
            alarms = [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "category": row[2],
                    "severity": row[3],
                    "severity_name": severity_names.get(row[3], "UNKNOWN"),
                    "message": row[4],
                    "source_name": row[5],
                    "value": row[6],
                    "acknowledged": bool(row[7])
                }
                for row in rows
            ]
            
            # Contar alarmes ativos
            active_cursor = await self._db.execute("""
                SELECT COUNT(*) FROM alarm_history WHERE acknowledged = 0
            """)
            active_count = (await active_cursor.fetchone())[0]
            
            return {
                "active_count": active_count,
                "total_count": len(alarms),
                "alarms": alarms
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter alarmes: {e}")
            return {
                "active_count": 0,
                "total_count": 0,
                "alarms": []
            }
            
    async def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Reconhece um alarme."""
        try:
            await self._db.execute("""
                UPDATE alarm_history SET acknowledged = 1 WHERE alarm_id = ?
            """, (alarm_id,))
            await self._db.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao reconhecer alarme: {e}")
            return False
            
    async def get_statistics(self, variable: str, hours: int = 24) -> Dict[str, Any]:
        """Calcula estatísticas de uma variável."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        try:
            cursor = await self._db.execute("""
                SELECT 
                    MIN(value), MAX(value), AVG(value), COUNT(*)
                FROM variable_history
                WHERE variable_name = ? AND timestamp > ?
            """, (variable, cutoff.isoformat()))
            
            row = await cursor.fetchone()
            
            return {
                "variable": variable,
                "period_hours": hours,
                "min": row[0],
                "max": row[1],
                "avg": row[2],
                "count": row[3]
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {
                "variable": variable,
                "period_hours": hours,
                "min": None,
                "max": None,
                "avg": None,
                "count": 0
            }


# Instância global do serviço
_data_service: Optional[DataService] = None


async def get_data_service() -> DataService:
    """Retorna instância do serviço de dados."""
    global _data_service
    
    if _data_service is None:
        _data_service = DataService()
        await _data_service.initialize()
        
    return _data_service


async def close_data_service():
    """Fecha o serviço de dados."""
    global _data_service
    
    if _data_service:
        await _data_service.close()
        _data_service = None
