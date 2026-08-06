# Copilot Instructions: contabilidade

## Visao geral
Sistema de contabilidade/NF-e com partida dobrada, plano de contas,
CFOP, NCM, CST/CSOSN, SPED ECD, impostos (ICMS/IPI/PIS/COFINS/IBS-CBS).

## Stack
- Python 3.11+ com FastAPI
- SQLAlchemy + Alembic (migracoes)
- SQLite para dev, PostgreSQL para prod
- Ruff (lint), pytest (testes)
- Docker para isolamento

## Convencoes
- Partida dobrada sempre balanceada (debito = credito)
- Validar CFOP, NCM, CST contra tabelas oficiais
- SPED ECD no leiute 9 (janeiro 2026)
- Reforma Tributaria EC 132/2023 (IBS/CBS)
- SQL parameterized, nunca concatenar
- Input validado com allowlist

## NAO faca
- Nao inventar aliquotas, consultar tabela
- Nao quebrar partida dobrada
- Nao remover migracoes Alembic
- Nao commitar kg.db (e local)
- Nao logar dados sensiveis (CNPJ, CPF, valores)
