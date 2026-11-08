"""FASE 1 - Extração e camada RAW.

O que este script faz:
  1. Baixa o .zip do Google Drive (sem intervenção manual).
  2. Descompacta os 4 CSVs.
  3. Lê cada CSV em blocos (chunks) e carrega nas tabelas raw_* SEM alterar
     o conteúdo (tudo texto, igual ao arquivo).

Propriedades exigidas no enunciado:
  - Idempotente: TRUNCATE antes de carregar => rodar 2x não duplica linhas.
  - Resiliente: try/except por tabela; um erro é registrado e não esconde os demais.
"""
import logging
import sys
import zipfile

import gdown
import pandas as pd

import config
from banco import conectar, executar, inserir_em_lote

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("extrair")


def baixar_zip():
    """Baixa o zip do Drive (pula se já existir em data/)."""
    config.DATA_DIR.mkdir(exist_ok=True)
    if config.ZIP_PATH.exists():
        log.info("Zip já existe, pulando download: %s", config.ZIP_PATH)
        return
    if config.DRIVE_FILE_ID.startswith("COLE_AQUI"):
        raise ValueError("Defina DRIVE_FILE_ID no config.py antes de executar.")
    url = f"https://drive.google.com/uc?id={config.DRIVE_FILE_ID}"
    log.info("Baixando zip do Google Drive...")
    gdown.download(url, str(config.ZIP_PATH), quiet=False)
    if not config.ZIP_PATH.exists():
        raise RuntimeError("Download falhou: o arquivo zip não foi criado.")


def extrair_zip():
    """Descompacta o zip e devolve {nome_do_csv_em_minusculo: caminho}."""
    with zipfile.ZipFile(config.ZIP_PATH) as zf:
        zf.extractall(config.DATA_DIR)
    return {p.name.lower(): p for p in config.DATA_DIR.rglob("*.csv")}


def colunas_da_tabela(conn, tabela):
    """Lê do próprio banco os nomes das colunas (fonte única: o .sql)."""
    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM {tabela}")
        return [linha[0] for linha in cur.fetchall()]


def carregar_tabela(conn, tabela, caminho_csv):
    """TRUNCATE + carga em blocos de um CSV para uma tabela raw. Retorna nº de linhas."""
    colunas = colunas_da_tabela(conn, tabela)

    # dtype=str + keep_default_na=False => nada é convertido: o texto fica idêntico.
    leitor = pd.read_csv(
        caminho_csv,
        sep=config.CSV_SEP,
        encoding=config.CSV_ENCODING,
        dtype=str,
        keep_default_na=False,
        chunksize=config.CHUNK_SIZE,
    )

    executar(conn, f"TRUNCATE TABLE {tabela}")  # idempotência
    sql = (f"INSERT INTO {tabela} ({', '.join(colunas)}) "
           f"VALUES ({', '.join(['%s'] * len(colunas))})")

    total = 0
    for i, bloco in enumerate(leitor, start=1):
        if bloco.shape[1] != len(colunas):
            raise ValueError(
                f"{caminho_csv.name} tem {bloco.shape[1]} colunas, mas {tabela} "
                f"tem {len(colunas)}. Confira a ordem/quantidade no 0_criar_banco.sql."
            )
        linhas = [tuple(linha) for linha in bloco.itertuples(index=False, name=None)]
        total += inserir_em_lote(conn, sql, linhas)
        log.info("%s: bloco %d carregado (%d linhas acumuladas)", tabela, i, total)
    return total


def main():
    try:
        baixar_zip()
        csvs = extrair_zip()
    except Exception:
        log.exception("Falha no download/extração")
        sys.exit(1)

    falhas = 0
    conn = conectar()
    try:
        for tabela, nome_csv in config.ARQUIVOS_CSV.items():
            try:
                caminho = csvs.get(nome_csv.lower())
                if caminho is None:
                    raise FileNotFoundError(f"{nome_csv} não encontrado no zip")
                n = carregar_tabela(conn, tabela, caminho)
                log.info("OK %s: %d linhas", tabela, n)
            except Exception:
                conn.rollback()
                falhas += 1
                log.exception("Erro ao carregar %s", tabela)
    finally:
        conn.close()

    if falhas:
        log.error("%d tabela(s) com erro.", falhas)
        sys.exit(1)
    log.info("Camada RAW concluída.")


if __name__ == "__main__":
    main()
