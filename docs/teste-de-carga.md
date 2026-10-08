# Teste de carga com k6

## Objetivo

Mostrar que a API escala sozinha: com mais usuários simultâneos, o Lambda cria mais ambientes de execução e a latência se mantém estável, sem nenhuma configuração de capacidade.

## Cenário (`loadtest/load-test.js`)

| Fase | Duração | Usuários virtuais |
|---|---|---|
| Aquecimento | 30 s | 0 → 10 |
| Escala | 1 min | 10 → 50 |
| Carga sustentada | 2 min | 50 |
| Descida | 30 s | 50 → 0 |

Cada usuário cria uma despesa (`POST /expenses`), lê de volta (`GET /expenses/{id}`) e espera 1 segundo. Com 50 usuários são cerca de 80 a 90 requisições por segundo, abaixo do *throttling* de 100 req/s.

Critérios de aprovação (*thresholds*):

- menos de 1% de erros
- p95 do `POST` abaixo de 800 ms
- p95 do `GET` abaixo de 500 ms

## Como rodar

```bash
# instalar: https://grafana.com/docs/k6/latest/set-up/install-k6/
API_URL=$(aws cloudformation describe-stacks --stack-name serverless-api-aws \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

k6 run -e API_URL="$API_URL" loadtest/load-test.js
```

## O que observar no dashboard

Abra a URL do output `DashboardUrl` enquanto o teste roda:

| Gráfico | Comportamento esperado |
|---|---|
| Lambda: `ConcurrentExecutions` | Sobe junto com os usuários virtuais e desce no fim |
| Lambda: `Duration` | Picos no começo (*cold starts*) e depois estável |
| API: `Latency` p95 | Estável durante a carga sustentada |
| Lambda: `Throttles` | Zero. Se aparecer, a cota de concorrência da conta foi atingida |
| DynamoDB: capacidade consumida | Acompanha as requisições, sem configurar nada |

No X-Ray (*Trace Map*) dá para ver quanto tempo de cada requisição foi gasto no Lambda e quanto no DynamoDB.

## Atenção: cota de concorrência

Contas novas da AWS podem começar com uma cota baixa de execuções simultâneas do Lambda. Confira em **Service Quotas > AWS Lambda > Concurrent executions**. Se estiver baixa, reduza o `target` no script ou peça aumento da cota.

## Limpeza

O teste cria milhares de despesas. Para limpar sem apagar a stack:

```bash
TABLE=$(aws cloudformation describe-stacks --stack-name serverless-api-aws \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" --output text)

aws dynamodb scan --table-name "$TABLE" --projection-expression id --output json \
  | python3 -c "import json,sys; [print(i['id']['S']) for i in json.load(sys.stdin)['Items']]" \
  | while read -r id; do
      aws dynamodb delete-item --table-name "$TABLE" --key "{\"id\": {\"S\": \"$id\"}}"
    done
```
