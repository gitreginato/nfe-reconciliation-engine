# Contrato de observabilidade

## Escopo

O MVP é um serviço FastAPI com PostgreSQL, Redis e um mock SEFAZ. O contrato
abaixo cobre os fluxos de importação, reconciliação, lançamentos e exports.
A instrumentação atual usa logs da aplicação e métricas HTTP do dashboard. Não
há dependência OpenTelemetry adicionada, portanto spans distribuídos ainda são
uma lacuna explícita, não um requisito marcado como implementado.

## Logs

| Evento | Nível | Campos mínimos | Teste |
|---|---|---|---|
| `nfe.importada` | INFO | chave mascarada, NSU, resultado | `test_log_importacao_registra_stats` |
| `reconciliacao.concluida` | INFO | chave mascarada, status, tipo | `test_log_reconciliacao_registra_status` |
| `lancamentos.gerados` | INFO | chave mascarada, quantidade | `test_log_lancamento_registra_quantidade` |
| `importacao.erro` | ERROR | chave mascarada, motivo | teste de erro do importador |

Dados pessoais, tokens, senhas e chaves completas não podem aparecer nos logs.

## Métricas HTTP e de negócio

O endpoint `/api/dashboard` deve expor:

- `total_notas`;
- `notas_pendentes`;
- `notas_reconciliadas`;
- `notas_divergentes`;
- `notas_canceladas`;
- `valor_total`.

A API `/api/notas` deve expor `total`, `page`, `page_size` e a lista limitada.
Os testes de integração verificam o contrato e impedem regressão silenciosa.

## Spans planejados

Quando o tracing for introduzido, usar estes nomes estáveis:

- `nfe.import`;
- `sefaz.distribute`;
- `sefaz.manifest`;
- `sefaz.download_xml`;
- `reconciliation.run`;
- `accounting.generate`;
- `ecd.export`.

Atributos devem conter apenas identificadores mascarados, status, contagem e
duração. XML, CNPJ completo, CPF, certificado e credenciais ficam fora dos
atributos e eventos.

## Critérios ODD

- [x] Fluxos críticos têm logs verificáveis por teste.
- [x] O dashboard expõe métricas de negócio.
- [x] A paginação expõe total e limites.
- [x] Dados sensíveis são testados contra exposição em logs.
- [ ] Spans OpenTelemetry são exportados para um collector.
- [ ] Alertas de erro e latência são configurados fora da aplicação.
