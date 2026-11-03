# Recorded interactions

These five conversations are a Markdown rendering of [the existing JSON record](demo-interactions.json). The model responses are scripted; the webhook, worker, source lookups, pricing and mock Meta transport run through the application. Acceptance and delivery are simulated. These records do not establish live LLM answer quality.

Reproduce with `uv run --env-file .env python manage.py demo_chat` after [setup](../README.md#running-the-project). The recorded source snapshot is `bf9e3a728f4ab12f8a82b7b18d6b4f8001901eb512115eda9e7906e21f773742`; later source changes require new records.

## 1. Catalog lookup

**Customer:** Quanto custa o Takamine GD20 e ele está disponível?

**Agent:** Takamine GD20 Dreadnought Natural está disponível por R$ 2199,00.

Evidence: catalog; 2 model request(s), 1 tool execution(s); outcome `answer`; mock acceptance and delivery confirmed.

## 2. Store hours

**Customer:** Qual é o horário de funcionamento?

**Agent:** 2. Horário de Funcionamento O atendimento presencial na loja segue os horários abaixo. O atendimento via WhatsApp segue o mesmo horário, com respostas automáticas fora do expediente. Dia Horário Segunda a Sexta-feira 09:00 às 18:00 Sábado 09:00 às 13:00 Domingo e Feriados Fechado Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário pode ser estendido.

Evidence: policy; 2 model request(s), 1 tool execution(s); outcome `answer`; mock acceptance and delivery confirmed.

## 3. Availability and return policy

**Customer:** O Takamine GD20 está disponível e posso devolver se me arrepender?

**Agent:** Takamine GD20 Dreadnought Natural está disponível por R$ 2199,00. 4.1 Direito de Arrependimento (Compras Online) O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento do produto, sem necessidade de justificativa. • O produto deve estar em sua embalagem original, sem sinais de uso, com todos os acessórios e manuais. • O reembolso será realizado na mesma forma de pagamento original em até 10 dias úteis. • O frete de devolução é por conta da loja em caso de arrependimento.

Evidence: catalog, policy; 2 model request(s), 2 tool execution(s); outcome `answer`; mock acceptance and delivery confirmed.

## 4. Payment-aware budget

**Customer:** Quero um violão de nylon até R$ 1.000 pagando integralmente por PIX.

**Agent:** Para pagamento integral por PIX, Tagima Memphis AC-39 Nylon Natural fica em R$ 408,41. 6.2 Regras de Promoções Cumulatividade: promoções não são cumulativas. O desconto de PIX (5%) não se aplica sobre preços já promocionais. Estoque: promoções estão sujeitas à disponibilidade de estoque. Produtos esgotados durante a promoção não geram direito a rain check (reserva de preço). 3. Formas de Pagamento Aceitamos as seguintes formas de pagamento para compras presenciais e online: Forma Condições Observações PIX Pagamento à vista 5% de desconto sobre o preço de tabela Cartão de Débito Pagamento à vista Todas as bandeiras aceitas Cartão de Crédito Até 12x sem juros Parcela mínima de R$ 100,00 Boleto Bancário Pagamento à vista Compensação em até 3 dias úteis

Evidence: catalog, policy; 2 model request(s), 2 tool execution(s); outcome `answer`; mock acceptance and delivery confirmed.

## 5. Human handoff

**Customer:** Quero falar com uma pessoa do atendimento.

**Agent:** Encaminhei sua conversa para atendimento humano.

Evidence: none; 1 model request(s), 0 tool execution(s); outcome `handoff`; mock acceptance and delivery confirmed.
