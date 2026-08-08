# NF-e Reconciliation Engine

> Sistema de importação, reconciliação e gestão de notas fiscais eletrônicas (NF-e). Importa notas da Receita Federal via NFeDistribuicaoDFe, faz reconciliação three-way matching com pedidos de compra, gera lançamentos contábeis automáticos, calcula tributos determinísticos, apura impostos mensalmente, manifesta destinatário em lote, exporta ECD no layout oficial e exibe em dashboard web.

## Stack

| Camada | Tecnologia | Por quê |
|--------|-----------|---------|
| Linguagem | Python 3.12 | Ecossistema fiscal mais maduro (nfelib, erpbrasil.edoc) |
| API | FastAPI | Async, tipado, documentação automática |
| ORM | SQLAlchemy 2.0 + Alembic | Migrações versionadas, queries parametrizadas |
| Banco | PostgreSQL 16 | Dados fiscais são relacionais |
| Cache | Redis 7 | Rate limit SEFAZ, filas de manifestação |
| Parsing XML | nfelib 2.5.2 | Validação contra XSD oficial NF-e 4.00 |
| Comunicação SEFAZ | erpbrasil.edoc 3.1.1 | Protocolo oficial de comunicação |
| Container | Docker Compose | Dev e prod isolados, mock SEFAZ próprio |
| Testes | pytest (781 testes, 99% cobertura) | TDD desde o início |
| Dashboard | FastAPI + Jinja2 | MVP não precisa de SPA |

## O que aprendi

- **TDD em domínio regulado**: 781 testes com 99% de cobertura. Cada critério de aceitação da spec vira um teste que falha primeiro, depois implementa, depois refatora. Em domínio fiscal, um bug gera multa, então testes não são opcionais.
- **Mock SEFAZ próprio em Python**: em vez de depender de serviços externos para testar, construí um mock da Receita Federal em Python. Todos os testes de importação usam `MOCK_SEFAZ=true`. Nunca chamar SEFAZ real em testes.
- **Mascaramento de dados sensíveis**: nunca logar CNPJ completo, valores em produção, ou senha de certificado. Implementei mascaramento (`12.345.678/****-**`) em todos os logs.
- **Validação XSD antes de persistir**: todo XML fiscal é validado contra o XSD oficial NF-e 4.00 antes de ser persistido. Usar nfelib, nunca lxml direto sem sanitização.
- **Queries parametrizadas sempre**: SQLAlchemy com parâmetros bind. Nunca concatenar SQL. Em dados fiscais, SQL injection não é só risco de segurança, é risco de corrupção de lançamentos contábeis.
- **Reconciliação determinística primeiro, IA depois**: three-way matching determinístico (nota, pedido, recebimento) antes de qualquer abordagem com IA. IA é fase 2, não MVP.
- **Gates de conformidade adaptativos**: construí gates contábil e legislativo que detectam a fase do projeto (MVP/homologação/produção) e ajustam a severidade dos controles. Baseado em Lei 6.404/76, NBC TG 200, Manual ECD Leiaute 9, IN RFB 2.003/2021.

## Funcionalidades

- **Importação DF-e**: importa notas da Receita Federal via NFeDistribuicaoDFe com rate limit e manifestação em lote
- **Parser XML fiscal**: parsing e validação contra XSD oficial NF-e 4.00 com nfelib
- **Reconciliação three-way matching**: nota, pedido de compra, recebimento
- **Lançamentos contábeis**: geração automática baseada em regras fiscais
- **Cálculo tributário**: validadores + cálculo determinístico de tributos
- **Apuração mensal**: apuração de impostos por período
- **Manifestação destinatário**: em lote, com rate limit
- **Exportação ECD**: layout oficial Leiaute 9 (SPED ECD)
- **Dashboard web**: FastAPI + Jinja2 com visualização de notas, reconciliação e lançamentos
- **Gates de conformidade**: contábil (12 controles) e legislativo (8 controles), adaptativos por fase

## Como rodar

```bash
# Subir ambiente de desenvolvimento
docker compose -f docker/docker-compose.yml up -d

# Rodar migrações do banco
docker compose exec app alembic upgrade head

# Rodar testes
docker exec contabilidade-app python -m pytest

# Testes com cobertura (mínimo 70%)
docker exec contabilidade-app python -m pytest --cov=src --cov-report=term-missing

# Apenas testes unitários
docker exec contabilidade-app python -m pytest tests/unit/

# Apenas testes de integração
docker exec contabilidade-app python -m pytest tests/integration/

# Atalhos do Makefile
make up        # sobe containers
make test      # roda todos os testes
make test-cov  # testes com cobertura
make lint      # ruff check
make down      # para containers
```

## Arquitetura

```
src/
├── importador/      # Importador DF-e + manifestação em lote + rate limit
├── parser/          # Parser XML (nfelib) + validação XSD
├── persistencia/    # Modelos SQLAlchemy + repositórios
├── reconciliacao/   # Motor de three-way matching
├── contabilidade/   # Gerador de lançamentos + exportador ECD
├── fiscal/          # Validadores + cálculo tributário + apuração mensal
├── dashboard/       # FastAPI + Jinja2
├── mock_sefaz/      # Mock da Receita para testes
└── gates/           # Gates de conformidade (contábil + legislativo)

tests/
├── unit/            # 716 testes unitários
├── integration/     # 65 testes de integração (com Docker + Redis)
└── fixtures/        # XMLs de exemplo, gerador sintético

docker/
├── docker-compose.yml       # Dev
├── docker-compose.test.yml  # Testes (com mock SEFAZ)
└── Dockerfile
```

## Testes

781 testes (716 unitários + 65 de integração), 99% de cobertura:

- **Importador**: 49 testes (DF-e, rate limit, manifestação em lote)
- **Dashboard**: 65 testes (rotas, templates, API)
- **Fiscal**: validadores, cálculo tributário, apuração mensal
- **Reconciliação**: motor de three-way matching
- **Contabilidade**: gerador de lançamentos, exportador ECD
- **Gates**: contábil (12 controles), legislativo (8 controles), contratos

```bash
docker exec contabilidade-app python -m pytest --cov=src --cov-report=term-missing
```

## Segurança

- **Segredos**: nunca hardcodar CNPJ, senha de certificado, ou dados sensíveis. Sempre `.env` (gitignored).
- **Logs**: mascaramento de CNPJ (`12.345.678/****-**`), valores em produção, senhas.
- **Queries**: SQLAlchemy com parâmetros bind. Nunca concatenar SQL.
- **XML**: validação contra XSD oficial antes de persistir. nfelib, nunca lxml direto.
- **Mock SEFAZ**: todos os testes usam mock. Nunca chamar SEFAZ real em testes.
- **Threat model**: ver `docs/threat-model.md` para modelagem STRIDE completa.
- **SECURITY.md**: política de reporte de vulnerabilidades.

## Status

- **Fase 0** (planejamento): concluída. Spec com 30 critérios de aceitação, 75 tarefas em 7 fases, threat model, contrato de telemetria.
- **Fase 1** (fundação): a iniciar. Implementação dos módulos core.
- **Fase 2** (comercial): emissão de NF-e, multi-empresa, reconciliação com IA.

## Documentação

- [docs/guia-simples.md](docs/guia-simples.md): guia explicado de forma simples (para não-técnico)
- [docs/spec.md](docs/spec.md): especificação técnica com 30 critérios de aceitação testáveis
- [docs/kanban.md](docs/kanban.md): quadro de tarefas (75 tarefas, 7 fases)
- [docs/plano-demo-entrevista.md](docs/plano-demo-entrevista.md): roteiro de demonstração para entrevista
- [docs/threat-model.md](docs/threat-model.md): modelagem de ameaças STRIDE
- [docs/observability-contract.md](docs/observability-contract.md): contrato de telemetria (ODD)
- [docs/relatorio-lacunas-contabeis-legislativas.md](docs/relatorio-lacunas-contabeis-legislativas.md): 47 lacunas identificadas

## Decisões arquiteturais

1. **Python** em vez de Node/PHP/Java: ecossistema fiscal mais maduro (nfelib, erpbrasil.edoc).
2. **Híbrido**: open source para importação, comercial para emissão (fase 2).
3. **PostgreSQL** em vez de MongoDB: dados fiscais são relacionais.
4. **Mock SEFAZ próprio** em Python: não depender de serviços externos para testar.
5. **Reconciliação determinística primeiro**, IA depois (fase 2).
6. **Single-tenant no MVP**, multi-empresa na fase 2.
7. **FastAPI + Jinja2** em vez de React: MVP não precisa de SPA.

## Licença

[MIT](LICENSE)
