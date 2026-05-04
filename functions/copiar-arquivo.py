"""
Funcao Lambda — Copiar Arquivo Entre Buckets S3
================================================
Trigger: S3 PutObject no bucket de ORIGEM
Descricao: Copia automaticamente arquivos enviados ao bucket
           de origem para o bucket de destino, organizando
           por data e tipo de arquivo.

Variaveis de Ambiente necessarias:
    BUCKET_DESTINO  — Nome do bucket de destino
    PREFIXO_DESTINO — Prefixo/pasta de destino (default: 'processados/')

IMPORTANTE: Use sempre buckets distintos para origem e destino
            para evitar loop infinito de triggers!
"""

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

# ── Configuracao via variaveis de ambiente ────────
BUCKET_DESTINO  = os.environ.get('BUCKET_DESTINO', 'bucket-processados-dio')
PREFIXO_DESTINO = os.environ.get('PREFIXO_DESTINO', 'processados/')


def lambda_handler(event, context):
    """
    Copia cada arquivo do evento S3 para o bucket de destino,
    organizando em subpastas por ano/mes/dia.
    """

    logger.info("Inicio | RequestId: %s | Destino: %s", context.aws_request_id, BUCKET_DESTINO)

    resultados = []

    for record in event.get('Records', []):
        bucket_origem = record['s3']['bucket']['name']
        chave_origem  = urllib.parse.unquote_plus(
            record['s3']['object']['key'], encoding='utf-8'
        )

        try:
            chave_destino = montar_chave_destino(chave_origem)

            # ── Copia o objeto ────────────────────────────────
            s3.copy_object(
                CopySource={
                    'Bucket': bucket_origem,
                    'Key': chave_origem
                },
                Bucket=BUCKET_DESTINO,
                Key=chave_destino,
                MetadataDirective='COPY',       # preserva metadados originais
                TaggingDirective='COPY'         # preserva tags originais
            )

            # ── Adiciona tag de rastreamento ──────────────────
            s3.put_object_tagging(
                Bucket=BUCKET_DESTINO,
                Key=chave_destino,
                Tagging={
                    'TagSet': [
                        {'Key': 'CopiadoDe',   'Value': bucket_origem},
                        {'Key': 'ChaveOrigem', 'Value': chave_origem},
                        {'Key': 'CopiadoEm',   'Value': datetime.utcnow().isoformat() + 'Z'},
                        {'Key': 'ManagedBy',   'Value': 'Lambda'}
                    ]
                }
            )

            logger.info(
                "Copiado com sucesso | %s/%s → %s/%s",
                bucket_origem, chave_origem, BUCKET_DESTINO, chave_destino
            )

            resultados.append({
                'arquivo': chave_origem,
                'destino': chave_destino,
                'status': 'copiado'
            })

        except ClientError as e:
            codigo = e.response['Error']['Code']
            logger.error("Erro S3 ao copiar %s: [%s] %s", chave_origem, codigo, str(e))
            resultados.append({
                'arquivo': chave_origem,
                'status': 'erro',
                'detalhe': f"[{codigo}] {str(e)}"
            })

        except Exception as e:
            logger.error("Erro inesperado ao copiar %s: %s", chave_origem, str(e))
            resultados.append({
                'arquivo': chave_origem,
                'status': 'erro',
                'detalhe': str(e)
            })

    sucesso = sum(1 for r in resultados if r['status'] == 'copiado')
    total   = len(resultados)

    logger.info("Concluido | %d/%d arquivos copiados", sucesso, total)

    return {
        'statusCode': 200 if sucesso == total else 207,
        'body': json.dumps({
            'mensagem': f'{sucesso} de {total} arquivos copiados',
            'bucket_destino': BUCKET_DESTINO,
            'resultados': resultados
        }, ensure_ascii=False)
    }


def montar_chave_destino(chave_origem: str) -> str:
    """
    Monta a chave de destino organizando por data.

    Exemplo:
        origem:  'uploads/relatorio.csv'
        destino: 'processados/2024/01/15/relatorio.csv'
    """
    agora = datetime.utcnow()
    nome_arquivo = chave_origem.rsplit('/', 1)[-1]  # pega apenas o nome do arquivo

    return (
        f"{PREFIXO_DESTINO}"
        f"{agora.year}/{agora.month:02d}/{agora.day:02d}/"
        f"{nome_arquivo}"
    )
