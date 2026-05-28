"""MCP SQL Server tool — natural language to SQL via standardized protocol.

Adapted from: github.com/vivekpathania/ai-experiments (mcp/)
Supports MySQL and PostgreSQL databases. Read-only SELECT queries.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import pymysql
    import psycopg2
    HAS_CONNECTORS = True
except ImportError:
    HAS_CONNECTORS = False


class MCPSQLExecutor:
    """Read-only SQL query executor for natural language database access."""

    def __init__(self):
        self._connections: dict[str, dict] = {}

    def register_connection(
        self,
        name: str,
        db_type: str,
        host: str,
        user: str,
        password: str,
        database: str,
        port: Optional[str] = None,
    ):
        self._connections[name] = {
            "db_type": db_type,
            "host": host,
            "user": user,
            "password": password,
            "database": database,
            "port": port or ("5432" if db_type == "postgres" else "3306"),
        }

    def get_schema(self, connection_name: str = "default") -> str:
        conn = self._connections.get(connection_name)
        if not conn:
            return "No connection registered. Use register_connection first."
        if not HAS_CONNECTORS:
            return "Database connectors not installed (pymysql/psycopg2)"

        if conn["db_type"] == "mysql":
            connection = pymysql.connect(
                host=conn["host"], user=conn["user"],
                password=conn["password"], database=conn["database"],
            )
            schema = {}
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                               IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s
                        ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """, (conn["database"],))
                    for row in cursor.fetchall():
                        tname = row[0]
                        col = {"name": row[1], "type": row[2], "nullable": row[4],
                               "default": row[5], "key": row[6]}
                        schema.setdefault(tname, []).append(col)
            finally:
                connection.close()
        else:
            connection = psycopg2.connect(
                database=conn["database"], user=conn["user"],
                password=conn["password"], host=conn["host"], port=conn["port"],
            )
            schema = {}
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT table_name, column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position
                    """)
                    for row in cursor.fetchall():
                        schema.setdefault(row[0], []).append(
                            {"name": row[1], "type": row[2], "nullable": row[3], "default": row[4]}
                        )
            finally:
                connection.close()

        return json.dumps(schema, indent=2)

    def execute_query(self, query: str, connection_name: str = "default") -> str:
        conn = self._connections.get(connection_name)
        if not conn:
            return "No connection registered."
        if not HAS_CONNECTORS:
            return "Database connectors not installed"

        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT") and "EXPLAIN" not in query_upper:
            return "Only SELECT queries are allowed"

        if conn["db_type"] == "mysql":
            connection = pymysql.connect(
                host=conn["host"], user=conn["user"],
                password=conn["password"], database=conn["database"],
            )
            try:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query)
                    return json.dumps(cursor.fetchall(), indent=2, default=str)
            finally:
                connection.close()
        else:
            connection = psycopg2.connect(
                database=conn["database"], user=conn["user"],
                password=conn["password"], host=conn["host"], port=conn["port"],
            )
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    cols = [desc[0] for desc in cursor.description]
                    return json.dumps(
                        [dict(zip(cols, row)) for row in cursor.fetchall()],
                        indent=2, default=str
                    )
            finally:
                connection.close()


mcp_sql = MCPSQLExecutor()
