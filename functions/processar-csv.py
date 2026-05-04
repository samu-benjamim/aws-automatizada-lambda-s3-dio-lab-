"""
Funcao Lambda — Processar CSV do S3
=====================================
Trigger: S3 PutObject (arquivos .csv)
Descricao: Le um arquivo CSV enviado ao S3, processa os dados
           (limpeza, validacao, estatisticas) e salva o resultado
           como JSON no mesmo bucket, na pasta 'resultados/'.

Variaveis de Ambiente necessarias:
    PASTA_RESULTADOS — Pasta de saida no S3 (default: 'resultados/')
    ENCODING_CSV     — Encoding do CSV (default: 'utf-8')
"""

import csv
import io
import json
import logging
import os
import urllib.parse
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')

PASTA_RESULTADOS = os.environ.get('PASTA_RESULTADOS', 'resultados/')
ENCODING_CSV     = os.environ.get('ENCODING_CSV', 'utf-8')


def lambda_handler(event, context):
    """
    Processa arquivo CSV do S3 e salva resultado como JSON.
    """

    logger.info("Inicio | RequestId: %s", context.aws_request_id)

    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    chave  = urllib.parse.unquote_plus(
        record['s3']['object']['key'], encoding='utf-8'
    )

    # Valida se e realmente um CSV
    if not chave.lower().endswith('.csv'):
        logger.warning("Arquivo ignorado (nao e CSV): %s", chave)
        return {'statusCode': 200, 'body': 'Arquivo ignorado — nao e CSV'}

    logger.info("Processando: s3://%s/%s", bucket, chave)

    try:
        # ── 1. Baixa o CSV do S3 ──────────────────────────────
        response = s3.get_object(Bucket=bucket, Key=chave)
        conteudo = response['Body'].read().decode(ENCODING_CSV)

        # ── 2. Parse e limpeza dos dados ──────────────────────
        dados_brutos, dados_limpos, erros = parsear_csv(conteudo)

        # ── 3. Gera estatisticas ──────────────────────────────
        estatisticas = gerar_estatisticas(dados_limpos)

        # ── 4. Monta o resultado ──────────────────────────────
        resultado = {
            "metadados": {
                "arquivo_origem": chave,
                "bucket_origem": bucket,
                "processado_em": datetime.utcnow().isoformat() + "Z",
                "lambda_request_id": context.aws_request_id,
                "encoding": ENCODING_CSV
            },
            "resumo": {
                "total_linhas_brutas": len(dados_brutos),
                "total_linhas_validas": len(dados_limpos),
                "total_linhas_com_erro": len(erros),
                "colunas": list(dados_limpos[0].keys()) if dados_limpos else []
            },
            "estatisticas": estatisticas,
            "erros_validacao": erros[:10],  # limita a 10 erros no resultado
            "dados": dados_limpos
        }

        # ── 5. Salva resultado como JSON no S3 ────────────────
        nome_arquivo = chave.rsplit('/', 1)[-1].replace('.csv', '')
        agora        = datetime.utcnow()
        chave_resultado = (
            f"{PASTA_RESULTADOS}"
            f"{agora.year}/{agora.month:02d}/{agora.day:02d}/"
            f"{nome_arquivo}_resultado.json"
        )

        s3.put_object(
            Bucket=bucket,
            Key=chave_resultado,
            Body=json.dumps(resultado, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json',
            Metadata={
                'arquivo-origem': chave,
                'total-registros': str(len(dados_limpos))
            }
        )

        logger.info(
            "Resultado salvo em s3://%s/%s | %d registros validos",
            bucket, chave_resultado, len(dados_limpos)
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'mensagem': f'{len(dados_limpos)} registros processados com sucesso',
                'resultado_em': chave_resultado,
                'resumo': resultado['resumo']
            }, ensure_ascii=False)
        }

    except ClientError as e:
        codigo = e.response['Error']['Code']
        logger.error("Erro S3 [%s]: %s", codigo, str(e))
        raise

    except Exception as e:
        logger.error("Erro inesperado: %s", str(e), exc_info=True)
        raise


def parsear_csv(conteudo: str) -> tuple:
    """
    Faz o parse do conteudo CSV, limpando e validando cada linha.

    Retorna:
        tuple: (dados_brutos, dados_limpos, erros)
    """
    leitor      = csv.DictReader(io.StringIO(conteudo))
    dados_brutos = []
    dados_limpos = []
    erros        = []

    for i, linha in enumerate(leitor, start=2):  # start=2 pois linha 1 e cabecalho
        dados_brutos.append(dict(linha))

        # Limpa espacos extras em todas as colunas
        linha_limpa = {k.strip(): v.strip() for k, v in linha.items() if k}

        # Valida linha (remove linhas completamente vazias)
        valores = list(linha_limpa.values())
        if all(v == '' for v in valores):
            erros.append({'linha': i, 'motivo': 'Linha completamente vazia'})
            continue

        dados_limpos.append(linha_limpa)

    return dados_brutos, dados_limpos, erros


def gerar_estatisticas(dados: list) -> dict:
    """
    Gera estatisticas basicas sobre o dataset processado.
    Identifica colunas numericas e calcula min/max/media.
    """
    if not dados:
        return {}

    colunas = dados[0].keys()
    estatisticas = {}

    for coluna in colunas:
        valores = [row.get(coluna, '') for row in dados]
        nao_vazios = [v for v in valores if v != '']

        # Tenta converter para numero
        try:
            numericos = [float(v.replace(',', '.')) for v in nao_vazios]
            estatisticas[coluna] = {
                "tipo": "numerico",
                "total": len(valores),
                "preenchidos": len(nao_vazios),
                "vazios": len(valores) - len(nao_vazios),
                "minimo": min(numericos),
                "maximo": max(numericos),
                "media": round(sum(numericos) / len(numericos), 2)
            }
        except (ValueError, ZeroDivisionError):
            # Coluna textual
            unicos = set(nao_vazios)
            estatisticas[coluna] = {
                "tipo": "texto",
                "total": len(valores),
                "preenchidos": len(nao_vazios),
                "vazios": len(valores) - len(nao_vazios),
                "valores_unicos": len(unicos)
            }

    return estatisticas
