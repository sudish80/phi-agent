"""SQL database query module for J.A.R.V.I.S.

Supports SQLite, PostgreSQL, MySQL — run queries and get results as text.
"""

import asyncio
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


async def query_database(sql: str, db_type: str = "sqlite",
                         database: str = "", host: str = "localhost",
                         port: int = 5432, user: str = "",
                         password: str = "") -> str:
    """Execute a SQL query and return results as formatted text."""
    db_type = db_type.lower()

    if db_type == "sqlite":
        return await _query_sqlite(sql, database)
    elif db_type == "postgres" or db_type == "postgresql":
        return await _query_postgres(sql, database, host, port, user, password)
    elif db_type == "mysql":
        return await _query_mysql(sql, database, host, port, user, password)
    else:
        return f"Unsupported database type: {db_type}. Use: sqlite, postgres, mysql"


async def _query_sqlite(sql: str, database: str) -> str:
    """Query a SQLite database file."""
    try:
        import aiosqlite
    except ImportError:
        return "SQLite requires aiosqlite"

    path = os.path.abspath(os.path.expanduser(database))
    if not os.path.exists(path):
        return f"Database file not found: {path}"

    loop = asyncio.get_event_loop()

    def _run():
        import sqlite3
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            return "Query returned no results."
        columns = [d[0] for d in cur.description]
        out = f"**{len(rows)} row(s)**\nColumns: {', '.join(columns)}\n"
        for i, row in enumerate(rows[:100]):
            out += f"\nRow {i + 1}: " + " | ".join(
                f"{c}={str(row[c])[:60]}" for c in columns)
        if len(rows) > 100:
            out += f"\n... [{len(rows) - 100} more rows]"
        conn.close()
        return out

    try:
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        return f"SQLite error: {e}"


async def _query_postgres(sql: str, database: str, host: str,
                          port: int, user: str, password: str) -> str:
    """Query a PostgreSQL database."""
    try:
        import asyncpg
    except ImportError:
        return "PostgreSQL requires asyncpg"

    if not database:
        return "PostgreSQL requires a database name"
    if not user:
        return "PostgreSQL requires a username"

    try:
        conn = await asyncpg.connect(
            host=host, port=port or 5432,
            user=user, password=password or "",
            database=database,
        )
        records = await conn.fetch(sql)
        await conn.close()
        if not records:
            return "Query returned no results."
        columns = list(records[0].keys())
        out = f"**{len(records)} row(s)**\nColumns: {', '.join(columns)}\n"
        for i, row in enumerate(records[:100]):
            out += f"\nRow {i + 1}: " + " | ".join(
                f"{c}={str(row[c])[:60]}" for c in columns)
        if len(records) > 100:
            out += f"\n... [{len(records) - 100} more rows]"
        return out
    except Exception as e:
        return f"PostgreSQL error: {e}"


async def _query_mysql(sql: str, database: str, host: str,
                       port: int, user: str, password: str) -> str:
    """Query a MySQL database."""
    try:
        import pymysql
    except ImportError:
        return "MySQL requires pymysql"

    if not database:
        return "MySQL requires a database name"

    loop = asyncio.get_event_loop()

    def _run():
        conn = pymysql.connect(
            host=host, port=port or 3306,
            user=user or "root", password=password or "",
            database=database,
        )
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            conn.close()
            return "Query returned no results."
        columns = [d[0] for d in cur.description]
        out = f"**{len(rows)} row(s)**\nColumns: {', '.join(columns)}\n"
        for i, row in enumerate(rows[:100]):
            out += f"\nRow {i + 1}: " + " | ".join(
                f"{columns[j]}={str(row[j])[:60]}" for j in range(len(columns)))
        if len(rows) > 100:
            out += f"\n... [{len(rows) - 100} more rows]"
        conn.close()
        return out

    try:
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        return f"MySQL error: {e}"


async def list_tables(db_type: str = "sqlite", database: str = "",
                      host: str = "localhost", port: int = 5432,
                      user: str = "", password: str = "") -> str:
    """List all tables in a database."""
    if db_type == "sqlite":
        return await query_database(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            "sqlite", database)
    elif db_type in ("postgres", "postgresql"):
        return await query_database(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name",
            db_type, database, host, port, user, password)
    elif db_type == "mysql":
        return await query_database(
            "SHOW TABLES", db_type, database, host, port, user, password)
    return "Unsupported database type"
