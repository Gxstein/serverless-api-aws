# Custos

Valores aproximados para `us-east-1`. Confira sempre na [AWS Pricing Calculator](https://calculator.aws/).

## Modelo de cobrança de cada serviço

| Serviço | Cobra por | Cota gratuita permanente |
|---|---|---|
| Lambda | Requisição + GB-segundo de execução | 1 milhão de requisições e 400 mil GB-s por mês |
| API Gateway (HTTP API) | Milhão de requisições (cerca de US$ 1,00) | Não tem |
| DynamoDB sob demanda | Unidades de leitura e escrita + GB armazenado | 25 GB de armazenamento |
| CloudFront | GB transferido + requisições | 1 TB e 10 milhões de requisições por mês |
| S3 | GB armazenado + requisições | Não tem, mas o frontend tem poucos KB |
| CloudWatch | Logs ingeridos, alarmes, dashboards | 5 GB de logs, 10 alarmes, 3 dashboards |
| X-Ray | *Traces* gravados | 100 mil por mês |

## Cenários

| Tráfego por mês | Custo estimado |
|---|---|
| Parado (só a stack criada) | US$ 0,00 |
| 10 mil requisições (uso pessoal) | menos de US$ 0,05 |
| 1 milhão de requisições | cerca de US$ 2,00 |

Para comparar: uma única EC2 t3.micro ligada 24 horas custa cerca de US$ 7,60 por mês, com ou sem tráfego.

## Escolhas que reduzem custo

- **arm64 (Graviton)** no Lambda: cerca de 20% mais barato por GB-segundo que x86
- **HTTP API** em vez de REST API: cerca de 70% mais barato por requisição
- **DynamoDB sob demanda**: sem pagar capacidade ociosa
- **Logs com retenção de 14 dias**, em vez de guardar para sempre
- **CloudFront PriceClass_100**: só as bordas mais baratas
- **Throttling** no API Gateway: um ataque ou *loop* no frontend não gera uma conta enorme
