-- =============================================================================
-- FASE 0 - Banco e tabelas (MySQL 8+)
-- Cria o database e as 8 tabelas: 4 RAW (tudo VARCHAR, sem constraints)
-- e 4 SILVER (tipadas, com PK, FK e 2 constraints extras por tabela).
-- Execute:  mysql -u root -p < 0_criar_banco.sql
-- =============================================================================

CREATE DATABASE IF NOT EXISTS viagens_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE viagens_db;

-- Reexecutar o script deve ser seguro: removemos as tabelas na ordem inversa
-- das dependências (filhas primeiro, pai "silver_viagem" por último).
DROP TABLE IF EXISTS silver_trecho;
DROP TABLE IF EXISTS silver_passagem;
DROP TABLE IF EXISTS silver_pagamento;
DROP TABLE IF EXISTS silver_viagem;
DROP TABLE IF EXISTS raw_trecho;
DROP TABLE IF EXISTS raw_passagem;
DROP TABLE IF EXISTS raw_pagamento;
DROP TABLE IF EXISTS raw_viagem;

-- =============================================================================
-- CAMADA RAW: cópia fiel do CSV. Tudo VARCHAR, sem PK/FK/constraints.
-- A ORDEM das colunas é a MESMA do CSV: o script 1_extrair.py carrega por posição.
-- Inclui colunas que a Silver não usa (cpf_viajante, funcao, dados de volta...).
-- =============================================================================

CREATE TABLE raw_viagem (
    id_viagem               VARCHAR(255),
    num_proposta            VARCHAR(255),
    situacao                VARCHAR(255),
    viagem_urgente          VARCHAR(255),
    justificativa_urgencia  VARCHAR(4000),
    cod_orgao_superior      VARCHAR(255),
    nome_orgao_superior     VARCHAR(255),
    cod_orgao_solicitante   VARCHAR(255),
    nome_orgao_solicitante  VARCHAR(255),
    cpf_viajante            VARCHAR(255),
    nome_viajante           VARCHAR(255),
    cargo                   VARCHAR(255),
    funcao                  VARCHAR(255),
    descricao_funcao        VARCHAR(255),
    data_inicio             VARCHAR(255),
    data_fim                VARCHAR(255),
    destinos                VARCHAR(4000),
    motivo                  VARCHAR(4000),
    valor_diarias           VARCHAR(255),
    valor_passagens         VARCHAR(255),
    valor_devolucao         VARCHAR(255),
    valor_outros_gastos     VARCHAR(255)
);

CREATE TABLE raw_pagamento (
    id_viagem           VARCHAR(255),
    num_proposta        VARCHAR(255),
    cod_orgao_superior  VARCHAR(255),
    nome_orgao_superior VARCHAR(255),
    cod_orgao_pagador   VARCHAR(255),
    nome_orgao_pagador  VARCHAR(255),
    cod_ug_pagadora     VARCHAR(255),
    nome_ug_pagadora    VARCHAR(255),
    tipo_pagamento      VARCHAR(255),
    valor               VARCHAR(255)
);

CREATE TABLE raw_passagem (
    id_viagem           VARCHAR(255),
    num_proposta        VARCHAR(255),
    meio_transporte     VARCHAR(255),
    pais_origem_ida     VARCHAR(255),
    uf_origem_ida       VARCHAR(255),
    cidade_origem_ida   VARCHAR(255),
    pais_destino_ida    VARCHAR(255),
    uf_destino_ida      VARCHAR(255),
    cidade_destino_ida  VARCHAR(255),
    pais_origem_volta   VARCHAR(255),
    uf_origem_volta     VARCHAR(255),
    cidade_origem_volta VARCHAR(255),
    pais_destino_volta  VARCHAR(255),
    uf_destino_volta    VARCHAR(255),
    cidade_destino_volta VARCHAR(255),
    valor_passagem      VARCHAR(255),
    taxa_servico        VARCHAR(255),
    data_emissao        VARCHAR(255),
    hora_emissao        VARCHAR(255)
);

CREATE TABLE raw_trecho (
    id_viagem        VARCHAR(255),
    num_proposta     VARCHAR(255),
    sequencia_trecho VARCHAR(255),
    origem_data      VARCHAR(255),
    origem_pais      VARCHAR(255),
    origem_uf        VARCHAR(255),
    origem_cidade    VARCHAR(255),
    destino_data     VARCHAR(255),
    destino_pais     VARCHAR(255),
    destino_uf       VARCHAR(255),
    destino_cidade   VARCHAR(255),
    meio_transporte  VARCHAR(255),
    numero_diarias   VARCHAR(255),
    missao           VARCHAR(255)
);

-- =============================================================================
-- CAMADA SILVER: dados limpos e tipados, com integridade referencial.
-- silver_viagem é a tabela PAI; as outras três apontam para ela via FK.
-- =============================================================================

CREATE TABLE silver_viagem (
    id_viagem           VARCHAR(20)   NOT NULL,
    num_proposta        VARCHAR(20),
    situacao            VARCHAR(50),
    viagem_urgente      VARCHAR(5),
    cod_orgao_superior  VARCHAR(20),
    nome_orgao_superior VARCHAR(255)  NOT NULL,          -- constraint extra 1
    nome_viajante       VARCHAR(255),
    cargo               VARCHAR(255),
    data_inicio         DATE,
    data_fim            DATE,
    destinos            VARCHAR(4000),
    motivo              VARCHAR(4000),
    valor_diarias       DECIMAL(10,2),
    valor_passagens     DECIMAL(10,2),
    valor_devolucao     DECIMAL(10,2),
    valor_outros_gastos DECIMAL(10,2),
    valor_total         DECIMAL(12,2),                   -- calculado
    duracao_dias        INT,                             -- calculado
    PRIMARY KEY (id_viagem),
    CONSTRAINT chk_viagem_diarias CHECK (valor_diarias >= 0)   -- constraint extra 2
);

CREATE TABLE silver_pagamento (
    id_pagamento       INT          NOT NULL AUTO_INCREMENT,
    id_viagem          VARCHAR(20)  NOT NULL,
    num_proposta       VARCHAR(20),
    nome_orgao_pagador VARCHAR(255),
    nome_ug_pagadora   VARCHAR(255),
    tipo_pagamento     VARCHAR(50)  NOT NULL,            -- constraint extra 1
    valor              DECIMAL(10,2),
    PRIMARY KEY (id_pagamento),
    CONSTRAINT fk_pagamento_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_pagamento_valor CHECK (valor >= 0)    -- constraint extra 2
);

CREATE TABLE silver_passagem (
    id_passagem        INT          NOT NULL AUTO_INCREMENT,
    id_viagem          VARCHAR(20)  NOT NULL,
    meio_transporte    VARCHAR(50),
    pais_origem_ida    VARCHAR(60),
    uf_origem_ida      VARCHAR(40),
    cidade_origem_ida  VARCHAR(80),
    pais_destino_ida   VARCHAR(60),
    uf_destino_ida     VARCHAR(40),
    cidade_destino_ida VARCHAR(80),
    valor_passagem     DECIMAL(10,2),
    taxa_servico       DECIMAL(10,2),
    data_emissao       DATE,
    PRIMARY KEY (id_passagem),
    CONSTRAINT fk_passagem_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_passagem_valor CHECK (valor_passagem >= 0),  -- constraint extra 1
    CONSTRAINT chk_passagem_taxa  CHECK (taxa_servico >= 0)     -- constraint extra 2
);

CREATE TABLE silver_trecho (
    id_trecho        INT          NOT NULL AUTO_INCREMENT,
    id_viagem        VARCHAR(20)  NOT NULL,
    sequencia_trecho INT,
    origem_data      DATE,
    origem_uf        VARCHAR(40),
    origem_cidade    VARCHAR(80),
    destino_data     DATE,
    destino_uf       VARCHAR(40),
    destino_cidade   VARCHAR(80),
    meio_transporte  VARCHAR(50),
    numero_diarias   DECIMAL(10,2),
    PRIMARY KEY (id_trecho),
    CONSTRAINT fk_trecho_viagem FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_trecho_diarias CHECK (numero_diarias >= 0),            -- constraint extra 1
    CONSTRAINT uq_trecho_viagem_seq UNIQUE (id_viagem, sequencia_trecho)  -- constraint extra 2
);
