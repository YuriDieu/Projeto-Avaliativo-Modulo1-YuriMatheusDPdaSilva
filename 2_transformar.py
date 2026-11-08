"""FASE 2 - Transformação: camada RAW -> camada SILVER.

O que este script faz:
  - Lê cada tabela raw_* (em streaming, sem carregar tudo na memória).
  - Converte tipos: texto -> DECIMAL (vírgula decimal) e texto -> DATE (DD/MM/AAAA).
  - Calcula valor_total e duracao_dias em silver_viagem.
  - Garante integridade referencial: só entram em pagamento/passagem/trecho
    linhas cujo id_viagem existe em silver_viagem (a ordem de carga importa!).
  - Remove duplicidades (mesmo id_viagem; mesmo par id_viagem+sequencia_trecho).
  - Idempotente: esvazia as tabelas silver antes de carregar.
"""
import logging
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation

from banco import conectar, executar, inserir_em_lote

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("transformar")

TAMANHO_LOTE = 5000
VALORES_VAZIOS = {"", "sem informação", "sem informacao", "nan", "null"}


# ----------------------------------------------------------------------------
# Funções de conversão (requisito 5.6): cada uma devolve None se não der
# para converter, e o NULL é gravado no banco em vez de um valor inventado.
# ----------------------------------------------------------------------------
def texto(valor, tamanho_max=None):
    """Limpa espaços; vazio vira None; corta ao tamanho da coluna."""
    if valor is None:
        return None
    v = str(valor).strip()
    if v.lower() in VALORES_VAZIOS:
        return None
    return v[:tamanho_max] if tamanho_max else v


def converter_decimal(valor):
    """'1272,97' -> Decimal('1272.97'). Aceita '1.272,97'. Inválido -> None."""
    if valor is None:
        return None
    v = str(valor).strip()
    if v.lower() in VALORES_VAZIOS:
        return None
    if "," in v:
        v = v.replace(".", "").replace(",", ".")  # remove milhar, troca decimal
    try:
        return Decimal(v).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def converter_data(valor):
    """'25/03/2025' -> date(2025, 3, 25). Inválido -> None."""
    if valor is None:
        return None
    v = str(valor).strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d/%m/%Y").date()
    except ValueError:
        return None


def converter_inteiro(valor):
    """'3' -> 3. Inválido -> None."""
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return None


def nao_negativo(decimal_):
    """Os CHECK (>= 0) rejeitam negativos; aqui negativo vira None (NULL passa no CHECK)."""
    if decimal_ is not None and decimal_ < 0:
        return None
    return decimal_


# ----------------------------------------------------------------------------
# Motor genérico: lê raw em streaming, transforma linha a linha, insere em lotes
# ----------------------------------------------------------------------------
def processar(conn_leitura, conn_escrita, select_sql, transformar, insert_sql, nome):
    """Aplica `transformar` a cada linha. Se devolver None, a linha é descartada."""
    lidas = gravadas = 0
    lote = []
    with conn_leitura.cursor() as cur:
        cur.execute(select_sql)
        while True:
            linhas = cur.fetchmany(TAMANHO_LOTE)
            if not linhas:
                break
            for linha in linhas:
                lidas += 1
                nova = transformar(linha)
                if nova is not None:
                    lote.append(nova)
            if lote:
                gravadas += inserir_em_lote(conn_escrita, insert_sql, lote, TAMANHO_LOTE)
                lote = []
    log.info("%s: %d lidas, %d gravadas, %d descartadas",
             nome, lidas, gravadas, lidas - gravadas)
    return gravadas


# ----------------------------------------------------------------------------
# Transformações de cada tabela
# ----------------------------------------------------------------------------
def transformar_viagem_factory():
    vistos = set()

    def transformar(l):
        (id_viagem, num_proposta, situacao, urgente, cod_org, nome_org, nome_viajante,
         cargo, d_ini, d_fim, destinos, motivo, v_diarias, v_pass, v_dev, v_outros) = l
        id_viagem = texto(id_viagem, 20)
        if id_viagem is None or id_viagem in vistos:  # sem chave ou duplicada
            return None
        vistos.add(id_viagem)

        inicio, fim = converter_data(d_ini), converter_data(d_fim)
        diarias = nao_negativo(converter_decimal(v_diarias))
        passagens = converter_decimal(v_pass)
        devolucao = converter_decimal(v_dev)
        outros = converter_decimal(v_outros)

        # valor_total = diárias + passagens + outros gastos - devolução
        zero = Decimal("0")
        total = (diarias or zero) + (passagens or zero) + (outros or zero) - (devolucao or zero)

        # duracao_dias = dias corridos, contando início e fim (viagem de 1 dia = 1)
        duracao = (fim - inicio).days + 1 if inicio and fim and fim >= inicio else None

        return (id_viagem, texto(num_proposta, 20), texto(situacao, 50), texto(urgente, 5),
                texto(cod_org, 20), texto(nome_org, 255) or "Não informado",
                texto(nome_viajante, 255), texto(cargo, 255), inicio, fim,
                texto(destinos, 4000), texto(motivo, 4000),
                diarias, passagens, devolucao, outros, total, duracao)

    return transformar


def ids_validos(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id_viagem FROM silver_viagem")
        return {r[0] for r in cur.fetchall()}


def main():
    conn_r = conectar(stream=True)   # leitura em streaming
    conn_w = conectar()              # escrita
    try:
        # Idempotência: esvazia tudo (FKs desligadas só durante o TRUNCATE)
        executar(conn_w, "SET FOREIGN_KEY_CHECKS = 0")
        for t in ("silver_trecho", "silver_passagem", "silver_pagamento", "silver_viagem"):
            executar(conn_w, f"TRUNCATE TABLE {t}")
        executar(conn_w, "SET FOREIGN_KEY_CHECKS = 1")

        # 1) VIAGEM primeiro (tabela pai)
        processar(
            conn_r, conn_w,
            "SELECT id_viagem, num_proposta, situacao, viagem_urgente, cod_orgao_superior, "
            "nome_orgao_superior, nome_viajante, cargo, data_inicio, data_fim, destinos, "
            "motivo, valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos "
            "FROM raw_viagem",
            transformar_viagem_factory(),
            "INSERT INTO silver_viagem (id_viagem, num_proposta, situacao, viagem_urgente, "
            "cod_orgao_superior, nome_orgao_superior, nome_viajante, cargo, data_inicio, "
            "data_fim, destinos, motivo, valor_diarias, valor_passagens, valor_devolucao, "
            "valor_outros_gastos, valor_total, duracao_dias) "
            "VALUES (" + ", ".join(["%s"] * 18) + ")",
            "silver_viagem",
        )
        validos = ids_validos(conn_w)

        # 2) PAGAMENTO (filhas só depois do pai: respeita a FK)
        def t_pagamento(l):
            id_v, prop, org, ug, tipo, valor = l
            id_v = texto(id_v, 20)
            if id_v not in validos:  # órfão -> descarta
                return None
            return (id_v, texto(prop, 20), texto(org, 255), texto(ug, 255),
                    texto(tipo, 50) or "Não informado", nao_negativo(converter_decimal(valor)))

        processar(
            conn_r, conn_w,
            "SELECT id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora, "
            "tipo_pagamento, valor FROM raw_pagamento",
            t_pagamento,
            "INSERT INTO silver_pagamento (id_viagem, num_proposta, nome_orgao_pagador, "
            "nome_ug_pagadora, tipo_pagamento, valor) VALUES (%s, %s, %s, %s, %s, %s)",
            "silver_pagamento",
        )

        # 3) PASSAGEM
        def t_passagem(l):
            (id_v, meio, p_o, uf_o, c_o, p_d, uf_d, c_d, v_pass, taxa, d_emis) = l
            id_v = texto(id_v, 20)
            if id_v not in validos:
                return None
            return (id_v, texto(meio, 50), texto(p_o, 60), texto(uf_o, 40), texto(c_o, 80),
                    texto(p_d, 60), texto(uf_d, 40), texto(c_d, 80),
                    nao_negativo(converter_decimal(v_pass)),
                    nao_negativo(converter_decimal(taxa)), converter_data(d_emis))

        processar(
            conn_r, conn_w,
            "SELECT id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida, "
            "cidade_origem_ida, pais_destino_ida, uf_destino_ida, cidade_destino_ida, "
            "valor_passagem, taxa_servico, data_emissao FROM raw_passagem",
            t_passagem,
            "INSERT INTO silver_passagem (id_viagem, meio_transporte, pais_origem_ida, "
            "uf_origem_ida, cidade_origem_ida, pais_destino_ida, uf_destino_ida, "
            "cidade_destino_ida, valor_passagem, taxa_servico, data_emissao) "
            "VALUES (" + ", ".join(["%s"] * 11) + ")",
            "silver_passagem",
        )

        # 4) TRECHO (também remove duplicidade de (id_viagem, sequencia) por causa do UNIQUE)
        vistos_trecho = set()

        def t_trecho(l):
            (id_v, seq, o_data, o_uf, o_cid, d_data, d_uf, d_cid, meio, diarias) = l
            id_v, seq = texto(id_v, 20), converter_inteiro(seq)
            if id_v not in validos or (id_v, seq) in vistos_trecho:
                return None
            vistos_trecho.add((id_v, seq))
            return (id_v, seq, converter_data(o_data), texto(o_uf, 40), texto(o_cid, 80),
                    converter_data(d_data), texto(d_uf, 40), texto(d_cid, 80),
                    texto(meio, 50), nao_negativo(converter_decimal(diarias)))

        processar(
            conn_r, conn_w,
            "SELECT id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade, "
            "destino_data, destino_uf, destino_cidade, meio_transporte, numero_diarias "
            "FROM raw_trecho",
            t_trecho,
            "INSERT INTO silver_trecho (id_viagem, sequencia_trecho, origem_data, origem_uf, "
            "origem_cidade, destino_data, destino_uf, destino_cidade, meio_transporte, "
            "numero_diarias) VALUES (" + ", ".join(["%s"] * 10) + ")",
            "silver_trecho",
        )
        log.info("Camada SILVER concluída.")
    except Exception:
        conn_w.rollback()
        log.exception("Erro na transformação")
        sys.exit(1)
    finally:
        conn_r.close()
        conn_w.close()


if __name__ == "__main__":
    main()
