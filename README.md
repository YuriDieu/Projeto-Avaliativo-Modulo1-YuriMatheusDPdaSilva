# Pipeline de Dados - Viagens a Serviço (Portal da Transparência)

Pipeline ETL completo em **Python + MySQL** seguindo a **Arquitetura Medallion** (Raw -> Silver -> Gold),
que transforma os dados brutos de viagens a serviço do Governo Federal (1º semestre de 2025) em
métricas e gráficos confiáveis.

## Problema que resolve
Os dados abertos chegam brutos: datas `DD/MM/AAAA`, decimais com vírgula, textos em `latin-1`,
duplicidades e registros sem vínculo. Este projeto automatiza o download, preserva o original,
limpa/tipa os dados e responde 7 perguntas de negócio sobre gastos públicos com viagens.

## Arquitetura

```
Google Drive (.zip)
      |  1_extrair.py (download + carga em blocos, TRUNCATE + INSERT)
      v
 RAW    raw_viagem | raw_pagamento | raw_passagem | raw_trecho      (tudo VARCHAR, cópia fiel)
      |  2_transformar.py (tipagem, limpeza, colunas calculadas, integridade)
      v
 SILVER silver_viagem (PAI) <-- silver_pagamento | silver_passagem | silver_trecho  (PK, FK, CHECK...)
      |  3_analise.ipynb (JOIN + GROUP BY)
      v
 GOLD   gold_* (tabelas) + vw_gold_* (views) + gráficos
```

## Tecnologias
Python 3.10+, MySQL 8+, pandas, PyMySQL, SQLAlchemy, gdown, matplotlib, python-dotenv, Jupyter.

## Estrutura do repositório

| Arquivo | Função |
|---|---|
| `0_criar_banco.sql` | Cria o database e as 8 tabelas (4 Raw + 4 Silver com PK/FK/constraints) |
| `1_extrair.py` | Download do zip + leitura dos CSVs em blocos + carga na Raw |
| `2_transformar.py` | Raw -> Silver (conversões, `valor_total`, `duracao_dias`, integridade) |
| `3_analise.ipynb` | Perguntas de negócio, camada Gold (tabela + view) e gráficos |
| `config.py` / `banco.py` | Parâmetros e utilitários de conexão |
| `.env.example` | Modelo de credenciais (copie para `.env`) |
| `requirements.txt` / `.gitignore` | Dependências / arquivos ignorados |

## Como executar
```bash
# 1. Ambiente
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Credenciais
cp .env.example .env        # edite com usuário/senha do seu MySQL
# edite config.py e cole o DRIVE_FILE_ID

# 3. Pipeline
mysql -u root -p < 0_criar_banco.sql
python 1_extrair.py
python 2_transformar.py
jupyter notebook 3_analise.ipynb      # Run All
```
Todos os scripts podem ser reexecutados sem duplicar dados (idempotentes).

## Decisões de modelagem e tratamento
- **Raw**: `VARCHAR` em tudo, nada é alterado (rastreabilidade/auditoria). Carga por posição de coluna.
- **Silver**: `valor_total = diárias + passagens + outros gastos - devolução`; `duracao_dias = data_fim - data_inicio + 1`.
- **Valores inválidos**: texto que não converte, vazio ou "Sem informação" vira `NULL` (nunca um valor inventado). Valores negativos nas colunas com `CHECK >= 0` viram `NULL`.
- **Integridade**: `silver_viagem` é carregada primeiro; linhas "órfãs" das tabelas filhas são descartadas e contadas no log.
- **Duplicidades**: mantém a 1ª ocorrência de `id_viagem` e de `(id_viagem, sequencia_trecho)`.

## Perguntas de negócio
| # | Pergunta | Camada |
|---|---|---|
| A1 | 5 órgãos com maior custo total | Silver |
| A2 | 3 destinos com maior custo médio por viagem | Silver |
| A3 | Viagem de maior duração e seu custo | Silver |
| B1 | Tipo de pagamento com maior valor médio | Gold |
| B2 | Meio de transporte mais usado nos trechos | Gold |
| B3 | UF de destino em mais trechos | Gold |
| B4 | Órgão que pagou mais no total | Gold |

## Conclusões e insights
*(Preencher após executar o notebook com os seus resultados.)*

## Melhorias possíveis
- Orquestrar com Airflow/cron e adicionar testes automatizados (pytest) das funções de conversão.
- Separar `destinos` (texto livre) em uma tabela dimensão própria.
- Carga incremental por mês em vez de recarga total.
- Dashboard (Streamlit/Power BI) sobre as views Gold.
