"""
CData Connect Cloud — ATDW_PlatformDB connection helper.

Requires pyodbc and the {SQL Server} ODBC driver (ships with Windows).
Credentials are read from .env (CDATA_HOST, CDATA_PORT, CDATA_USER, CDATA_PAT, CDATA_DATABASE).
"""
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_cdata_conn(timeout: int = 30) -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={os.environ['CDATA_HOST']},{os.environ['CDATA_PORT']};"
        f"DATABASE={os.environ['CDATA_DATABASE']};"
        f"UID={os.environ['CDATA_USER']};"
        f"PWD={os.environ['CDATA_PAT']};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=timeout)


def cdata_rows_as_dicts(cursor: pyodbc.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


if __name__ == "__main__":
    conn = get_cdata_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM listing")
    print(f"listing rows: {cur.fetchone()[0]:,}")
    conn.close()
