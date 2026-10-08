# Qualidade, fallback e adapter HTTP — capítulo 4

| Código | Fonte completa | Recorte | Módulo |
| --- | --- | --- | --- |
| 04-09 | [avaliação](archive/04/04-09.py) | [composição](printed/04-09.py) | [quality.py](../../../core/book_examples/chapter04/quality.py) |
| 04-10 | [fallback](archive/04/04-10.py) | [estratégia](printed/04-10.py) | [fallback.py](../../../core/book_examples/chapter04/fallback.py) |
| 04-12 | [HTTP com httpx](archive/04/04-12.py) | [execute](printed/04-12.py) | [http_adapter.py](../../../core/book_examples/chapter04/http_adapter.py) |

Os módulos de qualidade e fallback incluem imports dos tipos de apoio necessários.
A variante HTTP recebe um cliente explicitamente, sem criar conexão ou importar
`httpx`. Seus testes usam bibliotecas padrão e respostas programadas.

Na raiz do repositório, com Python 3.11 ou posterior:

```sh
python -m unittest tests.book_examples.chapter04.test_quality_fallback_http -v
```

Os [testes](../../../tests/book_examples/chapter04/test_quality_fallback_http.py)
mostram a montagem de avaliadores, agentes, cache e cliente HTTP. Também
executam os métodos dos recortes com os tipos e auxiliares completos. No recorte
HTTP, o namespace local associa `httpx.HTTPStatusError` à exceção da variante;
esse vínculo não importa nem testa o pacote externo.

## Montar o adapter sem rede

```python
import asyncio
from core.book_examples.chapter04.http_adapter import CatalogToolAdapter
from tests.book_examples.chapter04.test_quality_fallback_http import (
    FakeHttpClient, FakeResponse,
)

client = FakeHttpClient(FakeResponse({"products": [{"name": "Book"}]}))
adapter = CatalogToolAdapter("https://catalog.invalid", client=client)
print(asyncio.run(adapter.execute({"query": "book"})))
```

O cliente injetado precisa ter `async get(url, params=...)` e
`async post(url, json=...)`. A resposta deve oferecer `raise_for_status()`,
`json()` e `status_code`. Erros de status precisam usar a exceção local
`HTTPStatusError`, com `response.status_code`, ou ser traduzidos para ela.
O chamador define timeout e fechamento do cliente. A variante não cria o
`httpx.AsyncClient(timeout=30.0)` da fonte e não garante compatibilidade com
um cliente externo apenas por fornecer esses métodos.

## Avaliação de qualidade

`quality.py` combina heurísticas de comprimento/estrutura e padrões de evasão;
a fábrica usa pesos de 0,4 e 0,6. Isso não avalia correção factual. A regex de
lista aceita `1. item`, `-. item` e `*. item`, mas não `- item`, `* item` ou
`10. item`. O detector conta padrões distintos, não repetições, e pode penalizar
recusas legítimas.

O composto verifica a soma dos pesos com tolerância 0,001, mas não rejeita pesos
negativos nem limita a nota a 0–1. Os dois avaliadores concretos ignoram o
contexto recebido. No breaker, nota abaixo do limiar falha; nota igual passa.

## Ordem de fallback e falhas do cache

A cadeia é primário → cache → secundário → resposta degradada. A chave SHA-256
usa JSON com chaves ordenadas da tarefa e do contexto; ambos precisam ser
serializáveis. Resultados do secundário não são gravados no cache.

Se `cache.set` falhar depois do sucesso primário, a cadeia pode descartar o
resultado obtido, embora o breaker já registre sucesso. Falha em `cache.get`
interrompe a cadeia antes do secundário. Cache vazio é tratado como ausência;
valor incompatível com mapeamento pode provocar `TypeError`. O resultado recebe
metadados `_fallback` e `_warning`, substituindo chaves homônimas da cópia.

## HTTP, cache e erros

O schema declara campos obrigatórios e tipos, mas o adapter não os valida nem
aplica defaults. Rate limiting não está implementado. O cache alcança GET e
POST, sem invalidação de escrita ou política de idempotência.

O TTL usa `time.time()`, expira na igualdade e aceita `{}` como resposta
cacheável. JSON `null` não produz acerto porque `None` também representa ausência.
Erros de status viram dicionário e não são cacheados; timeout, outros erros de
transporte e JSON inválido propagam. Concorrência de cache, autenticação,
OpenAI/MCP e um catálogo real exigem integração e testes próprios.
