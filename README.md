# Contabilidade

Sistema de importação, reconciliação e gestão de notas fiscais eletrônicas
(NF-e). Importa notas da Receita Federal, reconcilia com pedidos de compra,
gera lançamentos contábeis e exibe em dashboard web.

## Documentação

- **[docs/guia-simples.md](docs/guia-simples.md)**: guia completo explicado de
  forma simples (para quem não sabe nada de programação ou contabilidade).
- **[docs/spec.md](docs/spec.md)**: especificação técnica com 30 critérios de
  aceitação testáveis.
- **[docs/kanban.md](docs/kanban.md)**: quadro de tarefas (67 tarefas, 6 fases).
- **[docs/plano-demo-entrevista.md](docs/plano-demo-entrevista.md)**: roteiro de
  demonstração sem certificados ou acesso governamental.
- **[docs/checklist-lado-empresa.md](docs/checklist-lado-empresa.md)**: acessos,
  regras e decisões que dependem da empresa.
- **[docs/plano-acessos-e-rag.md](docs/plano-acessos-e-rag.md)**: plano de APIs,
  certificados, legislação e RAG temporal.
- **[AGENTS.md](AGENTS.md)**: guia para agentes de IA que forem trabalhar no
  projeto.

## Stack

Python 3.12, FastAPI, nfelib, erpbrasil.edoc, PostgreSQL 16, Redis 7, Docker.

## Status

Fase 0 (planejamento) concluída. Fase 1 (fundação) a iniciar.
