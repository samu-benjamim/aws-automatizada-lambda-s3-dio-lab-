# ⚡ Tarefas Automatizadas com AWS Lambda Function e S3

> Repositório criado como entregável do desafio de laboratório da [DIO](https://www.dio.me/), com foco em consolidar conhecimentos sobre **automação de tarefas** utilizando **AWS Lambda** integrado ao **Amazon S3**.

---

## 📌 Sobre o Desafio

Este laboratório tem como objetivo implementar tarefas automatizadas utilizando **AWS Lambda Functions** em conjunto com o **Amazon S3**, explorando como funções serverless podem reagir a eventos de armazenamento e processar dados de forma automática, escalável e sem necessidade de gerenciar servidores.

---

## 🎯 Objetivos de Aprendizagem

- [x] Criar e configurar funções Lambda na AWS
- [x] Integrar Lambda com eventos do Amazon S3
- [x] Automatizar tarefas de processamento de arquivos serverless
- [x] Documentar processos técnicos de forma clara e estruturada
- [x] Utilizar o GitHub como ferramenta de compartilhamento de documentação técnica

---

## 📚 Conceitos Fundamentais

### O que é AWS Lambda?

O **AWS Lambda** é um serviço de computação **serverless** — você escreve o código, a AWS cuida de tudo o mais: servidores, sistema operacional, escalabilidade, disponibilidade e patches de segurança.

**Como funciona:**
```
Evento ocorre  →  Lambda é invocada  →  Código executa  →  Lambda encerra
  (trigger)        (em milissegundos)    (até 15 min)      (você paga só isso)
```

### Por que Lambda + S3 é uma combinação poderosa?

| Cenário | O que acontece automaticamente |
|---|---|
| Upload de imagem no S3 | Lambda redimensiona e gera thumbnail |
| CSV enviado para bucket | Lambda processa e insere no banco de dados |
| Arquivo de log chegando | Lambda analisa e dispara alertas |
| PDF enviado por cliente | Lambda extrai texto e indexa para busca |
| Vídeo enviado para S3 | Lambda aciona serviço de transcodificação |

---

## 🏗️ Arquitetura da Solução

```
┌─────────────┐     evento      ┌──────────────────┐     resultado    ┌──────────────┐
│             │  ─────────────► │                  │ ───────────────► │              │
│  Amazon S3  │   (PutObject)   │  AWS Lambda Fn   │   (processado)   │  S3 / RDS /  │
│  (Bucket    │                 │  (seu código)    │                  │  SNS / DynamoDB│
│   origem)   │ ◄───────────── │                  │                  │              │
└─────────────┘   permissão     └──────────────────┘                  └──────────────┘
                  via IAM Role         │
                                       │ logs
                                       ▼
                               ┌──────────────────┐
                               │  CloudWatch Logs │
                               └──────────────────┘
```

---

## 🛠️ Criando uma Lambda Function — Passo a Passo

### 1. Acessar o serviço Lambda no console AWS

- Menu de serviços → **Lambda**
- Clique em **"Create function"**

### 2. Configurar a função

| Campo | Valor recomendado |
|---|---|
| **Author from scratch** | Selecionar |
| **Function name** | `processar-arquivo-s3` |
| **Runtime** | Python 3.12 ou Node.js 20.x |
| **Architecture** | x86_64 |
| **Execution role** | Create a new role with basic Lambda permissions |

### 3. Adicionar o gatilho S3 (Trigger)

- Na página da função, clique em **"Add trigger"**
- Selecione **S3**
- Configure:
  - **Bucket**: selecione o bucket de origem
  - **Event type**: `PUT` (ou `All object create events`)
  - **Prefix**: pasta específica (ex: `uploads/`) — opcional
  - **Suffix**: extensão do arquivo (ex: `.csv`) — opcional

### 4. Configurar permissões IAM

A função precisa de permissão para acessar o S3. Adicione à IAM Role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::nome-do-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 💻 Exemplos de Funções Lambda

### Exemplo 1 — Registrar upload no log (Python)

Função mais simples: apenas loga o nome e tamanho do arquivo enviado ao S3.

```python
import json
import boto3

def lambda_handler(event, context):
    # Extraindo informações do evento S3
    bucket = event['Records'][0]['s3']['bucket']['name']
    chave  = event['Records'][0]['s3']['object']['key']
    tamanho = event['Records'][0]['s3']['object']['size']
    
    print(f"Arquivo recebido: {chave}")
    print(f"Bucket: {bucket}")
    print(f"Tamanho: {tamanho} bytes")
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Arquivo {chave} processado com sucesso!')
    }
```

---

### Exemplo 2 — Copiar arquivo para bucket de destino (Python)

Automatiza a cópia de arquivos enviados para um bucket de processamento:

```python
import boto3

s3 = boto3.client('s3')
BUCKET_DESTINO = 'meu-bucket-processado'

def lambda_handler(event, context):
    bucket_origem = event['Records'][0]['s3']['bucket']['name']
    chave = event['Records'][0]['s3']['object']['key']
    
    # Copia o arquivo para o bucket de destino
    s3.copy_object(
        CopySource={'Bucket': bucket_origem, 'Key': chave},
        Bucket=BUCKET_DESTINO,
        Key=f"processados/{chave}"
    )
    
    print(f"Arquivo {chave} copiado para {BUCKET_DESTINO}/processados/")
    
    return {'statusCode': 200, 'body': 'Copia realizada com sucesso'}
```

---

### Exemplo 3 — Processar CSV e salvar resultado (Python)

Lê um CSV enviado ao S3, processa os dados e salva o resultado:

```python
import boto3
import csv
import io
import json

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    chave  = event['Records'][0]['s3']['object']['key']
    
    # Baixa o arquivo CSV do S3
    response = s3.get_object(Bucket=bucket, Key=chave)
    conteudo = response['Body'].read().decode('utf-8')
    
    # Processa o CSV
    leitor = csv.DictReader(io.StringIO(conteudo))
    registros = list(leitor)
    total = len(registros)
    
    print(f"Total de registros processados: {total}")
    
    # Salva o resultado como JSON no S3
    resultado = json.dumps({'total_registros': total, 'dados': registros})
    chave_resultado = chave.replace('.csv', '_resultado.json')
    
    s3.put_object(
        Bucket=bucket,
        Key=f"resultados/{chave_resultado}",
        Body=resultado.encode('utf-8'),
        ContentType='application/json'
    )
    
    return {'statusCode': 200, 'body': f'{total} registros processados'}
```

---

## 🔗 S3 Object Lambda — Transformação em Tempo Real

O **S3 Object Lambda** permite transformar dados **no momento da leitura**, sem criar cópias dos arquivos. A Lambda intercepta a requisição `GetObject` e modifica a resposta:

```
Cliente solicita objeto  →  S3 Object Lambda  →  Lambda transforma  →  Retorna dado modificado
     (GetObject)              (intercepta)         (em tempo real)        (sem cópia no S3)
```

**Casos de uso:**
- Redimensionar imagens conforme o dispositivo do usuário
- Mascarar dados sensíveis (PII) automaticamente
- Converter formatos (XML → JSON) na entrega
- Aplicar marca d'água em documentos

**Configuração com CloudFormation:**
```yaml
S3ObjectLambdaAccessPoint:
  Type: AWS::S3ObjectLambda::AccessPoint
  Properties:
    Name: meu-access-point-transformacao
    ObjectLambdaConfiguration:
      SupportingAccessPoint: !Sub "arn:aws:s3:${AWS::Region}:${AWS::AccountId}:accesspoint/meu-access-point"
      TransformationConfigurations:
        - Actions: [GetObject]
          ContentTransformation:
            AwsLambda:
              FunctionArn: !GetAtt MinhaFuncaoLambda.Arn
```

---

## ⚙️ Configurações Importantes da Lambda

### Limites e configurações relevantes

| Configuração | Valor padrão | Máximo | Quando ajustar |
|---|---|---|---|
| **Timeout** | 3 segundos | 15 minutos | Processamentos longos |
| **Memória** | 128 MB | 10.240 MB | Arquivos grandes ou operações pesadas |
| **Tamanho do pacote** | — | 250 MB (zip) | Dependências externas |
| **Variáveis de ambiente** | — | 4 KB total | Configurações sensíveis |
| **Concorrência** | 1.000 | Sob demanda | Alta carga simultânea |

### Variáveis de ambiente — boa prática

Em vez de hardcodar nomes de buckets e configurações no código:

```python
import os

BUCKET_DESTINO = os.environ['BUCKET_DESTINO']  # configurado nas env vars da Lambda
PREFIXO = os.environ.get('PREFIXO', 'processados/')  # com valor padrão
```

---

## 📊 Monitoramento e Logs

### CloudWatch Logs

Todo `print()` ou `logging` na função aparece automaticamente no CloudWatch:

```
/aws/lambda/processar-arquivo-s3
  └── 2024/01/15
      └── [$LATEST] abc123...
          ├── START RequestId: xxx
          ├── Arquivo recebido: relatorio.csv
          ├── Total de registros: 1523
          └── END RequestId: xxx  Duration: 234ms  Billed: 300ms
```

### Métricas importantes no CloudWatch

| Métrica | O que monitora |
|---|---|
| **Invocations** | Quantas vezes a função foi chamada |
| **Duration** | Tempo de execução (afeta o custo) |
| **Errors** | Falhas na execução |
| **Throttles** | Invocações bloqueadas por limite de concorrência |
| **ConcurrentExecutions** | Execuções simultâneas em andamento |

---

## 💡 Boas Práticas

### ✅ O que fazer
- Sempre usar **variáveis de ambiente** para configurações (nomes de buckets, endpoints)
- Configurar **Dead Letter Queue (DLQ)** com SQS para capturar falhas
- Usar **camadas (Layers)** para dependências compartilhadas entre funções
- Definir **timeout adequado** — nunca deixar no padrão de 3s para processos longos
- Adicionar **tratamento de exceções** com try/except para erros previsíveis
- Usar **logs estruturados** (JSON) para facilitar análise no CloudWatch

### ❌ O que evitar
- Colocar credenciais AWS no código — use **IAM Roles**
- Ignorar o campo **"Billed Duration"** nos logs — afeta diretamente o custo
- Criar loops infinitos acidentais (Lambda grava no S3 → S3 dispara Lambda → ...)
- Deixar a função com mais memória do que precisa — ajuste para otimizar custo

---

## ⚠️ Armadilha Clássica — Loop Infinito

Cuidado com o cenário mais comum de erro ao integrar Lambda com S3:

```
❌ PROBLEMA:
Bucket A → aciona Lambda → Lambda grava no Bucket A → aciona Lambda → Loop infinito 💸

✅ SOLUÇÃO:
Bucket A (origem) → aciona Lambda → Lambda grava no Bucket B (destino)
```

Sempre use **buckets distintos** para origem e destino, ou configure o trigger com **prefixo/sufixo** para evitar que a Lambda processe os próprios arquivos que gera.

---

## 🗂️ Estrutura do Repositório

```
📁 repo-lambda-s3-dio/
├── 📄 README.md
├── 📁 functions/
│   ├── registrar-upload.py          ← Exemplo 1: log de uploads
│   ├── copiar-arquivo.py            ← Exemplo 2: cópia entre buckets
│   └── processar-csv.py             ← Exemplo 3: processamento de CSV
├── 📁 cloudformation/
│   └── lambda-s3-stack.yaml         ← Stack CloudFormation do lab
└── 📁 images/
    ├── 01-criacao-funcao.png
    ├── 02-configuracao-trigger.png
    ├── 03-teste-execucao.png
    └── 04-logs-cloudwatch.png
```

---

## 🔗 Recursos Utilizados

- [S3 Object Lambda com CloudFormation — Documentação AWS](https://docs.aws.amazon.com/pt_br/AmazonS3/latest/userguide/olap-using-cfn-template.html)
- [AWS Lambda — Documentação Oficial](https://docs.aws.amazon.com/pt_br/lambda/latest/dg/welcome.html)
- [Usando Lambda com Amazon S3](https://docs.aws.amazon.com/pt_br/lambda/latest/dg/with-s3.html)
- [GitHub Quick Start — DIO](https://github.com/digitalinnovationone/github-quickstart)
- [GitBook: Formação GitHub Certification](https://aline-antunes.gitbook.io/formacao-fundamentos-github)

---

## 👨‍💻 Autor

Feito com 💙 durante os estudos na [DIO](https://www.dio.me/) — Plataforma de Educação em Tecnologia.

---

> *"Serverless não significa sem servidor — significa sem preocupação com servidor."*