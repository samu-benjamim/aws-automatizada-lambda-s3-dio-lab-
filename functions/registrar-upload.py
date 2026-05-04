"""
Funcao Lambda — Registrar Upload no CloudWatch
================================================
Trigger: S3 PutObject
Descricao: Captura eventos de upload no S3 e registra
           informacoes detalhadas no CloudWatch Logs.

Uso: Auditoria, rastreamento e monitoramento de uploads.
"""

import json
import logging
import urllib.parse
from datetime import datetime

# Configuracao de logging estruturado
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Handler principal da funcao Lambda.

    Parametros:
        event   (dict): Dados do evento S3 (bucket, objeto, tamanho...)
        context (obj):  Contexto de execucao da Lambda (memoria, timeout...)

    Retorno:
        dict: Status HTTP e mensagem de confirmacao
    """

    logger.info("Inicio do processamento | RequestId: %s", context.aws_request_id)

    resultados = []

    # Um evento S3 pode conter multiplos registros (ex: upload em lote)
    for i, record in enumerate(event.get('Records', [])):

        try:
            # ── Extrai dados do evento ────────────────────────
            bucket = record['s3']['bucket']['name']
            chave  = urllib.parse.unquote_plus(
                record['s3']['object']['key'],
                encoding='utf-8'
            )
            tamanho   = record['s3']['object'].get('size', 0)
            etag      = record['s3']['object'].get('eTag', 'N/A')
            regiao    = record['awsRegion']
            evento    = record['eventName']
            timestamp = record['eventTime']

            # ── Calcula tamanho em formato legivel ────────────
            tamanho_legivel = formatar_tamanho(tamanho)

            # ── Determina tipo do arquivo ─────────────────────
            extensao = chave.rsplit('.', 1)[-1].lower() if '.' in chave else 'sem extensao'

            # ── Log estruturado ───────────────────────────────
            log_entry = {
                "registro": i + 1,
                "bucket": bucket,
                "arquivo": chave,
                "extensao": extensao,
                "tamanho_bytes": tamanho,
                "tamanho_legivel": tamanho_legivel,
                "etag": etag,
                "regiao": regiao,
                "evento": evento,
                "timestamp_evento": timestamp,
                "timestamp_processamento": datetime.utcnow().isoformat() + "Z",
                "lambda_request_id": context.aws_request_id
            }

            logger.info("Upload registrado: %s", json.dumps(log_entry, ensure_ascii=False))

            resultados.append({
                "arquivo": chave,
                "status": "registrado",
                "tamanho": tamanho_legivel
            })

        except KeyError as e:
            logger.error("Erro ao extrair dados do registro %d: campo ausente %s", i, str(e))
            resultados.append({"registro": i + 1, "status": "erro", "detalhe": str(e)})

        except Exception as e:
            logger.error("Erro inesperado no registro %d: %s", i, str(e))
            resultados.append({"registro": i + 1, "status": "erro", "detalhe": str(e)})

    total = len(resultados)
    sucesso = sum(1 for r in resultados if r.get('status') == 'registrado')

    logger.info(
        "Processamento concluido | Total: %d | Sucesso: %d | Erros: %d",
        total, sucesso, total - sucesso
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'mensagem': f'{sucesso} de {total} uploads registrados com sucesso',
            'resultados': resultados
        }, ensure_ascii=False)
    }


def formatar_tamanho(tamanho_bytes: int) -> str:
    """Converte bytes para formato legivel (KB, MB, GB)."""
    if tamanho_bytes < 1024:
        return f"{tamanho_bytes} B"
    elif tamanho_bytes < 1024 ** 2:
        return f"{tamanho_bytes / 1024:.1f} KB"
    elif tamanho_bytes < 1024 ** 3:
        return f"{tamanho_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{tamanho_bytes / (1024 ** 3):.2f} GB"
