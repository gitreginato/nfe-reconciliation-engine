# Plano de demonstração para entrevista

## Objetivo

Demonstrar um sistema próprio de reconciliação NF-e e lançamentos contábeis sem
depender de certificados, e-CAC, SEFAZ real ou dados da empresa.

A demonstração usa exclusivamente:

- mock SEFAZ local;
- dados sintéticos;
- PostgreSQL local;
- regras contábeis explícitas;
- testes automatizados.

## Mensagem de abertura

> Este é um MVP demonstrável. Ele usa um mock da SEFAZ para não depender de
> certificados ou dados da empresa. O fluxo foi separado em importação,
> reconciliação, lançamento e auditoria. A integração real entra depois que a
> empresa define seus acessos e regras internas.

## Sequência da demonstração

### 1. Mostrar o problema

Explique que uma nota recebida precisa ser comparada com:

```text
NF-e + pedido de compra + recebimento
```

A saída pode ser:

- `matched`, sem divergência;
- `divergent`, com diferença registrada;
- `pending`, sem pedido ou sem informação suficiente.

### 2. Subir o ambiente

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Verifique:

```bash
docker compose -f docker/docker-compose.yml ps
```

Não mostrar senhas ou conteúdo do `.env` na tela.

### 3. Mostrar os testes

```bash
docker exec contabilidade-app python -m pytest -q
```

Resultado esperado no estado atual:

```text
162 passed
```

Se o ambiente da entrevista estiver lento, execute primeiro:

```bash
docker exec contabilidade-app python -m pytest \
  tests/unit/test_validadores.py \
  tests/unit/test_gate_contracts.py -q
```

### 4. Importar notas sintéticas

```bash
curl -s -X POST http://localhost:8000/api/importacao/executar
```

Mostrar que o retorno apresenta:

- notas consultadas;
- notas importadas;
- duplicadas;
- erros;
- canceladas.

O mock inclui compras normais, ativo, serviço, devolução, frete, desconto,
ICMS-ST e impostos recuperáveis.

### 5. Mostrar idempotência

Execute a importação novamente ou use o teste específico. Explique que a chave
de acesso e o NSU impedem duplicidade.

### 6. Criar pedidos de demonstração

```bash
curl -s -X POST http://localhost:8000/api/reconciliacao/popular-pedidos
```

### 7. Executar reconciliação

```bash
curl -s -X POST http://localhost:8000/api/reconciliacao/executar
```

Mostre uma divergência e explique:

- valor esperado;
- valor encontrado;
- diferença;
- percentual;
- tolerância configurada;
- tipo de matching.

### 8. Gerar lançamentos

```bash
curl -s -X POST http://localhost:8000/api/lancamentos/executar
```

Mostre que:

- nota divergente não gera lançamento;
- nota matched gera débito e crédito;
- nota cancelada gera estorno;
- nota sintética não é tratada como documento fiscal autorizado.

### 9. Mostrar a validação fiscal

Demonstre que o sistema rejeita:

- chave com DV incorreto;
- CFOP inexistente;
- CFOP de mercadoria com NCM de serviço;
- total incompatível com os itens;
- protocolo fora do formato.

Exemplos de endpoints:

```bash
curl -i http://localhost:8000/api/notas/123
curl -i "http://localhost:8000/api/export/ecd?data_inicio=2024-01-01&data_fim=2026-01-01"
```

### 10. Mostrar dashboard e exportação

```bash
curl -s http://localhost:8000/api/dashboard
curl -s "http://localhost:8000/api/notas?page=1&page_size=5"
curl -I "http://localhost:8000/api/export/csv?tipo=lancamentos"
```

Na interface web, mostrar:

- origem da nota;
- protocolo;
- status de autorização;
- divergências;
- paginação;
- exportações.

### 11. Mostrar ECD

```bash
curl -I "http://localhost:8000/api/export/ecd?data_inicio=2026-07-01&data_fim=2026-07-31"
```

Explique corretamente:

- o MVP gera uma base ECD estruturada;
- a validação definitiva depende do PVA e dos dados/plano da empresa;
- não afirmar que o arquivo está pronto para transmissão sem essa etapa.

## Roteiro de perguntas para a entrevista

Se perguntarem sobre integração real, responder:

1. “O mock foi usado para demonstrar o fluxo sem depender de certificado ou
   credencial da empresa.”
2. “A integração real será feita em homologação, por UF, com certificado e
   procuração fornecidos pela empresa.”
3. “O certificado não deve ficar no Git, no Dockerfile ou no `.env` versionado.”
4. “O plano separa consulta, validação, reconciliação, lançamento e transmissão.”
5. “A regra fiscal final depende do regime, plano de contas e políticas internas.”
6. “O RAG será auxiliar documental, não substituirá o motor determinístico nem
   decidirá transmissão sozinho.”

## O que destacar tecnicamente

- TDD: testes para entradas válidas, inválidas e limites.
- SDD: critérios de aceitação escritos antes do incremento.
- ODD: logs, métricas e contrato de observabilidade.
- Segurança: validação server-side, ORM, máscara de dados e rate limit.
- Idempotência: reprocessar não duplica notas ou reconciliações.
- Partida dobrada: cada lançamento tem débito e crédito.
- Rastreabilidade: origem, XML, NSU, protocolo e eventos.
- Arquitetura substituível: mock hoje, SEFAZ real depois.

## O que não afirmar

Não afirmar que o MVP:

- está autorizado a transmitir em produção;
- substitui contador ou advogado;
- tem todos os CFOPs, NCMs e CSTs oficiais;
- foi validado no PVA;
- implementa assinatura ICP-Brasil completa;
- integra o ERP da empresa;
- conhece as regras internas da empresa;
- usa dados reais da organização.

## Evidências para levar

- `docs/spec-testes.md`;
- `docs/observability-contract.md`;
- `docs/relatorio-gates.md`;
- `docs/relatorio-lacunas-contabeis-legislativas.md`;
- `docs/checklist-lado-empresa.md`;
- `docs/plano-acessos-e-rag.md`;
- `.devin/skills/contabil-gate/SKILL.md`;
- `.devin/skills/legislativo-gate/SKILL.md`;
- `tests/unit/test_validadores.py`;
- `tests/integration/test_cenarios_reais.py`.

## Critério de sucesso da demonstração

A pessoa entrevistadora deve conseguir ver, sem acesso governamental:

1. uma nota entrando;
2. uma divergência sendo explicada;
3. um lançamento sendo gerado;
4. um cancelamento sendo estornado;
5. uma entrada inválida sendo rejeitada;
6. um relatório sendo exportado;
7. testes provando que o fluxo não é apenas uma tela estática.
