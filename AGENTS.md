# AGENTS.md - Projeto Contabilidade

> Guia para agentes de IA (Devin, Claude, etc.) que forem trabalhar neste
> projeto. Carregado no início de toda sessão neste diretório.

## Contexto do projeto

Sistema de importação, reconciliação e gestão de notas fiscais eletrônicas
(NF-e). Importa notas da Receita Federal via NFeDistribuicaoDFe, faz
reconciliação three-way matching com pedidos de compra, gera lançamentos
contábeis automáticos, calcula tributos determinísticos, apura impostos
mensalmente, manifesta destinatário em lote, exporta ECD no layout oficial
e exibe em dashboard web.

Documentação completa:
- `docs/guia-simples.md`: guia explicado de forma simples (para não-técnico).
- `docs/spec.md`: especificação técnica com 30 critérios de aceitação.
- `docs/kanban.md`: quadro de tarefas (75 tarefas, 7 fases).
- `docs/plano-demo-entrevista.md`: roteiro de demonstração para entrevista.
- `docs/checklist-lado-empresa.md`: responsabilidades que dependem da empresa.
- `docs/plano-acessos-e-rag.md`: plano de integração com APIs governamentais e RAG.
- `docs/relatorio-lacunas-contabeis-legislativas.md`: 47 lacunas identificadas.
- `docs/observability-contract.md`: contrato de telemetria (ODD).
- `docs/spec-testes.md`: especificação dos testes.

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic
- PostgreSQL 16, Redis 7
- nfelib 2.5.2 (parsing XML fiscal), erpbrasil.edoc 3.1.1 (comunicação SEFAZ)
- Docker Compose para dev e prod
- pytest para testes, Jinja2 para dashboard

## Comandos

```bash
# Subir ambiente de desenvolvimento
docker compose -f docker/docker-compose.yml up -d

# Rodar migrações do banco
docker compose exec app alembic upgrade head

# Rodar testes
docker exec contabilidade-app python -m pytest

# Rodar testes com cobertura
docker exec contabilidade-app python -m pytest --cov=src --cov-report=term-missing

# Rodar apenas testes unitários
docker exec contabilidade-app python -m pytest tests/unit/

# Rodar apenas testes de integração
docker exec contabilidade-app python -m pytest tests/integration/

# Rodar mock SEFAZ (separado)
docker compose -f docker/docker-compose.test.yml up sefaz-mock

# Parar tudo
docker compose -f docker/docker-compose.yml down

# Rebuild (quando mudar requirements.txt)
docker compose -f docker/docker-compose.yml up -d --build

# Atalhos do Makefile
make up        # sobe containers
make test      # roda todos os testes
make test-unit # só testes unitários
make test-cov  # testes com cobertura (mínimo 70%)
make lint      # ruff check
make down      # para containers
```

## Convenções

- **Dependências**: sempre pinar versão exata em requirements.txt. Nunca usar
  `latest`, `*`, ou ranges. Rodar `/supply-chain` antes de adicionar nova.
- **Banco**: todas as mudanças de schema passam por migração Alembic. Nunca
  editar schema.sql diretamente após a primeira migração.
- **Testes**: TDD. Cada critério de aceitação da spec vira um teste que falha
  primeiro, depois implementa, depois refatora.
- **Mocks**: usar mock SEFAZ local (MOCK_SEFAZ=true) para todos os testes de
  importação. Nunca chamar SEFAZ real em testes.
- **Segredos**: nunca hardcodar CNPJ, senha de certificado, ou qualquer dado
  sensível. Sempre variável de ambiente com `.env` (que não é commitado).
- **Logs**: nunca logar CNPJ completo, valores em produção, ou senha. Usar
  mascaramento (ex.: `12.345.678/****-**`).
- **Queries**: sempre SQLAlchemy com parâmetros bind. Nunca concatenar SQL.
- **XML**: sempre validar contra XSD oficial antes de persistir. Usar nfelib,
  nunca lxml direto sem sanitização.

## Estrutura de diretórios

```
src/
  importador/     # Importador DF-e + manifestação em lote + rate limit
  parser/         # Parser XML (nfelib)
  persistencia/   # Modelos SQLAlchemy + repositórios
  reconciliacao/  # Motor de matching
  contabilidade/  # Gerador de lançamentos + exportador ECD
  fiscal/         # Validadores + cálculo tributário + apuração mensal
  dashboard/      # FastAPI + Jinja2
  mock_sefaz/     # Mock da Receita para testes
tests/
  unit/           # Testes unitários
  integration/    # Testes de integração (com Docker + Redis)
  fixtures/       # XMLs de exemplo, gerador sintético
docker/
  docker-compose.yml      # Dev
  docker-compose.test.yml # Testes (com mock SEFAZ)
  Dockerfile
schemas/
  nfe/            # XSD simplificado NF-e 4.00
docs/
  guia-simples.md
  spec.md
  kanban.md
  plano-demo-entrevista.md
  checklist-lado-empresa.md
  plano-acessos-e-rag.md
  relatorio-lacunas-contabeis-legislativas.md
  observability-contract.md
  spec-testes.md
.github/
  workflows/
    ci.yml        # CI/CD pipeline (testes + lint + cobertura)
Makefile          # Atalhos para comandos comuns
```

## Gates obrigatórios ao terminar geração

Antes de declarar qualquer tarefa como Done, passar pelos 6 gates:
1. `/ponytail` (minimalismo)
2. `/autoresearch` (otimização)
3. `/improve` (auditoria)
4. `/secure-code` (OWASP)
5. `/nlp-gate` (português)
6. `/copy-gate` (copy, se aplicável)

Para código fiscal/contábil, aplicar também os gates do projeto:
7. `.devin/skills/contabil-gate/SKILL.md`
8. `.devin/skills/legislativo-gate/SKILL.md`

Se a tarefa for trivial (uma linha, rename), dizer explicitamente que pulou.

## Verificação adicional dos novos cenários

- `docker compose exec app pytest tests/unit/test_validadores.py tests/unit/test_gate_contracts.py`
- `docker compose exec app pytest tests/integration/test_cenarios_reais.py`
- `docker compose exec app pytest --cov=src --cov-report=term-missing`

A aprovação dos gates contábil e legislativo significa que o escopo testado
passou e que as lacunas estão registradas. Não substitui PVA, SEFAZ ou revisão
profissional.

## Decisões arquiteturais (não revisitar sem motivo forte)

1. Python em vez de Node/PHP/Java (ecossistema fiscal mais maduro).
2. Híbrido: open source para importação, comercial para emissão (fase 2).
3. PostgreSQL em vez de MongoDB (dados fiscais são relacionais).
4. Mock SEFAZ próprio em Python (não usar sefaz-mocked Node.js).
5. Reconciliação determinística primeiro, IA depois (fase 2).
6. Single-tenant no MVP (multi-empresa na fase 2).
7. FastAPI + Jinja2 em vez de React (MVP não precisa de SPA).

## Fontes oficiais (para consulta)

- Portal NF-e: https://www.nfe.fazenda.gov.br/portal/principal.aspx
- NT 2025.002 (reforma tributária): https://taxup.com.br/solucoes/reforma-tributaria/layout-nfe-nt-2025-002/
- Schemas XSD: https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos
- nfelib: https://github.com/akretion/nfelib
- erpbrasil.edoc: https://github.com/erpbrasil/erpbrasil.edoc
- Manual ECD Leiaute 9: https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd
