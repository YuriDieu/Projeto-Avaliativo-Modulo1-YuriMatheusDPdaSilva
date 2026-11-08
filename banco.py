"""Conexão e funções utilitárias do MySQL (conectar, executar, inserir_em_lote)."""
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

import config


def conectar(stream=False):
    """Abre uma conexão com o banco definido no .env.

    stream=True usa um cursor "sem buffer" (SSCursor): as linhas vêm do
    servidor aos poucos, ideal para ler tabelas grandes sem lotar a memória.
    """
    cursor = pymysql.cursors.SSCursor if stream else pymysql.cursors.Cursor
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=cursor,
    )


def executar(conn, sql, params=None):
    """Executa um comando SQL (DDL/DML) e confirma (commit)."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


def inserir_em_lote(conn, sql, linhas, tamanho_lote=5000):
    """Insere uma lista de tuplas em lotes usando executemany.

    Inserir linha a linha seria muito lento; em lotes é muito mais rápido.
    Retorna quantas linhas foram inseridas.
    """
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(linhas), tamanho_lote):
            lote = linhas[i:i + tamanho_lote]
            cur.executemany(sql, lote)
            total += len(lote)
    conn.commit()
    return total


def get_engine():
    """Engine do SQLAlchemy (usada pelo pandas no notebook de análise)."""
    url = URL.create(
        "mysql+pymysql",
        username=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url)
