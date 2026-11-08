"""Parâmetros do projeto + leitura das credenciais do arquivo .env.

Observação: este arquivo e o banco.py foram fornecidos "prontos" no enunciado.
Esta é uma versão equivalente, caso você ainda não os tenha. Se já tem os
do professor, mantenha os seus e só confira os nomes usados nos outros scripts.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # lê o .env e coloca as variáveis no ambiente

# ---- Caminhos -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ZIP_PATH = DATA_DIR / "viagens_2025.zip"

# ---- Fonte dos dados ------------------------------------------------------
# Cole aqui o ID do arquivo no Google Drive (trecho entre /d/ e /view na URL).
DRIVE_FILE_ID = "1pQjKacyHdIsyteknQbwKGM5_4hL5V4RV"

# Tabela Raw -> nome do CSV dentro do .zip
ARQUIVOS_CSV = {
    "raw_viagem": "2025_Viagem.csv",
    "raw_pagamento": "2025_Pagamento.csv",
    "raw_passagem": "2025_Passagem.csv",
    "raw_trecho": "2025_Trecho.csv",
}

# ---- Formato dos CSVs (informado no enunciado) ----------------------------
CSV_SEP = ";"
CSV_ENCODING = "latin-1"
CHUNK_SIZE = 50_000  # linhas lidas por bloco (evita estourar a memória)

# ---- Banco de dados (vem do .env) -----------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "viagens_db")
