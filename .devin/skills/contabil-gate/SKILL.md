---
name: contabil-gate
description: Gate adaptativo de validação contábil para NF-e, reconciliação e SPED ECD. Detecta fase do projeto (MVP/homologação/produção), ajusta severidade dos 12 controles conforme contexto, calcula score composto e gera recomendações contextuais. Baseado em Lei 6.404/76, NBC TG 200, Manual ECD Leiaute 9, IN RFB 2.003/2021, EC 132/2023.
triggers:
  - user
  - model
---

# Gate contábil adaptativo

Gate que se ajusta ao contexto do projeto antes de aplicar os 12 controles.
A aprovação não substitui revisão de contador, auditor ou validação no PVA.

## Fase 1: Detectar contexto (executar antes dos controles)

Ler o projeto e classificar:

1. **Fase do projeto** (determina multiplicador de severidade):
   - `MVP`: mock SEFAZ ativo, sem certificado A1 real, CI/CD sem deploy automático, cobertura < 80%
   - `homologacao`: certificado de testes, SEFAZ homologação, CI/CD com deploy staging
   - `producao`: certificado A1 real, SEFAZ produção, deploy automatizado, cobertura >= 80%

2. **Domínio** (determina quais controles aplicam):
   - `fiscal`: só NF-e/DF-e, sem ECD
   - `contabil`: só ECD/lançamentos, sem NF-e
   - `fiscal-contabil`: ambos (aplicar todos os 12 controles)

3. **Stack** (determina como verificar precisão monetária):
   - Python: verificar uso de `Decimal` vs `float`
   - Java: verificar `BigDecimal` vs `double`
   - Outras: adaptar verificação de precisão

4. **Tamanho** (determina profundidade da auditoria):
   - `pequeno` (< 5 módulos): auditoria completa em todos
   - `medio` (5-20 módulos): auditoria por amostragem estratificada
   - `grande` (> 20 módulos): auditoria por camadas (persistência, negócio, API)

Como detectar: ler `AGENTS.md`, `.env` (variáveis `MOCK_SEFAZ`, `CERTIFICADO_A1_PATH`), `docker-compose.yml`, `pyproject.toml`/`requirements.txt`, estrutura de `src/`, cobertura de testes.

## Fase 2: Aplicar controles com severidade adaptativa

Cada controle tem **peso** e **severidade base**. O multiplicador de fase ajusta a severidade:

| Fase | Multiplicador | Efeito |
|------|--------------|--------|
| MVP | 0.5 | CRITICAL vira HIGH, HIGH vira MEDIUM, MEDIUM vira LOW |
| Homologação | 1.0 | Mantém severidade base |
| Produção | 1.5 | LOW vira MEDIUM, MEDIUM vira HIGH, HIGH vira CRITICAL |

Controles marcados `N/A` para o domínio detectado são excluídos do score.

### C1. Partida dobrada (peso 10, CRITICAL)
Lei nº 6.404/1976, art. 177. NBC TG 200 (CPC 00).
- [ ] Todo lançamento tem conta de débito e conta de crédito.
- [ ] O valor é positivo e o débito é igual ao crédito.
- [ ] A soma do diário fecha e lançamentos de estorno invertem as contas.
Aplica: `fiscal-contabil`, `contabil`. Não aplica: `fiscal`.

### C2. Plano de contas (peso 8, HIGH)
Manual ECD Leiaute 9, registro I050. NBC TG 200.
- [ ] Código referencial é único.
- [ ] Contas analíticas e sintéticas são distinguidas.
- [ ] Lançamentos usam somente contas analíticas.
- [ ] A hierarquia e a natureza da conta são coerentes.
Aplica: `fiscal-contabil`, `contabil`.

### C3. CFOP (peso 7, HIGH)
Convênio s/nº de 1970, tabela vigente do CONFAZ.
- [ ] CFOP tem quatro dígitos e existe na tabela vigente.
- [ ] O primeiro dígito é compatível com entrada ou saída.
- [ ] Serviço, ativo, consumo e devolução têm mapeamento contábil próprio.
Aplica: todos os domínios.

### C4. NCM e serviço (peso 6, HIGH)
TIPI 2024, LC nº 116/2003.
- [ ] Mercadoria tem NCM de oito dígitos validado contra a tabela vigente.
- [ ] Serviço usa código compatível com o leiaute e LC nº 116/2003.
- [ ] CFOP de serviço não é combinado com NCM de mercadoria.
Aplica: `fiscal-contabil`, `fiscal`.

### C5. CST e CSOSN (peso 6, HIGH)
Tabelas ICMS/IPI/PIS/COFINS vigentes.
- [ ] CST/CSOSN pertence à tabela aplicável ao regime tributário.
- [ ] CST isento ou não tributado não gera imposto incompatível.
Aplica: `fiscal-contabil`, `fiscal`.

### C6. ECD (peso 9, CRITICAL)
IN RFB nº 2.003/2021, Manual Leiaute 9 de janeiro de 2026.
- [ ] Registros 0000, I001, I030, I050, I200, I250, I990, 9001, 9900, 9990 e 9999 são coerentes.
- [ ] O período e as datas dos lançamentos são válidos.
- [ ] Débitos e créditos do diário fecham.
- [ ] O arquivo é validado pelo PVA antes da transmissão.
Aplica: `fiscal-contabil`, `contabil`. Não aplica: `fiscal`.

### C7. Reconciliação three-way (peso 7, HIGH)
- [ ] NF-e, pedido e recebimento são comparados quando disponíveis.
- [ ] Tolerâncias de valor, quantidade e data são explícitas.
- [ ] Estados `matched`, `divergent` e `pending` são persistidos.
- [ ] A operação é idempotente e divergências são auditáveis.
Aplica: `fiscal-contabil`, `fiscal`.

### C8. Tributos e IBS/CBS (peso 8, CRITICAL)
EC 132/2023, LC 214/2025.
- [ ] ICMS, ICMS-ST, IPI, PIS e COFINS são calculados com base, alíquota e valor coerentes.
- [ ] IBS/CBS usam configuração versionada, não alíquota permanente hardcoded.
- [ ] Valores usam `Decimal` (Python) ou `BigDecimal` (Java), arredondamento explícito.
Aplica: `fiscal-contabil`, `fiscal`.

### C9. Estorno e rastreabilidade (peso 5, MEDIUM)
- [ ] Estorno cria novo lançamento, referencia o original e marca o original.
- [ ] Nota sintética não gera lançamento fiscal.
- [ ] NF-e SEFAZ mantém origem, XML, protocolo e data de autorização.
Aplica: `fiscal-contabil`, `contabil`.

### C10. Datas e prazo ECD (peso 6, HIGH)
IN RFB nº 2.003/2021, art. 5º.
- [ ] Data futura ou fora do período é rejeitada.
- [ ] O prazo normal da ECD é o último dia útil de junho do ano seguinte, conforme art. 5º da IN RFB nº 2.003/2021, salvo situação especial ou prorrogação vigente.
- [ ] Mudanças legais são acompanhadas por testes de regressão e fonte oficial.
Aplica: `fiscal-contabil`, `contabil`.

### C11. Precisão monetária (peso 7, HIGH)
- [ ] Valores monetários usam `Decimal` (Python) ou `BigDecimal` (Java), não `float`/`double`.
- [ ] Arredondamento e tolerância de centavo são explícitos.
- [ ] Soma de itens, tributos, frete e desconto é reproduzível.
Aplica: todos os domínios.

### C12. Evidência e atualização (peso 4, MEDIUM)
- [ ] Cada regra tem fonte, vigência, teste e responsável pela atualização.
- [ ] O relatório distingue comportamento verificado de lacuna futura.
- [ ] A aprovação não substitui PVA, SEFAZ ou revisão profissional.
Aplica: todos os domínios.

## Fase 3: Calcular score composto

Para cada controle aplicável, atribuir status:
- `PASSA` (1.0): regra implementada, teste verde, fonte registrada.
- `PASSA_COM_LACUNA` (0.5): comportamento seguro mas sem cobertura completa.
- `FALHA` (0.0): regra ausente, teste falha, ou fonte desatualizada.

Fórmula:
```
score = Σ(peso_controle × status_controle) / Σ(peso_controle) × 100
```

Threshold de aprovação por fase:

| Fase | Threshold | Condição adicional |
|------|-----------|-------------------|
| MVP | >= 55% | Nenhuma lacuna CRITICAL sem plano de mitigação |
| Homologação | >= 75% | Nenhuma lacuna CRITICAL sem data de resolução |
| Produção | >= 90% | Zero lacunas CRITICAL, zero HIGH sem resolução |

## Fase 4: Veredito e recomendações

- **BLOQUEIA**: score < threshold da fase, OU qualquer CRITICAL sem mitigação em produção.
- **PASSA COM LACUNAS**: score >= threshold mas há lacunas rastreadas.
- **PASSA**: score = 100%, sem lacunas.

O relatório de saída deve conter:

1. **Contexto detectado**: fase, domínio, stack, tamanho, com evidências (arquivos lidos).
2. **Tabela de controles**: controle, peso, severidade ajustada, status, evidência.
3. **Score**: valor numérico, threshold da fase, diferença.
4. **Lacunas**: lista com ID, descrição, severidade ajustada, referência legal, próximo passo.
5. **Recomendações contextuais**: próximas 3-5 ações priorizadas por (severidade × peso × fase).
6. **Memória**: comparar com execução anterior se existir `docs/gate-contabil-historico.json`, marcar lacunas resolvidas e novas.

## Memória entre execuções

Se `docs/gate-contabil-historico.json` existir, ler antes de executar e:
- Marcar lacunas da execução anterior como `resolvida` se não aparecerem nesta.
- Marcar lacunas novas como `nova`.
- Atualizar o arquivo ao final com a execução atual.

Formato do histórico:
```json
{
  "ultima_execucao": "2026-08-06",
  "fase_detectada": "MVP",
  "score": 72.5,
  "lacunas": [
    {"id": "C6-1", "descricao": "...", "severidade": "HIGH", "status": "aberta"}
  ]
}
```

## Referências legais

- Lei nº 6.404/1976 (Lei das S/A): art. 177 (partida dobrada).
- NBC TG 200 (CPC 00): estrutura conceitual, plano de contas.
- IN RFB nº 2.003/2021: SPED ECD, layout e prazo (art. 5º).
- Manual ECD Leiaute 9 (janeiro de 2026): layout dos registros.
- EC 132/2023 + LC 214/2025: Reforma Tributária (IBS/CBS/IS).
- LC nº 87/1996 (Lei Kandir): ICMS não cumulatividade.
- LC nº 116/2003: lista de serviços (ISS).
- Decreto nº 7.212/2010: regulamento IPI.
- TIPI 2024: tabela de alíquotas IPI por NCM.
- Convênio s/nº de 1970 + tabelas vigentes CONFAZ: CFOP.
