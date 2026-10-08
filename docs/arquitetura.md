# Arquitetura

## Por que serverless

| Pergunta | Com servidor (EC2) | Serverless (este projeto) |
|---|---|---|
| Quem cuida do sistema operacional? | Eu | AWS |
| Como escala? | Auto Scaling configurado por mim | Automático, por requisição |
| Quanto custa parado? | A instância continua cobrando | Praticamente nada |
| Como faço deploy? | Imagem, servidor, reinício | Novo pacote da função, em segundos |

## Caminho de uma requisição

1. O navegador abre `https://<id>.cloudfront.net`. O CloudFront entrega `index.html`, `app.js` e `styles.css` do cache mais próximo ou busca no S3 assinando a requisição (OAC).
2. O JavaScript chama `https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/expenses`.
3. O API Gateway aplica CORS e *throttling* e transforma a requisição num evento (payload v2) para o Lambda.
4. A função lê `routeKey` (por exemplo `POST /expenses`), valida o corpo e grava no DynamoDB.
5. A resposta volta pelo mesmo caminho. Logs, métricas e o *trace* do X-Ray ficam no CloudWatch.

## Por que uma única função

As cinco rotas apontam para a mesma função, que faz o roteamento por `routeKey`:

- menos *cold starts*, porque uma execução já aquecida atende qualquer rota
- um único conjunto de permissões, logs e alarmes
- código pequeno o bastante para não justificar separar

Se uma rota precisasse de mais memória ou de permissões diferentes, ela ganharia uma função própria.

## Modelo de dados (DynamoDB)

| Atributo | Tipo | Exemplo |
|---|---|---|
| `id` (chave de partição) | String (UUID) | `3f0c...` |
| `description` | String | `Almoço` |
| `amount` | Number | `32.9` |
| `category` | String | `alimentacao` |
| `date` | String (ISO) | `2026-10-05` |
| `created_at` | String (ISO, UTC) | `2026-10-05T15:20:11+00:00` |

O valor é tratado como `Decimal` no Python e arredondado para centavos, evitando erro de ponto flutuante com dinheiro.

`GET /expenses` e `/summary` usam `Scan` com paginação. Para uma tabela pessoal pequena isso é simples e barato. Com muitos dados, o próximo passo seria um índice secundário (GSI) por mês ou categoria e usar `Query`.

## Escalabilidade

- **Lambda**: cada requisição simultânea usa um ambiente de execução. Se 50 chegam juntas, a AWS cria até 50 ambientes sem nenhuma configuração. O limite é a cota de concorrência da conta.
- **API Gateway**: escala sozinho; o *throttling* configurado (100 req/s, rajada de 200) protege a conta.
- **DynamoDB sob demanda**: aceita picos sem planejamento de capacidade, cobrando por leitura e escrita.
- **CloudFront**: o frontend é servido do cache nas bordas, sem carga na origem.

## Infraestrutura como código

- `template.yaml` (SAM) vira um template CloudFormation. O `sam deploy` cria um *change set*, mostra o que vai mudar e aplica.
- `deploy/github-oidc.yaml` é CloudFormation puro e cria, uma vez, o acesso do GitHub Actions.
- O CloudFormation usa uma role de execução própria. A role do GitHub só pode iniciar o deploy desta stack.
