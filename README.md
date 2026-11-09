# Pipeline de Dados - Viagens a Serviço (Portal da Transparência)

Pipeline ETL completo em **Python + MySQL**, seguindo a **Arquitetura Medallion** (Raw → Silver → Gold). Ele transforma os dados brutos de viagens a serviço do Governo Federal (1º semestre de 2025) em métricas e gráficos confiáveis para apoiar a tomada de decisão.

## Problema que resolve

Os dados abertos de viagens a serviço chegam brutos: datas em `DD/MM/AAAA`, decimais com vírgula, textos em `latin-1`, registros duplicados e linhas sem vínculo com a viagem de origem. Este projeto:

1. baixa os dados direto da fonte, sem intervenção manual;
2. preserva o dado original (camada Raw), para rastreabilidade e auditoria;
3. limpa, tipa e relaciona as tabelas (camada Silver);
4. responde perguntas de negócio sobre os gastos públicos com viagens (camada Gold).

## Arquitetura

```
Google Drive (.zip)
      │  1_extrair.py   (download + carga em blocos, TRUNCATE + INSERT)
      ▼
 RAW     raw_viagem | raw_pagamento | raw_passagem | raw_trecho
         (tudo VARCHAR, cópia fiel do CSV)
      │  2_transformar.py   (tipagem, limpeza, colunas calculadas, integridade)
      ▼
 SILVER  silver_viagem (PAI) ◄── silver_pagamento | silver_passagem | silver_trecho
         (DECIMAL, DATE, PK, FK, CHECK, NOT NULL, UNIQUE)
      │  3_analise.ipynb   (JOIN + GROUP BY)
      ▼
 GOLD    gold_* (tabelas) + vw_gold_* (views) + gráficos
```

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python 3.10+ | Scripts do pipeline |
| MySQL 8+ | Banco de dados (Raw, Silver e Gold) |
| pandas | Leitura dos CSVs em blocos e consultas no notebook |
| PyMySQL | Conexão com o MySQL |
| SQLAlchemy | Engine usada pelo pandas e criação da Gold |
| gdown | Download automático do arquivo no Google Drive |
| matplotlib | Gráficos |
| python-dotenv | Leitura das credenciais do `.env` |
| Jupyter | Notebook de análise |

## Estrutura do repositório

| Arquivo | Função |
|---|---|
| `0_criar_banco.sql` | Cria o database e as 8 tabelas (4 Raw + 4 Silver com PK, FK e constraints) |
| `1_extrair.py` | Download do zip, leitura dos CSVs em blocos e carga na Raw |
| `2_transformar.py` | Raw → Silver (conversões, `valor_total`, `duracao_dias`, integridade) |
| `3_analise.ipynb` | Perguntas de negócio, camada Gold (tabela + view) e gráficos |
| `config.py` / `banco.py` | Parâmetros e utilitários de conexão |
| `.env.example` | Modelo de credenciais (copie para `.env`) |
| `requirements.txt` / `.gitignore` | Dependências e arquivos ignorados |

## Como executar

**Pré-requisitos:** Python 3.10+, MySQL 8.0.16+ (o `CHECK` só é aplicado a partir dessa versão) e Git.

```bash
# 1. Ambiente virtual e dependências
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

# 2. Credenciais
copy .env.example .env            # Linux/Mac: cp .env.example .env
# edite o .env com usuário e senha do seu MySQL
# edite o config.py e informe o DRIVE_FILE_ID (apenas o ID, não o link completo)

# 3. Pipeline (nesta ordem)
mysql -u root -p < 0_criar_banco.sql     # ou execute o arquivo no MySQL Workbench
python 1_extrair.py
python 2_transformar.py
jupyter notebook 3_analise.ipynb         # Run All
```

Todos os scripts podem ser reexecutados sem duplicar dados (são idempotentes).

## Decisões de modelagem e tratamento

- **Raw:** todas as colunas `VARCHAR`, sem constraints; o conteúdo do CSV não é alterado. A carga é feita por posição de coluna. Em `raw_viagem`, `justificativa_urgencia` tem 2000 caracteres, porque três colunas de 4000 ultrapassam o limite de 65.535 bytes por linha do MySQL (erro 1118).
- **Silver:** PK em todas as tabelas, FK de `silver_pagamento`, `silver_passagem` e `silver_trecho` para `silver_viagem`, e duas constraints extras por tabela (`NOT NULL`, `CHECK`, `UNIQUE`).
- **Colunas calculadas:**
  - `valor_total = valor_diarias + valor_passagens + valor_outros_gastos − valor_devolucao`
  - `duracao_dias = data_fim − data_inicio + 1` (viagem de um dia = 1 dia)
- **Valores inválidos:** texto que não converte, campo vazio ou "Sem informação" vira `NULL`, nunca um valor inventado. Valores negativos nas colunas com `CHECK >= 0` também viram `NULL`.
- **Integridade referencial:** `silver_viagem` é carregada primeiro. Linhas "órfãs" (sem viagem correspondente) das tabelas filhas são descartadas e contadas no log.
- **Duplicidades:** mantém a primeira ocorrência de `id_viagem` e de `(id_viagem, sequencia_trecho)`.
- **Gold:** quatro agregações com `JOIN` + `GROUP BY`, criadas como tabela (`gold_*`, materializada) e como view (`vw_gold_*`, sempre atualizada).
- **Destinos com poucas viagens:** na pergunta do custo médio por destino, `HAVING COUNT(*) >= 5` evita que um caso isolado seja apontado como "o destino mais caro".

## Perguntas de negócio

| # | Pergunta | Camada |
|---|---|---|
| A1 | Os 5 órgãos com maior custo total | Silver |
| A2 | Os 3 destinos com maior custo médio por viagem | Silver |
| A3 | A viagem de maior duração e seu custo total | Silver |
| B1 | O tipo de pagamento com maior valor médio | Gold |
| B2 | O meio de transporte mais usado nos trechos | Gold |
| B3 | A UF de destino que aparece em mais trechos | Gold |
| B4 | O órgão que pagou mais no total | Gold |

## Conclusões e insights

Resultados obtidos no 1º semestre de 2025.

**Órgãos com maior custo total.** Os cinco órgãos que mais concentram os gastos com viagens são, nesta ordem de grandeza: Ministério da Justiça e Segurança Pública, Ministério da Defesa, Ministério da Educação, Ministério do Meio Ambiente e Mudança do Clima e Ministério da Previdência Social. Os custos se concentram em órgãos com grande capilaridade territorial e atividades de campo, como fiscalização, segurança, educação e atendimento ao público, o que sugere que a viagem é parte da operação desses órgãos e não um gasto eventual.

**Viagem de maior duração.** A viagem mais longa do período é a de código **20699856**, do Ministério da Previdência Social. Como a duração é calculada como `data_fim − data_inicio + 1`, ela representa dias corridos. Viagens muito longas fogem do padrão e merecem verificação do motivo registrado.

**Meio de transporte mais usado.** O **veículo oficial** é o meio mais frequente nos trechos. Isso indica uma presença forte de deslocamentos por terra, de curta e média distância, dentro dos estados ou entre estados vizinhos.

**UF de destino mais frequente.** **São Paulo** é a UF que aparece em mais trechos. Isso é coerente com o peso econômico e populacional do estado e com a grande rede de aeroportos e de órgãos federais ali presentes.

**Órgão que mais pagou.** O maior volume pago saiu do **Fundo Nacional de Segurança Pública**. Quem paga nem sempre é quem solicita a viagem: o órgão pagador, em `silver_pagamento`, pode ser diferente do órgão superior da viagem. Isso explica a presença de um fundo na liderança dos pagamentos, ligado ao peso do Ministério da Justiça e Segurança Pública nos custos.

**Limitações da análise**
- O período cobre apenas seis meses de 2025, então não há como avaliar sazonalidade anual.
- `destinos` é um campo de texto livre, em que a mesma localidade pode aparecer escrita de formas diferentes.
- Valores inválidos ou negativos viraram `NULL` e não entram nas somas, o que pode subestimar alguns custos.
- A análise descreve onde está o gasto, mas não avalia se ele foi necessário ou eficiente.

## Melhorias possíveis

- Orquestrar o pipeline com Airflow ou cron e adicionar testes automatizados (pytest) das funções de conversão.
- Separar `destinos` (texto livre) em uma tabela dimensão própria, com nomes padronizados.
- Carga incremental por mês, em vez de recarga total.
- Dashboard (Streamlit ou Power BI) sobre as views Gold.
- Validação de qualidade dos dados, com relatório de quantas linhas foram descartadas e por quê.

## Solução de problemas

| Problema | Solução |
|---|---|
| `Row size too large` ao criar `raw_viagem` | Usar `VARCHAR(2000)` em `justificativa_urgencia` (já corrigido no script) |
| Falha no download com `gdown` | Informar só o **ID** do arquivo no `DRIVE_FILE_ID`, ou baixar o zip manualmente para `data/viagens_2025.zip` |
| `Access denied for user 'root'` | Conferir `DB_PASSWORD` no `.env` |
| `DLL load failed ... Controle de Aplicativo` (SQLAlchemy) | Reinstalar em Python puro: `pip uninstall -y sqlalchemy`, depois `$env:DISABLE_SQLALCHEMY_CEXT="1"` e `pip install --no-binary sqlalchemy sqlalchemy` |

## Autor

Yuri Matheus D. P. da Silva — Projeto Avaliativo, Módulo 1 (Análise de Dados com Python).