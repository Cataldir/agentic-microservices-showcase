# Apoio GCP: portas, runtime HTTP e infraestrutura de referência

Este diretório contém exemplos novos de apoio que podem ser estudados sem uma
conta cloud. O contrato `TextGenerator.generate_text(prompt) -> str` mantém o
domínio independente do provedor. O adaptador resolve o alias didático
`reasoning` para um modelo configurado pelo operador. A infraestrutura é uma
referência separada; os testes locais não fazem deploy.

## Executar o que foi testado localmente

Na raiz deste diretório, com Python 3.10 ou posterior já disponível:

```text
python -B run_tests.py
python -B demo_offline.py
```

O primeiro comando executa **45 testes**, usando somente a biblioteca padrão.
Verifica configuração, alias, resposta textual, saída vazia, propagação de
erros, fechamento do cliente, o contrato HTTP e invariantes dos arquivos
Terraform JSON. Gera `test-results.json` e `test-output.txt` locais, ignorados
pelo Git. A demonstração imprime uma resposta identificada como **falsa local**.
Nenhum desses comandos importa o SDK real, resolve ADC ou abre sockets.

| Componente | Evidência nesta entrega | Limite |
| --- | --- | --- |
| Adaptador Python e rotas HTTP | Executados com clientes falsos e streams em memória | Sem resposta Gemini real e sem servidor HTTP em rede |
| `terraform/*.tf.json` | JSON válido; referências, permissões e relações conferidas em testes e documentação | Sem CLI Terraform, parser HCL, provider instalado, `validate`, `plan` ou `apply` |
| `Dockerfile.reference` | Receita completa para o runtime HTTP | Sem build, download de imagem, instalação ou teste de container |
| Template OIDC | Arquivo `.example` fora de `.github/workflows`, job permanentemente desativado | Sem pool, provider WIF, SA de CI ou execução GitHub Actions |

O pacote é adicional ao material portável. Não contém capítulos, trechos
impressos, diagramas do manuscrito ou registros editoriais.

## Geração de texto: configuração e erros

O [Google Gen AI SDK](https://googleapis.github.io/python-genai/) atende o
backend Gemini Enterprise Agent Platform. A receita fixa `google-genai==2.29.0`,
versão consultada na [release oficial](https://github.com/googleapis/python-genai/releases/tag/v2.29.0).
O adaptador usa `enterprise=True` e API `v1`. `vertexai=True` continua sendo o
alias legado de `enterprise` no [cliente oficial desta versão](https://github.com/googleapis/python-genai/blob/v2.29.0/google/genai/client.py).
Não mistura os dois seletores e não usa a Gemini Developer API por API key.

| Entrada | Significado |
| --- | --- |
| Alias `reasoning` | Nome lógico do contrato; não é um ID de modelo Google |
| `GOOGLE_GENAI_MODEL` | ID real escolhido para esse alias; obrigatório, sem default |
| `GOOGLE_CLOUD_PROJECT` | ID do projeto existente; obrigatório |
| `GOOGLE_CLOUD_LOCATION` | Região ou `global` para a chamada de inferência; obrigatório |
| `PORT` | Porta do runtime HTTP; default 8080 |

`GenerationConfig.from_env(env, alias="reasoning")` resolve essas entradas.
Um alias desconhecido falha, assim como nomes vazios, formato inválido,
limites numéricos inválidos ou variáveis `GOOGLE_API_KEY`/`GEMINI_API_KEY`
presentes. A verificação de formato não comprova disponibilidade de modelo,
quota ou conformidade regional. O operador precisa conferir a combinação
modelo/localização e a política de dados antes de uma integração autorizada.

O cliente real é importado apenas em `sdk_client_factory`; obter credenciais
fica a cargo de [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/application-default-credentials).
No Cloud Run, a identidade anexada ao serviço pode fornecer ADC sem uma chave
JSON estática. Nenhuma credencial é criada ou distribuída neste pacote.

A chamada tem timeout SDK de 30.000 ms e 1.024 tokens de saída. O código solicita
uma tentativa ao SDK (`retry_options.attempts = 1`) e não acrescenta um loop de
retry. Isso não oferece efeito exatamente uma vez, controle de quota ou um
prazo total para todas as operações. O formato dessas opções foi conferido em
[`HttpOptions` da versão fixada](https://github.com/googleapis/python-genai/blob/v2.29.0/google/genai/types.py).

`ValueError` indica um prompt ausente ou longo demais. `EmptyResponseError`
indica ausência de texto, que também pode decorrer de bloqueio ou de saída não
textual. `ProviderError` preserva a exceção original em `__cause__`, sem expor
seu conteúdo na mensagem HTTP. O cliente é fechado; uma falha de fechamento
não substitui uma falha de geração já ativa. Uma falha após o provedor ter
processado a chamada não prova que a operação deixou de ocorrer.

## Runtime HTTP Cloud Run

`gcp_support/http_service.py` fornece `GET /healthz` e `POST /generate` com JSON
`{"prompt":"..."}`. A resposta de sucesso é `{"text":"..."}`. Entrada inválida
retorna 400; rota desconhecida 404; método inadequado 405; corpo acima de 64 KiB
413; mídia diferente de JSON 415; falha do provedor ou ausência de texto 502.
A saúde verifica somente o processo HTTP, sem chamar o modelo.

O servidor mínimo usa execução serial. A referência Cloud Run configura
concorrência 1 por instância e escuta `0.0.0.0:PORT`, seguindo o
[contrato de containers](https://docs.cloud.google.com/run/docs/container-contract).
TLS e autenticação de invocação pertencem à plataforma. A referência mantém
ingress interno e não concede `roles/run.invoker` a ninguém; um chamador futuro
precisa de acesso de rede e de IAM definidos separadamente. O serviço não
contém gateway, limitador de taxa, pool de agentes ou um consumidor Pub/Sub.

`Dockerfile.reference` mostra como montar a imagem, mas essa build faria
instalação de dependências e não foi executada aqui. O pacote Python direto
está fixado; dependências transitivas e o digest da imagem base ainda precisam
ser congelados para uma build reproduzível. A imagem implantada pelo Terraform
deve ser informada por digest de um Artifact Registry existente.

## Recursos e identidades declarados

O provider é [`hashicorp/google` 8.6.0](https://github.com/hashicorp/terraform-provider-google/releases/tag/v8.6.0),
fixado em `versions.tf.json`; Terraform 1.6–1.x é a faixa declarada. Os arquivos
usam a [sintaxe JSON oficial do Terraform](https://developer.hashicorp.com/terraform/language/syntax/json),
sem módulos fictícios ou downloads executados nesta revisão.

| Recurso | Papel e fronteira |
| --- | --- |
| Artifact Registry Docker | Repositório para imagens; não faz build ou push |
| Cloud Run v2 | Runtime HTTP opcional, inicialmente desativado |
| Secret Manager | Somente metadados de `business-config`, com réplica regional; sem versão, payload ou referência no container |
| Tópico `tasks` + assinatura pull | Tarefas independentes com retenção declarada de sete dias |
| Tópico `dead-letters` + assinatura de inspeção | Recebe e conserva encaminhamentos da DLQ para inspeção |
| SA `runtime` | Papel customizado só com `aiplatform.endpoints.predict` no projeto |
| SA `publisher` | `roles/pubsub.publisher` somente no tópico de tarefas |
| SA `consumer` | `roles/pubsub.subscriber` somente na assinatura de tarefas |
| SA `inspector` | `roles/pubsub.subscriber` somente na assinatura de inspeção |
| Service agent Pub/Sub existente | Publisher no tópico DLQ e subscriber na assinatura de origem |

A permissão de geração foi conferida no
[mapa oficial de operações e IAM](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/access-control).
Ela não autoriza tuning, criação de endpoints ou administração de modelos.
O runtime não recebe leitura de segredos porque este exemplo usa ADC e não lê
`business-config`. Adicionar um consumidor de segredo exige uma versão
preexistente e `roles/secretmanager.secretAccessor` naquele segredo, como
descreve o [guia de segredos do Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

O deployer e o service agent do Cloud Run são identidades diferentes da SA
`runtime`. Os pré-requisitos de leitura da imagem e de atuar como a SA de
execução precisam ser atendidos separadamente; conceder Artifact Registry
Reader ao runtime não resolve, por si só, o pull da imagem. Consulte
[permissões de implantação](https://docs.cloud.google.com/run/docs/deploying).

Antes de qualquer uso real do IaC, precisam existir projeto, APIs habilitadas
(`run.googleapis.com`, `artifactregistry.googleapis.com`,
`secretmanager.googleapis.com`, `pubsub.googleapis.com`,
`iam.googleapis.com` e `aiplatform.googleapis.com`), permissões do operador,
service agents e política de estado Terraform. Nada disso é criado ou ativado
por um comando desta entrega. O HCL JSON também não define backend remoto.

`project_number` deve ser o número do projeto da assinatura Pub/Sub e seu
service agent já deve existir. A identidade usa
`service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com`. Não se declara
`google_project_service_identity`, que requer provider beta na
[documentação desse recurso](https://github.com/hashicorp/terraform-provider-google/blob/v8.6.0/website/docs/r/project_service_identity.html.markdown).

`enable_runtime` é `false` por default. Os recursos base e as políticas são
declarações revisáveis; não foram aplicados. Uma futura implantação autorizada
tem fases distintas: recursos base, imagem fornecida por processo separado e,
por fim, runtime habilitado. Terraform não constrói ou publica a imagem.
Para esse runtime, são necessários uma imagem já disponível por digest, `inference_model` e
`inference_location`. A região do container é uma entrada independente.
Não há criação de versão de segredo, invocador público ou deploy no CI.
A pré-condição verifica o formato da URI e o repositório esperado; não consulta
a existência da imagem nem testa seu funcionamento.
O serviço tem `deletion_protection=true`. Depois de criado, mudar
`enable_runtime` para `false` solicita remoção e será bloqueado por essa proteção;
não é um mecanismo para suspender tráfego ou cancelar custos.
O esquema do [Cloud Run v2 fixado](https://github.com/hashicorp/terraform-provider-google/blob/v8.6.0/website/docs/r/cloud_run_v2_service.html.markdown)
fundamenta os campos; a implementação final precisa passar pelo provider real.

## Pub/Sub e Kafka: contratos diferentes

A assinatura pull declara entrega **pelo menos uma vez**, sem ordenação e sem
exactly-once. A aplicação deve tolerar duplicatas e confirmar somente após os
efeitos necessários. O prazo de confirmação de 60 segundos não é a retenção
de sete dias. Esses conceitos seguem as
[propriedades da assinatura](https://docs.cloud.google.com/pubsub/docs/subscription-properties).

A DLQ pertence à assinatura de origem. O service agent precisa publicar no
tópico DLQ e confirmar na origem; as concessões ao consumidor da aplicação não
substituem essas duas permissões. O valor 10 é um alvo aproximado de tentativas;
contagem e encaminhamento são best effort, conforme o
[guia de dead-letter topics](https://docs.cloud.google.com/pubsub/docs/dead-letter-topics).
Durante um eventual provisionamento, a política na origem e os vínculos IAM
podem surgir em momentos diferentes. Não usar a fila antes da conclusão e
propagação das permissões; não há simulação cloud dessa sequência aqui.

A referência retém mensagens confirmadas na origem e configura retenção nos
tópicos. Isso permite preparar replay dentro da janela por timestamp ou
snapshot, seguindo [seek e replay](https://docs.cloud.google.com/pubsub/docs/replay-overview).
Não fornece offsets de partições Kafka, um redrive automático ou idempotência
dos efeitos de negócio. Também não implementa o publicador ou consumidor SDK.

Onde o exemplo depende de partições, grupos de consumidores e offsets, manter
a interface Kafka. Um operador pode avaliar o
[Managed Service for Apache Kafka](https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/overview).
Trocar esse mecanismo por Pub/Sub exigiria outro exemplo, em vez de uma mera
troca de nomes.

O serviço HTTP Cloud Run não inicia um loop pull em background. A execução
contínua precisa de um runtime próprio ou de configuração de CPU/ciclo de vida
adequada; veja [alocação de CPU](https://docs.cloud.google.com/run/docs/configuring/billing-settings)
e [worker pools](https://docs.cloud.google.com/run/docs/deploy-worker-pools).

## CI com OIDC: referência sem ativação

`ci/github-oidc.reference.yaml.example` mostra a relação entre GitHub OIDC,
Workload Identity Federation e SA de CI. O job tem `if: ${{ false }}` e não
contém comandos de publicação ou deploy. Os IDs do projeto, provider WIF e SA
de CI são entradas futuras; nenhum valor real foi configurado.

Uma configuração autorizada precisará restringir as claims ao repositório e
ao contexto de execução escolhido; usar IDs estáveis de organização/repositório
evita confundir identidades renomeadas. A SA de CI deve ter apenas as
permissões das operações permitidas e o vínculo de impersonação apropriado.
O arquivo referencia `auth@v3`; fixar as actions por SHA revisado antes de
habilitar a configuração. Veja a
[documentação WIF para pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
e o [repositório oficial da action](https://github.com/google-github-actions/auth).
Credenciais efêmeras geradas pela action são excluídas pelo `.gitignore` e
`.dockerignore`; não são material de apoio.

Não há demonstração de failover entre regiões, replicação de estado,
replicação de tópico, limitação global de requisições ou redução garantida de
custo. Essas capacidades exigem desenho, permissões e verificação próprios.
