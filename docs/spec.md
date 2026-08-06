# Spec: Sistema de Importação, Reconciliação e Gestão de NF-e

> Spec-Driven Development. Nível 2 (spec-anchored). Esta spec é a fonte única de
> verdade. Se divergir do código, a spec está certa (ou precisa ser atualizada
> explicitamente). Data: 05/08/2026.

---

## User story principal

Como **auxiliar administrativo ou contador**, quero **importar automaticamente
todas as notas fiscais eletrônicas que minha empresa recebeu da Receita Federal,
reconciliá-las com pedidos de compra e recebimentos, e gerar lançamentos
contábeis automáticos**, para **eliminar trabalho manual, detectar divergências
antes do pagamento e preparar dados para o SPED**.

---

## Escopo

### Dentro do escopo (MVP)

1. Importação de NF-e via NFeDistribuicaoDFe (notas recebidas pelo CNPJ)
2. Parsing de XML com nfelib, validação contra XSD oficial
3. Persistência em PostgreSQL (schema completo normalizado)
4. Manifestação automática do destinatário (ciência da emissão)
5. Reconciliação three-way matching (pedido + recebimento + NF-e)
6. Detecção de divergências com tolerâncias configuráveis
7. Dashboard web (FastAPI + Jinja2) com notas importadas, divergências, status
8. Geração de lançamentos contábeis por tipo de operação (CFOP)
9. Exportação CSV/Excel para ERP externo
10. Mock SEFAZ local para testes sem certificado

### Fora do escopo (fase 2)

1. Emissão de NF-e (vai por API comercial, integração futura)
2. NFS-e municipal (cada cidade tem padrão diferente, fase 2)
3. CT-e e MDF-e (fase 2)
4. Geração direta de arquivos SPED (ECD, ECF, EFD)
5. Integração com ERP externo via API (SAP, Oracle, Odoo)
6. Matching com IA (embeddings para casos ambíguos)
7. Multi-empresa (MVP é single-tenant)

---

## Arquitetura

```
                    [Receita Federal]
                    NFeDistribuicaoDFe
                          |
                          v
              +-----------+-----------+
              |  Importador DF-e      |
              |  (erpbrasil.edoc)     |
              |  certificado A1       |
              +-----------+-----------+
                          |
                          v
              +-----------+-----------+
              |  Parser XML           |
              |  (nfelib + xsdata)    |
              |  validação XSD        |
              +-----------+-----------+
                          |
                          v
              +-----------+-----------+
              |  PostgreSQL 16        |
              |  schema NF-e completo |
              +-----------+-----------+
                          |
              +-----------+-----------+
              |  Motor de             |
              |  Reconciliação        |
              |  (three-way matching) |
              +-----------+-----------+
                          |
                          v
              +-----------+-----------+
              |  Gerador de           |
              |  Lançamentos Contábeis|
              |  (CFOP -> débito/créd)|
              +-----------+-----------+
                          |
                          v
              +-----------+-----------+
              |  Dashboard Web        |
              |  (FastAPI + Jinja2)   |
              +-----------+-----------+
```

### Stack técnica

| Camada | Tecnologia | Versão pinada |
|---|---|---|
| Linguagem | Python | 3.12 |
| Parsing XML | nfelib | 2.5.2 |
| Comunicação SEFAZ | erpbrasil.edoc | 3.1.1 |
| Data binding | xsdata | (dependência do nfelib) |
| Banco principal | PostgreSQL | 16-alpine |
| Cache/fila | Redis | 7-alpine |
| Backend | FastAPI | a pinar |
| ORM | SQLAlchemy | a pinar |
| Migrações | Alembic | a pinar |
| Testes | pytest + pytest-asyncio | a pinar |
| Container | Docker Compose | 3.8 |
| Mock SEFAZ | próprio (Python) | n/a |
| Dashboard | FastAPI + Jinja2 | n/a |

---

## Critérios de aceitação (testáveis)

### Módulo 1: Importação DF-e

1. [ ] Dado um CNPJ com certificado A1 válido, quando o importador consulta
   NFeDistribuicaoDFe, então recebe lote de até 50 documentos por chamada.

2. [ ] Dado um NSU inicial, quando o importador consulta, então retorna
   documentos com NSU sequencial e armazena o último NSU em `dfe_importacao`.

3. [ ] Dado um resumo de NF-e (sem XML completo), quando o sistema envia
   evento de Ciência da Emissão, então a próxima consulta retorna o XML completo.

4. [ ] Dado uma chamada à Receita que retorna erro (SEFAZ offline), quando o
   sistema recebe timeout, então retira com backoff exponencial (3 tentativas,
   2s, 4s, 8s) e registra em log.

5. [ ] Dado uma NF-e já importada (mesma chave de acesso), quando o sistema
   tenta reimportar, então ignora sem duplicar (idempotência por chave de 44
   dígitos).

6. [ ] Dado o mock SEFAZ local ativo, quando o importador consulta, então
   recebe documentos de teste sem precisar de certificado real.

### Módulo 2: Parsing e persistência

7. [ ] Dado um XML de NF-e válido (leiaute 4.00, PL_010b), quando o parser
   processa com nfelib, então extrai: emitente, destinatário, itens, tributos,
   pagamentos, total.

8. [ ] Dado um XML com campos de IBS/CBS (NT 2025.002 v1.50), quando o parser
   processa, então extrai o grupo UB (alíquota, base de cálculo, valor IBS/CBS).

9. [ ] Dado um XML inválido (contra XSD), quando o parser valida, então
   rejeita com lista de erros de validação e não persiste.

10. [ ] Dado uma NF-e parseada, quando o sistema persiste, então insere nas
    tabelas: nfe, participante (emitente e destinatário), nfe_item,
    nfe_tributo, nfe_pagamento. Cada item fica vinculado à NF-e.

11. [ ] Dado uma NF-e cancelada (evento de cancelamento importado), quando o
    sistema processa o evento, então atualiza `status_autorizacao` para
    'cancelada' e remove de reconciliações pendentes.

### Módulo 3: Reconciliação

12. [ ] Dado uma NF-e de entrada sem pedido de compra vinculado, quando o
    motor de reconciliação executa, então marca status 'pending' em
    `reconciliacao`.

13. [ ] Dado uma NF-e com valor total igual ao pedido de compra (mesmo CNPJ,
    mesma data ±3 dias), quando o motor executa, então faz match
    determinístico e marca status 'matched'.

14. [ ] Dado uma NF-e com divergência de preço até 2% (tolerância
    configurável), quando o motor executa, então marca status 'matched' com
    aviso de divergência aceita.

15. [ ] Dado uma NF-e com divergência de preço acima de 2%, quando o motor
    executa, então marca status 'divergent' e registra divergências em JSONB.

16. [ ] Dado uma NF-e com divergência de quantidade acima de 5%, quando o
    motor executa, então marca status 'divergent' e registra detalhe em
    `reconciliacao.divergencias`.

17. [ ] Dado um three-way matching (pedido + recebimento + NF-e) com todos os
    valores coerentes, quando o motor executa, então marca status 'matched'
    e tipo_match 'three_way'.

18. [ ] Dado uma NF-e sem recebimento vinculado (serviço, não mercadoria),
    quando o motor executa, então faz two-way matching (pedido + NF-e) e
    marca tipo_match 'two_way'.

### Módulo 4: Lançamentos contábeis

19. [ ] Dado uma NF-e de compra de mercadoria para revenda (CFOP 1102),
    quando o gerador executa, então gera débito em Estoque (1.1.3.x) e
    crédito em Fornecedores (2.1.x).

20. [ ] Dado uma NF-e de compra de ativo imobilizado (CFOP 1551), quando o
    gerador executa, então gera débito em Imobilizado (1.2.x) e crédito em
    Fornecedores (2.1.x).

21. [ ] Dado uma NF-e com ICMS destacado, quando o gerador executa, então
    gera lançamento de ICMS a recuperar (1.1.5.x) creditando Estoque.

22. [ ] Dado uma NF-e cancelada, quando o gerador executa, então estorna o
    lançamento contábil anterior (lançamento de estorno).

23. [ ] Dado um plano de contas referencial configurado, quando o gerador
    executa, então mapeia cada lançamento para o código referencial da
    Receita (Registro I051 da ECD).

### Módulo 5: Dashboard

24. [ ] Dado notas importadas no banco, quando o usuário acessa o dashboard,
    então vê: total de notas, notas pendentes, notas reconciliadas, notas com
    divergência, valor total importado.

25. [ ] Dado notas com divergência, quando o usuário clica em uma divergência,
    então vê o detalhe: NF-e vs pedido, campo divergente, valor esperado,
    valor encontrado, diferença.

26. [ ] Dado um período selecionado, quando o usuário filtra, então vê apenas
    notas daquele período com totais recalculados.

27. [ ] Dado notas importadas, quando o usuário clica em "Exportar CSV",
    então baixa arquivo com todas as notas e itens para Excel.

### Módulo 6: Mock SEFAZ para testes

28. [ ] Dado o mock SEFAZ ativo (variável de ambiente MOCK_SEFAZ=true), quando
    o importador consulta, então recebe 10 NF-e de exemplo do pool mock.

29. [ ] Dado o mock SEFAZ ativo, quando o sistema envia manifestação, então
    recebe sucesso instantâneo e o XML completo fica disponível na próxima
    consulta.

30. [ ] Dado o mock SEFAZ ativo, quando o sistema consulta novamente com o
    último NSU, então recebe "nenhum documento novo" (NSU já consumido).

---

## Contrato / Interface

### Variáveis de ambiente

```
# Banco de dados
DATABASE_URL=postgresql://user:pass@localhost:5432/nfe_db

# Cache
REDIS_URL=redis://localhost:6379/0

# Certificado digital (produção)
CERTIFICADO_A1_PATH=/path/to/certificado.pfx
CERTIFICADO_A1_SENHA=senha_secreta
CNPJ_CONSULTADO=12345678000190

# Ambiente SEFAZ
SEFAZ_AMBIENTE=homologacao  # homologacao | producao
MOCK_SEFAZ=true             # true = usa mock local, false = usa SEFAZ real

# Rate limit
SEFAZ_RATE_LIMIT=3          # máximo 3 consultas/segundo

# Tolerâncias de reconciliação
TOLERANCIA_PRECO_PERCENT=2.0
TOLERANCIA_QTD_PERCENT=5.0
TOLERANCIA_DATA_DIAS=3
```

### Endpoints da API (FastAPI)

```
GET  /api/notas                    # lista paginada de NF-e importadas
GET  /api/notas/{chave}            # detalhe de uma NF-e específica
GET  /api/notas/{chave}/xml        # XML original da NF-e
GET  /api/notas/{chave}/itens      # itens da NF-e
GET  /api/reconciliacoes           # lista de reconciliações com status
GET  /api/reconciliacoes/{id}      # detalhe de uma reconciliação
POST /api/reconciliacoes/{id}/resolver  # resolver divergência manualmente
GET  /api/lancamentos              # lançamentos contábeis gerados
GET  /api/importacao/status        # status da última importação DF-e
POST /api/importacao/executar      # disparar importação manual
GET  /api/dashboard                # métricas agregadas para dashboard
GET  /api/export/csv               # exportar todas as notas em CSV
```

### Schema do banco (tabelas principais)

```sql
-- Tabelas definidas na pesquisa-sistema-nfe-reconciliacao.md, Parte 2.1
-- 8 tabelas: nfe, participante, nfe_item, nfe_tributo, nfe_pagamento,
-- nfe_evento, reconciliacao, dfe_importacao
-- Mais tabelas de domínio: pedido_compra, recebimento, plano_contas,
-- lancamento_contabil
```

---

## Restrições

1. **NÃO** persistir XML sem validar contra XSD oficial (Pacote 010b v1.30).
2. **NÃO** importar nota duplicada (chave de acesso é única, 44 dígitos).
3. **NÃO** exceder 3 consultas/segundo à SEFAZ (rate limit oficial).
4. **NÃO** armazenar senha do certificado em texto plano. Usar variável de
   ambiente ou cofre, nunca hardcodar.
5. **NÃO** fazer lançamento contábil sem CFOP válido e plano de contas mapeado.
6. **NÃO** permitir reconciliação manual sem trilha de auditoria (quem, quando,
   justificativa).
7. **NÃO** exibir dados sensíveis em logs (CNPJ completo, valores em logs de
   erro usar mascaramento).
8. **NÃO** suportar mais de 1 empresa por instância no MVP (single-tenant).
9. **NÃO** emitir NF-e no MVP (emissão vai por API comercial na fase 2).
10. **NÃO** processar NFS-e municipal no MVP (padrões variam por cidade).

---

## Decisões arquiteturais

### 1. Python em vez de Node/PHP/Java

**Decisão**: Python 3.12 com FastAPI.
**Por quê**: nfelib e erpbrasil.edoc são Python, open source, confiáveis
(auditados). O ecossistema fiscal Python é o mais maduro no Brasil (Akretion,
erpbrasil). FastAPI é async, tipado, com documentação automática (OpenAPI).

### 2. Híbrido: open source para importação, comercial para emissão

**Decisão**: importação de NF-e com nfelib + erpbrasil.edoc (open source).
Emissão de NF-e via API comercial (NFE.io ou BrasilNFe) na fase 2.
**Por quê**: importação é fluxo de leitura, sem risco fiscal. Emissão exige
responsabilidade fiscal direta, melhor terceirizar para API que assume o risco.
Custo de emissão: ~R$ 0,10 a R$ 0,50 por nota.

### 3. PostgreSQL em vez de MongoDB

**Decisão**: PostgreSQL 16 com schema normalizado.
**Por quê**: dados fiscais são relacionais por natureza (NF-e tem itens,
itens têm tributos, tributos têm tipos). ACID é obrigatório para contabilidade.
JSONB para campo de divergências (flexível) sem perder o resto relacional.

### 4. Mock SEFAZ próprio em vez de usar sefaz-mocked (Node.js)

**Decisão**: refazer o mock SEFAZ em Python.
**Por quê**: sefaz-mocked é Node.js (outra linguagem, outra dependência).
O mock é trivial (4 endpoints que retornam XML fixo). Em Python, integra com
o resto do sistema e não adiciona dependência de supply chain.

### 5. Reconciliação determinística primeiro, IA depois

**Decisão**: MVP usa matching determinístico (CNPJ + valor + data) e fuzzy
(tolerância percentual). IA (embeddings) fica para fase 2.
**Por quê**: determinístico resolve 80% dos casos. IA adiciona complexidade,
custo de inferência e opacidade. Para MVP, transparência é mais importante
que cobertura.

### 6. Single-tenant no MVP

**Decisão**: uma empresa por instância.
**Por quê**: multi-tenant adiciona complexidade (isolamento de dados, RBAC,
faturamento). MVP precisa validar o fluxo, não escalar. Fase 2 adiciona
multi-tenant se fizer sentido.

### 7. FastAPI + Jinja2 em vez de React/Vue

**Decisão**: dashboard server-rendered com Jinja2.
**Por quê**: MVP não precisa de SPA. Jinja2 é mais simples, não exige build
frontend, não adiciona dependências npm. Se a interface precisar de
interatividade complexa depois, migra para React na fase 2.

---

## Estratégia de testes (sem certificado real)

### Camada 1: Unit tests com XMLs de exemplo

Usar XMLs reais de exemplo do próprio nfelib:
`nfelib/nfe/samples/v4_0/leiauteNFe/NFe35200159594315000157550010000000012062777161.xml`

Testar: parsing, extração de campos, persistência, validação XSD.

### Camada 2: Mock SEFAZ local (próprio)

Servidor Python (FastAPI ou Flask) que simula:
- `NFeDistribuicaoDFe`: retorna pool de 10 NF-e de exemplo, com NSU sequencial
- `RecepcaoEvento`: retorna sucesso de manifestação
- `NFeStatusServico`: retorna "serviço em operação"

Pool de NF-e mock: 10 XMLs variados (entrada, saída, com IBS/CBS, cancelada,
com divergência de valor, com divergência de quantidade).

### Camada 3: Gerador sintético de NF-e

Função que gera NF-e XML sintéticas com nfelib (montar do zero com
dataclasses), variando:
- Número de itens (1 a 50)
- Valores (com e sem divergência vs pedido)
- CNPJs de fornecedores (10 diferentes)
- CFOPs (5 tipos diferentes)
- Com e sem IBS/CBS
- Com e sem evento de cancelamento

Gerar 1000 NF-e para testar volume, reconciliação e dashboard.

### Camada 4: SEFAZ homologação (opcional, exige CNPJ)

Ambiente oficial de testes da Receita:
`https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx`

Exige certificado A1 de homologação. Cada SEFAZ estadual emite certificados
de teste para desenvolvedores. Requer CNPJ (mesmo que MEI).

### Camada 5: Sandbox API comercial (fase 2, emissão)

NFE.io e BrasilNFe têm ambiente sandbox. Notas emitidas em sandbox não têm
validade fiscal. Para testar emissão quando a fase 2 for implementada.

### Cobertura de testes

| Módulo | Cobertura mínima | Tipo |
|---|---|---|
| Parser XML | 95% | unit + XMLs de exemplo |
| Persistência | 90% | integration com PostgreSQL em Docker |
| Importador DF-e | 85% | integration com mock SEFAZ |
| Reconciliação | 90% | unit com gerador sintético |
| Lançamentos contábeis | 90% | unit com CFOPs variados |
| Dashboard | 70% | integration com banco de teste |
| Mock SEFAZ | 90% | unit + integration |

---

## Cronograma de implementação (MVP)

### Fase 1: Fundação (semana 1)

1. Setup do projeto: Docker Compose com PostgreSQL + Redis
2. Schema do banco (8 tabelas principais + 4 de domínio)
3. Migrações com Alembic
4. Modelos SQLAlchemy
5. Mock SEFAZ em Python

### Fase 2: Importação (semana 2)

6. Importador DF-e com erpbrasil.edoc
7. Parser XML com nfelib
8. Validação XSD
9. Persistência com deduplicação por chave de acesso
10. Manifestação automática do destinatário
11. Rate limit com Redis

### Fase 3: Reconciliação (semana 3)

12. Tabelas de pedido_compra e recebimento
13. Motor de matching determinístico
14. Motor de matching fuzzy (tolerâncias)
15. Detecção de divergências
16. Trilha de auditoria

### Fase 4: Contabilidade (semana 4)

17. Plano de contas referencial
18. Gerador de lançamentos por CFOP
19. Estorno automático para notas canceladas
20. Exportação para ECD (formato)

### Fase 5: Dashboard (semana 5)

21. Endpoints da API
22. Templates Jinja2
23. Filtros por período, status, fornecedor
24. Exportação CSV/Excel
25. Métricas agregadas

### Fase 6: Testes e polish (semana 6)

26. Gerador sintético de 1000 NF-e
27. Testes de integração completos
28. Documentação de instalação
29. Docker Compose de produção
30. Backup e restore

---

## Dependências e pinning

```requirements.txt
# Parsing XML fiscal
nfelib==2.5.2
xsdata==24.7  # dependência do nfelib, pinada explicitamente

# Comunicação SEFAZ
erpbrasil.edoc==3.1.1

# Backend
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.32
alembic==1.13.2
psycopg2-binary==2.9.9
redis==5.0.8
jinja2==3.1.4
python-multipart==0.0.9

# Testes
pytest==8.3.2
pytest-asyncio==0.23.8
pytest-cov==5.0.0
httpx==0.27.0  # para testar a própria API

# Utilitários
python-dotenv==1.0.1
pydantic==2.8.2
tenacity==9.0.0  # retry com backoff
```

Todas as versões pinadas. Lockfile com hashes gerado por `pip-compile
--generate-hashes`. Commitar no repositório.

---

## Status

- [x] Spec escrita
- [x] Critérios de aceitacao testáveis (30 critérios)
- [ ] Implementação
- [ ] Testes passando
- [ ] Spec atualizada (nível 2: manter viva com o código)

---

## Próximos passos

1. Confirmar esta spec com o usuário
2. Criar estrutura do projeto e Docker Compose
3. Implementar fase 1 (fundação + mock SEFAZ)
4. Seguir com TDD: cada critério de aceitação vira um teste que falha primeiro
