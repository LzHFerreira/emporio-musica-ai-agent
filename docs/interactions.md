# Recorded conversations

These five conversations were generated live on 2026-11-04 and are copied verbatim from the command output; nothing was scripted, edited or retried selectively. Each customer message went through the signed local webhook, the worker, the tool loop and the evidence guard, and each reply reached the mock Meta transport.

- **Model:** `qwen3.5:9b` (Q4_K_M) on a local Ollama server, on an AMD Ryzen 5 8600G with Radeon 760M integrated graphics (Vulkan) and 28 GB RAM. Requests took 10–70 s each.
- **Code:** commit `5750de3`; source snapshot `8e4d35de1785a6b0e4455abf575694dd884f6a74401413e84669ea6f9a54c2d5`, loaded into a fresh database.
- **Settings:** `MODEL_PROVIDER=ollama`, `OLLAMA_MODEL=qwen3.5:9b`, `TURN_DEADLINE_SECONDS=900` (the 60 s default is a WhatsApp reply target that a local CPU/iGPU model cannot meet).
- **Customers:** synthetic senders, except conversation 4, which uses `--sender` with the phone of synthetic customer 2 so order lookups are scoped to her.

Nine of ten turns produced a grounded answer; one ended in the fixed safe-failure reply. Each conversation ends with a check against the source data, including what the agent got wrong or left out.

Reproduce after [setup](../README.md#running-the-project), for example:

```bash
MODEL_PROVIDER=ollama OLLAMA_MODEL=qwen3.5:9b TURN_DEADLINE_SECONDS=900 \
  uv run --env-file .env python manage.py interact_chat --sender 5567996547821
```

Model output varies between runs, so a rerun will not reproduce these replies word for word.

## 1. Catalog search with a budget, then a PIX follow-up

Recorded 2026-11-04T14:57:31Z with `interact_chat`.

**Customer:** Quais opções de violões disponíveis custando até R$1000?

**Agent:**

> Encontrei algumas opções de violões disponíveis no nosso catálogo com preço até R$ 1000:
>
> 1. **Tagima Memphis AC-39 Nylon Natural** - R$ 429,90  
>    Violão clássico com cordas de nylon, perfeito para quem está começando. Corpo leve e confortável para longas sessões de estudo.
>
> 2. **Rozini RC-104 Nylon Estudante** - R$ 459,90  
>    Violão clássico de estudo da Rozini, feito com madeiras nacionais. Acabamento caprichado e preço acessível para iniciantes.
>
> 3. **Shelby SN-100 Folk Aço Preto** - R$ 549,00  
>    Violão folk aço com visual moderno em preto. Indicado para quem busca um instrumento versátil com boa relação custo-benefício.
>
> 4. **Giannini GF-1R Aço Folk Sunburst** - R$ 579,90  
>    Violão folk com tampo em Spruce e acabamento Sunburst clássico. Som equilibrado e visual elegante para palco e estúdio.
>
> Também há um ukulele barítono Kala (não é violão) por R$ 599,00, caso tenha interesse nesse tipo de instrumento.
>
> Gostaria de saber mais sobre algum desses modelos ou prefere que eu busque outras opções?

<sub>2 model request(s); tools: `search_catalog`; sources: catalog.</sub>

**Customer:** E se eu pagar no PIX, muda alguma coisa?

**Agent:**

> Não consegui concluir sua consulta agora. Você pode tentar novamente ou pedir atendimento humano.

<sub>3 model request(s); tools: `lookup_public_policy`, `search_catalog`; sources: catalog, policy.</sub>

**Check:** Prices, descriptions and stock match `products.csv`. Gap: the search returns 5 items per page and the model did not say more existed, so Yamaha C40 Nylon Natural (R$ 599,90) and Giannini GN-15 Nylon Cedr Natural (R$ 689,00), both under R$ 1.000, were omitted. The second turn consulted policy and catalog, but the evidence guard rejected the drafted answers and the customer received the fixed safe-failure reply.

## 2. Store address and hours

Recorded 2026-11-04T15:01:59Z with `interact_chat`.

**Customer:** Qual o endereço da loja?

**Agent:**

> O endereço da nossa loja é: Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333.

<sub>3 model request(s); tools: `lookup_public_policy`; sources: policy.</sub>

**Customer:** E no sábado, vocês abrem que horas?

**Agent:**

> No sábado, a loja abre das 09:00 às 13:00. Se precisar de mais alguma informação, é só perguntar!

<sub>2 model request(s); tools: `lookup_public_policy`; sources: policy.</sub>

**Check:** The address matches manual §1.2 (p. 2) and the Saturday hours match §2 (p. 2).

## 3. Price, then the return policy

Recorded 2026-11-04T15:04:14Z with `interact_chat`.

**Customer:** Quanto custa o Takamine GD20?

**Agent:**

> O Takamine GD20 Dreadnought Natural custa R$ 2.199,00. É um violão dreadnought com tampo sólido em cedro, ideal para fingerstyle, com timbre quente e definido. Se quiser saber mais detalhes ou se está disponível na forma de pagamento que você prefere, é só me avisar!

<sub>2 model request(s); tools: `search_catalog`; sources: catalog.</sub>

**Customer:** Se eu comprar pelo site e me arrepender, posso devolver?

**Agent:**

> Sim, você pode devolver! De acordo com nossa política de devolução para compras online, o cliente tem até 7 dias corridos após receber o produto para solicitar a devolução, sem precisar dar uma justificativa. O produto precisa estar na embalagem original, sem sinais de uso e com todos os acessórios e manuais.
>
> O reembolso será feito na mesma forma de pagamento que você usou para comprar, em até 10 dias úteis. Além disso, o frete da devolução é por conta da loja nesse caso.
>
> Se tiver mais alguma dúvida ou precisar de ajuda com o processo, estou à disposição!

<sub>2 model request(s); tools: `lookup_public_policy`; sources: policy.</sub>

**Check:** Price and description match `products.csv` (product 95). The return answer applies §4.1 (p. 4): 7 calendar days after receipt, original packaging, return shipping paid by the store, refund within 10 business days.

## 4. Own order status, then a return request (non-trivial)

Recorded 2026-11-04T15:06:13Z with `interact_chat --sender 5567996547821`.

**Customer:** Oi, qual o status do meu pedido?

**Agent:**

> Olá! Seu pedido número 8 está com o status de **enviado** (shipped). Ele foi realizado em 15 de fevereiro de 2026.
>
> Se precisar de mais detalhes sobre esse pedido ou tiver alguma dúvida, é só avisar!

<sub>2 model request(s); tools: `list_own_orders`; sources: orders.</sub>

**Customer:** Ele chegou e me arrependi da compra. Posso devolver?

**Agent:**

> Sim, você pode devolver! De acordo com nossa política de devolução, o cliente tem até 7 dias corridos após receber o produto para solicitar a devolução, sem precisar dar uma justificativa.
>
> Para que a devolução seja aceita, o produto precisa estar na embalagem original, sem sinais de uso e com todos os acessórios e manuais. O frete de volta será por nossa conta. O reembolso será feito no mesmo meio de pagamento original em até 10 dias úteis.
>
> Precisa de ajuda para iniciar o processo de devolução?

<sub>2 model request(s); tools: `lookup_public_policy`; sources: policy.</sub>

**Check:** The test sender matches synthetic customer 2 (Ana Carolina Ferreira), and the agent read only her orders: order 8, `shipped`, placed 15/02/2026, matches `orders.csv`. It did not offer the available tracking code or delivery estimate. The return answer applies §4.1 correctly.

## 5. Out-of-scope request, then a recommendation

Recorded 2026-11-04T15:08:02Z with `interact_chat`.

**Customer:** Vocês vendem pizza?

**Agent:**

> Esse assunto foge do que o Empório da Música atende: trabalhamos com instrumentos e acessórios musicais. Posso ajudar com algum produto, preço ou política da loja?

<sub>3 model request(s); tools: `search_catalog`; sources: none.</sub>

**Customer:** Tá bom. Então me indica um violão bom pra iniciante?

**Agent:**

> Que legal que você está pensando em começar a tocar violão! Temos algumas opções excelentes para iniciantes. Aqui estão dois modelos que são muito bem avaliados por quem está começando:
>
> 1. **Tagima Memphis AC-39 Nylon Natural** - R$ 429,90
>    - Cordas de nylon (mais fáceis de tocar no início)
>    - Corpo leve e confortável
>    - Perfeito para quem está começando
>
> 2. **Rozini RC-104 Nylon Estudante** - R$ 459,90
>    - Feito com madeiras nacionais
>    - Acabamento caprichado
>    - Preço acessível para iniciantes
>
> Você prefere violão de cordas de nylon (mais suave para os dedos) ou de aço? Também tem um ukulele barítono Kala se quiser algo diferente!
>
> Qual desses te chama mais a atenção? Posso te dar mais detalhes sobre algum deles.

<sub>3 model request(s); tools: `search_catalog`, `search_catalog`; sources: catalog.</sub>

**Check:** The out-of-scope reply is the application's fixed text. In the recommendation, prices and features match the catalog, but "muito bem avaliados por quem está começando" has no basis in the data (there are no reviews); the evidence guard does not detect this kind of claim.

