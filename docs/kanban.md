# Kanban: Sistema de Contabilidade com NF-e

> Quadro de tarefas do projeto. Cada tarefa é um cartão que se move da esquerda
> para a direita conforme avança. WIP limit 1 (uma tarefa em Doing por vez).
> Atualizado em: 06/08/2026.

---

## Legenda

- **Backlog**: tudo que precisa ser feito, sem ordem obrigatória.
- **To Do**: próxima tarefa a ser feita, na ordem de cima para baixo.
- **Doing**: tarefa em andamento agora (máximo 1).
- **Review**: tarefa feita, aguardando passar pelos 6 gates.
- **Done**: tarefa finalizada, passou nos gates, está pronta.

Cada tarefa em Done tem o resultado dos gates documentado:
`[P]` ponytail, `[A]` autoresearch, `[I]` improve, `[S]` secure-code,
`[N]` nlp-gate, `[C]` copy-gate, `[F]` contabil-gate, `[L]` legislativo-gate.
`OK` = passou, `SKIP` = trivial, pulado.

---

## BACKLOG (ideias e tarefas futuras)

### Fase 2 (depois do MVP)

- [ ] F2-01: Integração com API comercial para emissão de NF-e (NFE.io)
- [ ] F2-02: Suporte a NFS-e municipal (padrão nacional primeiro)
- [ ] F2-03: Suporte a CT-e (conhecimento de transporte)
- [ ] F2-04: Suporte a MDF-e (manifesto de carga)
- [ ] F2-05: Geração direta de arquivos SPED (ECD, ECF, EFD)
- [ ] F2-06: Multi-empresa (multi-tenant)
- [ ] F2-07: Matching com IA (embeddings para casos ambíguos)
- [ ] F2-08: Integração com ERP externo (SAP, Oracle, Odoo) via API
- [ ] F2-09: App mobile para aprovar divergências
- [ ] F2-10: Alertas por e-mail quando notas divergentes chegam

### Melhorias futuras

- [ ] MF-01: Backup automático do banco (pg_dump cron)
- [ ] MF-02: Monitoramento com Prometheus + Grafana
- [ ] MF-03: Autenticação de usuário (login, senha, sessão)
- [ ] MF-04: API rate limiting (proteger a própria API)
- [ ] MF-05: Versionamento de schema do banco (migrações automáticas)
- [ ] MF-06: Suporte a certificado A3 (token USB)
- [ ] MF-07: Exportação para PDF (relatório mensal)
- [ ] MF-08: Internacionalização (inglês, espanhol)

---

## TO DO (próximas tarefas, em ordem)

### Fase 7: Fechamento de lacunas offline (semana 7)

- [ ] F7-01: Cálculo tributário determinístico (ICMS/IPI/PIS/COFINS/ST)
- [ ] F7-02: Apuração mensal (endpoint que fecha período por imposto)
- [ ] F7-03: SPED/ECD layout oficial (blocos 0, I, J, K, 9)
- [ ] F7-04: Manifestação do destinatário automatizada em lote
- [ ] F7-05: CI/CD pipeline automatizado
- [ ] F7-06: Cobertura de testes do gerador.py e ecd.py
- [ ] F7-07: Rate limit real exercitado em testes de integração
- [ ] F7-08: Parser XML oficial com validação XSD da SEFAZ

---

## DOING (máximo 1 tarefa por vez)

(nada no momento)

---

## REVIEW (feito, aguardando gates)

(nada no momento)

---

## DONE (finalizado, passou nos gates)

### Fase 1 a 6 (MVP original)

- [x] D0-01 a D0-08: Pesquisa, auditoria, spec, estrutura, guia, kanban, AGENTS.md
- [x] F1-01 a F1-10: Fundação (Docker, schema, modelos, mock SEFAZ)
- [x] F2-11 a F2-20: Importação DF-e (erpbrasil.edoc, parser, validação, persistência)
- [x] F3-01 a F3-12: Reconciliação (matching, divergências, auditoria)
- [x] F4-01 a F4-10: Contabilidade (plano de contas, lançamentos, estorno, ECD)
- [x] F5-01 a F5-16: Dashboard (FastAPI, endpoints, templates, filtros)
- [x] F6-01 a F6-13: Testes e polish (gerador sintético, volume, idempotência, retry, XSD)

### Fase 7: Fechamento de lacunas offline

- [x] F7-01: Cálculo tributário determinístico (ICMS/IPI/PIS/COFINS/ST)
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]OK
- [x] F7-02: Apuração mensal (endpoint que fecha período por imposto)
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]OK
- [x] F7-03: SPED/ECD layout oficial (blocos 0, I, J, K, 9)
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]OK
- [x] F7-04: Manifestação do destinatário automatizada em lote
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]OK
- [x] F7-05: CI/CD pipeline automatizado
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]SKIP [L]SKIP
- [x] F7-06: Cobertura de testes do gerador.py e ecd.py
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]SKIP
- [x] F7-07: Rate limit real exercitado em testes de integração
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]SKIP [L]SKIP
- [x] F7-08: Parser XML oficial com validação XSD da SEFAZ
  Gates: [P]OK [A]OK [I]OK [S]OK [N]OK [C]SKIP [F]OK [L]SKIP

---

## Estatísticas

| Métrica | Valor |
|---|---|
| Total de tarefas no MVP | 67 |
| Tarefas do MVP concluídas | 65 |
| Tarefas da Fase 7 | 8 |
| Tarefas da Fase 7 concluídas | 8 |
| Total de testes | 258 |
| Fases | 7 |
| Mock SEFAZ | ativo |
| Ambiente | homologação |
| CI/CD | GitHub Actions ativo |
| Cobertura mínima | 70% |

---

## Regras do kanban

1. **WIP limit 1**: só uma tarefa em Doing por vez. Acabou, move para Review,
   pega a próxima.
2. **Gates obrigatórios**: toda tarefa que vai de Doing para Review precisa
   passar pelos 6 gates (ponytail, autoresearch, improve, secure-code, nlp-gate,
   copy-gate). Se for trivial, dizer explicitamente que pulou.
3. **Ordem**: respeitar a ordem de To Do (de cima para baixo dentro de cada
   fase). Fases são sequenciais (fase 2 depende de fase 1, etc.).
4. **Atualização**: mover cartões conforme avança. Se uma tarefa bloquear,
   marcar com [BLOQUEADA] e explicar o motivo.
5. **Granularidade**: cada tarefa deve levar de 30 minutos a 4 horas. Se
   maior, quebrar em subtarefas.
