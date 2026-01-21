"""
Adaptador de armazenamento de histórico para asyncua.

Este módulo implementa a interface HistoryStorageInterface do asyncua
para permitir que clientes OPC UA (como o UA Expert) acessem dados históricos.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import aiosqlite
from pathlib import Path

from asyncua import ua
from asyncua.ua.ua_binary import variant_to_binary, variant_from_binary
from asyncua.server.history import HistoryStorageInterface

logger = logging.getLogger(__name__)


class HistoryStorageSQLite(HistoryStorageInterface):
    """
    Backend de armazenamento de histórico usando SQLite.
    
    Implementa a interface HistoryStorageInterface do asyncua para permitir
    que clientes OPC UA façam requisições HistoryRead padrão.
    
    Attributes:
        db_path: Caminho do banco de dados SQLite
        max_history_data_response_size: Tamanho máximo de resposta
        
    Example:
        >>> storage = HistoryStorageSQLite("/app/data/history.db")
        >>> await storage.init()
        >>> server.iserver.history_manager.set_storage(storage)
    """
    
    def __init__(self, db_path: str = "history.db", max_history_data_response_size: int = 10000):
        """
        Inicializa o storage de histórico.
        
        Args:
            db_path: Caminho do banco de dados SQLite
            max_history_data_response_size: Número máximo de registros por resposta
        """
        super().__init__(max_history_data_response_size)
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._datachanges_period: Dict[ua.NodeId, tuple] = {}
        self._events_period: Dict[ua.NodeId, tuple] = {}
        
    async def init(self):
        """Inicializa conexão com o banco de dados e cria tabelas."""
        # Criar diretório se necessário
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Conectar ao banco
        self._db = await aiosqlite.connect(self.db_path)
        
        # Criar tabela de mapeamento variável -> NodeId
        await self._db.execute('''
            CREATE TABLE IF NOT EXISTS variable_node_mapping (
                variable_name TEXT PRIMARY KEY,
                namespace_index INTEGER,
                node_identifier TEXT,
                table_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Criar tabela de histórico de alarmes
        await self._db.execute('''
            CREATE TABLE IF NOT EXISTS alarm_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alarm_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                message TEXT NOT NULL,
                source_name TEXT NOT NULL,
                value REAL NOT NULL,
                acknowledged BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Criar índice para otimizar consultas de alarmes
        await self._db.execute('''
            CREATE INDEX IF NOT EXISTS idx_alarm_timestamp 
            ON alarm_history(timestamp DESC)
        ''')
        
        await self._db.commit()
        
        logger.info(f"HistoryStorage SQLite inicializado: {self.db_path}")
        
    async def stop(self):
        """Fecha conexão com o banco de dados."""
        if self._db:
            await self._db.close()
            logger.info("HistoryStorage SQLite fechado")
            
    def _get_table_name(self, node_id: ua.NodeId) -> str:
        """Gera nome da tabela para um NodeId."""
        # Usar formato que evita caracteres especiais
        return f"history_{node_id.NamespaceIndex}_{node_id.Identifier}".replace("-", "_")
    
    async def register_variable_mapping(self, variable_name: str, node_id: ua.NodeId):
        """
        Registra o mapeamento entre nome de variável e NodeId.
        
        Isso permite que a API REST busque histórico por nome da variável.
        
        Args:
            variable_name: Nome da variável (ex: "VoltageA")
            node_id: NodeId OPC UA da variável
        """
        table = self._get_table_name(node_id)
        try:
            await self._db.execute('''
                INSERT OR REPLACE INTO variable_node_mapping 
                (variable_name, namespace_index, node_identifier, table_name)
                VALUES (?, ?, ?, ?)
            ''', (variable_name, node_id.NamespaceIndex, str(node_id.Identifier), table))
            await self._db.commit()
            logger.debug(f"Mapeamento registrado: {variable_name} -> {table}")
        except aiosqlite.Error as e:
            logger.warning(f"Erro ao registrar mapeamento para {variable_name}: {e}")
        
    async def new_historized_node(self, node_id: ua.NodeId, period, count: int = 0):
        """
        Configura um nó para historização.
        
        Args:
            node_id: ID do nó a historizar
            period: Período de retenção (timedelta ou None)
            count: Número máximo de registros (0 = ilimitado)
        """
        table = self._get_table_name(node_id)
        self._datachanges_period[node_id] = (period, count)
        
        try:
            await self._db.execute(f'''
                CREATE TABLE IF NOT EXISTS "{table}" (
                    _Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ServerTimestamp TIMESTAMP,
                    SourceTimestamp TIMESTAMP,
                    StatusCode INTEGER,
                    Value TEXT,
                    VariantType TEXT,
                    VariantBinary BLOB
                )
            ''')
            
            # Criar índice para otimização
            await self._db.execute(f'''
                CREATE INDEX IF NOT EXISTS "idx_{table}_time" 
                ON "{table}"(SourceTimestamp)
            ''')
            
            await self._db.commit()
            logger.debug(f"Tabela de histórico criada para {node_id}")
            
        except aiosqlite.Error as e:
            logger.warning(f"Erro ao criar tabela de histórico para {node_id}: {e}")
            
    async def save_node_value(self, node_id: ua.NodeId, datavalue: ua.DataValue):
        """
        Salva um valor no histórico.
        
        Args:
            node_id: ID do nó
            datavalue: Valor a salvar
        """
        table = self._get_table_name(node_id)
        
        # Padronizar formato de timestamp (sem timezone, com espaço)
        server_ts = datavalue.ServerTimestamp
        source_ts = datavalue.SourceTimestamp
        if hasattr(server_ts, 'replace'):
            server_ts = server_ts.replace(tzinfo=None).isoformat(' ')
        if hasattr(source_ts, 'replace'):
            source_ts = source_ts.replace(tzinfo=None).isoformat(' ')
        
        try:
            await self._db.execute(
                f'INSERT INTO "{table}" VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                (
                    server_ts,
                    source_ts,
                    datavalue.StatusCode.value if datavalue.StatusCode else 0,
                    str(datavalue.Value.Value) if datavalue.Value else None,
                    datavalue.Value.VariantType.name if datavalue.Value else None,
                    bytes(variant_to_binary(datavalue.Value)) if datavalue.Value else None,
                )
            )
            await self._db.commit()
            
            # Limpar dados antigos se período definido
            period, count = self._datachanges_period.get(node_id, (None, 0))
            if period:
                cutoff = datetime.now(timezone.utc) - period
                await self._db.execute(
                    f'DELETE FROM "{table}" WHERE SourceTimestamp < ?',
                    (cutoff,)
                )
                await self._db.commit()
                
            if count > 0:
                await self._db.execute(
                    f'''DELETE FROM "{table}" WHERE _Id NOT IN 
                        (SELECT _Id FROM "{table}" ORDER BY SourceTimestamp DESC LIMIT ?)''',
                    (count,)
                )
                await self._db.commit()
                
        except aiosqlite.Error as e:
            logger.error(f"Erro ao salvar valor no histórico para {node_id}: {e}")
            
    async def read_node_history(
        self, 
        node_id: ua.NodeId, 
        start: Optional[datetime], 
        end: Optional[datetime], 
        nb_values: int
    ) -> tuple:
        """
        Lê histórico de um nó.
        
        Args:
            node_id: ID do nó
            start: Data/hora inicial (inclusivo)
            end: Data/hora final (inclusivo)
            nb_values: Número máximo de valores (0 = sem limite)
            
        Returns:
            Tupla (lista de DataValues, continuation point)
        """
        table = self._get_table_name(node_id)
        results = []
        cont = None
        
        try:
            # Determinar ordem e limites
            start_time, end_time, order, limit = self._get_bounds(start, end, nb_values)
            
            query = f'''
                SELECT ServerTimestamp, SourceTimestamp, StatusCode, VariantBinary 
                FROM "{table}"
                WHERE SourceTimestamp BETWEEN ? AND ?
                ORDER BY SourceTimestamp {order}
            '''
            
            if limit > 0:
                query += f' LIMIT {limit}'
                
            cursor = await self._db.execute(query, (start_time, end_time))
            rows = await cursor.fetchall()
            
            for row in rows:
                try:
                    # Reconstruir DataValue
                    server_ts = row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0]))
                    source_ts = row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(str(row[1]))
                    status = ua.StatusCode(row[2]) if row[2] else ua.StatusCode()
                    
                    value = None
                    if row[3]:
                        from asyncua.common.utils import Buffer
                        value = variant_from_binary(Buffer(row[3]))
                    
                    # Nota: O construtor DataValue usa StatusCode_ (com underscore)
                    dv = ua.DataValue(
                        Value=value,
                        StatusCode_=status,
                        SourceTimestamp=source_ts,
                        ServerTimestamp=server_ts
                    )
                    
                    results.append(dv)
                except Exception as e:
                    logger.warning(f"Erro ao reconstruir DataValue: {e}")
                    
            # Verificar se precisa de continuation point
            if len(results) > self.max_history_data_response_size:
                cont = results[self.max_history_data_response_size].SourceTimestamp
                results = results[:self.max_history_data_response_size]
                
        except aiosqlite.Error as e:
            logger.error(f"Erro ao ler histórico de {node_id}: {e}")
            
        return results, cont
        
    @staticmethod
    def _get_bounds(start, end, nb_values):
        """Calcula limites de tempo e ordem da query."""
        order = "ASC"
        
        if start is None or start == ua.get_win_epoch():
            order = "DESC"
            start = ua.get_win_epoch()
            
        if end is None or end == ua.get_win_epoch():
            end = datetime.now(timezone.utc) + timedelta(days=1)
            
        if start < end:
            # Remover timezone para compatibilidade com o formato salvo no SQLite
            start_dt = start.replace(tzinfo=None) if hasattr(start, 'replace') else start
            end_dt = end.replace(tzinfo=None) if hasattr(end, 'replace') else end
            start_time = start_dt.isoformat(" ") if hasattr(start_dt, 'isoformat') else str(start_dt)
            end_time = end_dt.isoformat(" ") if hasattr(end_dt, 'isoformat') else str(end_dt)
        else:
            order = "DESC"
            start_dt = end.replace(tzinfo=None) if hasattr(end, 'replace') else end
            end_dt = start.replace(tzinfo=None) if hasattr(start, 'replace') else start
            start_time = start_dt.isoformat(" ") if hasattr(start_dt, 'isoformat') else str(start_dt)
            end_time = end_dt.isoformat(" ") if hasattr(end_dt, 'isoformat') else str(end_dt)
            
        limit = nb_values if nb_values else -1
        
        return start_time, end_time, order, limit
        
    async def new_historized_event(self, source_id: ua.NodeId, evtypes, period, count: int = 0):
        """Configura eventos para historização (não implementado neste projeto)."""
        self._events_period[source_id] = (period, count)
        logger.debug(f"Historização de eventos habilitada para {source_id}")
        
    async def save_event(self, event):
        """Salva evento no histórico (não implementado neste projeto)."""
        pass
        
    async def read_event_history(self, source_id, start, end, nb_values, evfilter):
        """Lê histórico de eventos (não implementado neste projeto)."""
        return [], None
        
    # ========== Métodos adicionais para API REST (Grafana) ==========
    
    async def get_history_for_api(
        self,
        variable_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Recupera histórico de uma variável para a API REST.
        
        Este método é usado pelo Grafana/FastAPI para consultar o histórico
        armazenado pelo servidor OPC UA.
        
        Args:
            variable_name: Nome da variável (ex: "VoltageA")
            start_time: Início do período
            end_time: Fim do período
            limit: Número máximo de registros
            
        Returns:
            Lista de pontos históricos no formato da API
        """
        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(hours=24))
        
        # Remover timezone para compatibilidade com SQLite
        start_dt = start_time.replace(tzinfo=None) if hasattr(start_time, 'replace') else start_time
        end_dt = end_time.replace(tzinfo=None) if hasattr(end_time, 'replace') else end_time
        
        results = []
        
        try:
            # Primeiro, tentar buscar o mapeamento exato da variável
            cursor = await self._db.execute(
                "SELECT table_name FROM variable_node_mapping WHERE variable_name = ?",
                (variable_name,)
            )
            mapping = await cursor.fetchone()
            
            if mapping:
                # Tabela específica encontrada
                table_name = mapping[0]
                results = await self._read_history_from_table(table_name, start_dt, end_dt, limit)
            else:
                # Fallback: buscar em todas as tabelas (pode retornar tudo)
                cursor = await self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'history_%'"
                )
                tables = await cursor.fetchall()
                
                for (table_name,) in tables:
                    table_results = await self._read_history_from_table(table_name, start_dt, end_dt, limit)
                    results.extend(table_results)
                    
        except aiosqlite.Error as e:
            logger.error(f"Erro ao recuperar histórico para API: {e}")
            
        # Ordenar por timestamp e limitar
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]
    
    async def _read_history_from_table(
        self, 
        table_name: str, 
        start_dt: datetime, 
        end_dt: datetime, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Lê dados históricos de uma tabela específica.
        
        Args:
            table_name: Nome da tabela
            start_dt: Início do período (sem timezone)
            end_dt: Fim do período (sem timezone)
            limit: Número máximo de registros
            
        Returns:
            Lista de pontos históricos
        """
        results = []
        
        try:
            query = f'''
                SELECT SourceTimestamp, Value, VariantBinary
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
                    ts_str = row[0]
                    if isinstance(ts_str, str):
                        ts = datetime.fromisoformat(ts_str)
                    else:
                        ts = ts_str
                    
                    # Tentar extrair valor do binário ou do texto
                    value = None
                    if row[2]:  # VariantBinary
                        from asyncua.common.utils import Buffer
                        variant = variant_from_binary(Buffer(row[2]))
                        value = variant.Value
                    elif row[1]:  # Value (texto)
                        value = float(row[1])
                        
                    if value is not None:
                        results.append({
                            "timestamp": ts.isoformat(),
                            "value": value,
                            "quality": "Good",
                            "table": table_name
                        })
                except Exception as e:
                    logger.debug(f"Erro ao processar registro: {e}")
                    
        except aiosqlite.Error as e:
            logger.debug(f"Erro ao consultar tabela {table_name}: {e}")
            
        return results
        
    async def get_all_historized_variables(self) -> List[str]:
        """
        Retorna lista de todas as variáveis com histórico.
        
        Returns:
            Lista de nomes de variáveis historizadas
        """
        variables = []
        
        try:
            cursor = await self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'history_%'"
            )
            tables = await cursor.fetchall()
            
            for (table_name,) in tables:
                # Extrair identificador da variável do nome da tabela
                # Formato: history_{namespace}_{identifier}
                parts = table_name.split("_", 2)
                if len(parts) >= 3:
                    variables.append(parts[2])
                    
        except aiosqlite.Error as e:
            logger.error(f"Erro ao listar variáveis historizadas: {e}")
            
        return variables
        
    async def get_statistics_for_api(
        self, 
        variable_name: str, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Calcula estatísticas de uma variável para a API.
        
        Args:
            variable_name: Nome da variável
            hours: Período em horas
            
        Returns:
            Dicionário com min, max, avg, count
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        stats = {
            "variable_name": variable_name,
            "period_hours": hours,
            "min": None,
            "max": None,
            "avg": None,
            "count": 0
        }
        
        try:
            cursor = await self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'history_%'"
            )
            tables = await cursor.fetchall()
            
            all_values = []
            
            for (table_name,) in tables:
                try:
                    query = f'''
                        SELECT VariantBinary, Value
                        FROM "{table_name}"
                        WHERE SourceTimestamp > ?
                    '''
                    cursor = await self._db.execute(query, (cutoff.isoformat(" "),))
                    rows = await cursor.fetchall()
                    
                    for row in rows:
                        value = None
                        if row[0]:
                            from asyncua.common.utils import Buffer
                            variant = variant_from_binary(Buffer(row[0]))
                            value = variant.Value
                        elif row[1]:
                            value = float(row[1])
                            
                        if value is not None:
                            all_values.append(value)
                            
                except aiosqlite.Error:
                    pass
                    
            if all_values:
                stats["min"] = min(all_values)
                stats["max"] = max(all_values)
                stats["avg"] = sum(all_values) / len(all_values)
                stats["count"] = len(all_values)
                
        except aiosqlite.Error as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            
        return stats
    
    # ========== Métodos para Alarmes ==========
    
    async def save_alarm(self, alarm_data: Dict[str, Any]):
        """
        Salva um alarme no banco de dados.
        
        Args:
            alarm_data: Dicionário com dados do alarme:
                - id: ID único do alarme
                - timestamp: Data/hora do evento
                - category: Categoria (Electrical, Environment)
                - severity: Nível de severidade (100-900)
                - message: Mensagem descritiva
                - source_name: Nome da variável fonte
                - value: Valor que disparou o alarme
                - acknowledged: Se foi reconhecido
        """
        try:
            # Padronizar formato do timestamp (sem timezone, com espaço)
            timestamp = alarm_data.get('timestamp', datetime.now(timezone.utc).isoformat())
            if isinstance(timestamp, str):
                # Remover timezone e substituir T por espaço
                timestamp = timestamp.replace('+00:00', '').replace('T', ' ')
            
            await self._db.execute('''
                INSERT INTO alarm_history 
                (alarm_id, timestamp, category, severity, message, source_name, value, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alarm_data.get('id', ''),
                timestamp,
                alarm_data.get('category', ''),
                alarm_data.get('severity', 0),
                alarm_data.get('message', ''),
                alarm_data.get('source_name', ''),
                alarm_data.get('value', 0.0),
                alarm_data.get('acknowledged', False)
            ))
            await self._db.commit()
            logger.debug(f"Alarme salvo: {alarm_data.get('id')}")
        except aiosqlite.Error as e:
            logger.error(f"Erro ao salvar alarme: {e}")
    
    async def get_alarms(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        category: Optional[str] = None,
        active_only: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Recupera alarmes do banco de dados.
        
        Args:
            start_time: Início do período
            end_time: Fim do período
            category: Filtrar por categoria
            active_only: Se True, apenas alarmes não reconhecidos
            limit: Número máximo de resultados
            
        Returns:
            Lista de alarmes
        """
        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(hours=24))
        
        # Remover timezone para compatibilidade com SQLite
        start_dt = start_time.replace(tzinfo=None) if hasattr(start_time, 'replace') and start_time.tzinfo else start_time
        end_dt = end_time.replace(tzinfo=None) if hasattr(end_time, 'replace') and end_time.tzinfo else end_time
        
        alarms = []
        
        try:
            query = '''
                SELECT alarm_id, timestamp, category, severity, message, source_name, value, acknowledged
                FROM alarm_history
                WHERE timestamp BETWEEN ? AND ?
            '''
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
            
            # Mapear severity value para nome
            severity_names = {100: "INFORMATIVE", 250: "LOW", 500: "MEDIUM", 700: "HIGH", 900: "CRITICAL"}
            
            for row in rows:
                alarms.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "category": row[2],
                    "severity": row[3],
                    "severity_name": severity_names.get(row[3], "UNKNOWN"),
                    "message": row[4],
                    "source_name": row[5],
                    "value": row[6],
                    "acknowledged": bool(row[7])
                })
                
        except aiosqlite.Error as e:
            logger.error(f"Erro ao recuperar alarmes: {e}")
            
        return alarms
    
    async def get_active_alarm_count(self) -> int:
        """
        Conta alarmes ativos (não reconhecidos) nas últimas 24 horas.
        
        Returns:
            Número de alarmes ativos
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_dt = cutoff.replace(tzinfo=None)
        
        try:
            cursor = await self._db.execute('''
                SELECT COUNT(*) FROM alarm_history
                WHERE acknowledged = 0 AND timestamp > ?
            ''', (cutoff_dt.isoformat(" "),))
            result = await cursor.fetchone()
            return result[0] if result else 0
        except aiosqlite.Error as e:
            logger.error(f"Erro ao contar alarmes ativos: {e}")
            return 0
