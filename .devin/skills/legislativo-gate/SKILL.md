---
name: legislativo-gate
description: Gate adaptativo de conformidade legislativa para NF-e, DF-e, tributos, ECD e LGPD. Detecta fase do projeto (MVP/homologação/produção), ajusta severidade dos 8 controles conforme contexto, calcula score composto ponderado e gera recomendações contextuais. Baseado em MOC 7.0, IN RFB 2.003/2021, EC 132/2023, LC 214/2025, Lei 13.709/2018.
triggers:
  - user
  - model
---

# Gate legislativo adaptativo

Gate que se ajusta ao contexto do projeto antes de aplicar os 8 controles de
conformidade legal. A aprovação indica que as regras verificadas têm testes e
fontes identificadas; não constitui parecer jurídico, nem garante autorização
fiscal sem validação nos ambientes oficiais.

## Fase 1: Detectar contexto (executar antes dos controles)

Ler o projeto e classificar:

1. **Fase do projeto** (determina multiplicador de severidade):
   - `MVP`: mock SEFAZ ativo, sem certificado A1 real, sem deploy produção
   - `homologacao`: certificado de testes, SEFAZ homologação, deploy staging
   - `producao`: certificado A1 real, SEFAZ produção, deploy automatizado

2. **Domínio legislativo** (determina quais controles aplicam):
   - `nf-e-only`: só notas fiscais eletrônicas
   - `ecd-only`: só escrituração contábil digital
   - `fiscal-completo`: NF-e + ECD + tributos + LGPD (aplicar todos)
   - `df-e-outros`: CT-e, MDF-e, NFS-e (aplicar L1 + L9 adaptado)

3. **Regime tributário** (determina quais regras de L4 aplicar):
   - Ler do projeto ou perguntar: Simples Nacional, Lucro Real, Lucro Presumido
   - Simples: CSOSN, sem destaque de ICMS/IPI (geralmente), DAS unificado
   - Lucro Real: CST ICMS/IPI/PIS/COFINS, ECD obrigatória, ECF
   - Lucro Presumido: CST ICMS/IPI, ECD se faturamento > limite, sem ECF

4. **Setor** (determina regras especiais):
   - `comercio`: ICMS, IPI, ST
   - `servicos`: ISS, retenções CSRF, LC 116/2003
   - `industria`: IPI, TIPI, industrialização
   - `agro`: ICMS diferido, Zona Franca

Como detectar: ler `AGENTS.md`, `.env` (variáveis `MOCK_SEFAZ`, `CNPJ_CONSULTADO`), `docker-compose.yml`, estrutura de `src/`, regime tributário em config ou documentação.

## Fase 2: Aplicar controles com severidade adaptativa

Cada controle tem **peso** e **severidade base**. O multiplicador de fase ajusta:

| Fase | Multiplicador | Efeito |
|------|--------------|--------|
| MVP | 0.5 | CRITICAL vira HIGH, HIGH vira MEDIUM, MEDIUM vira LOW |
| Homologação | 1.0 | Mantém severidade base |
| Produção | 1.5 | LOW vira MEDIUM, MEDIUM vira HIGH, HIGH vira CRITICAL |

Controles não aplicáveis ao domínio/regime/setor detectados são `N/A` (excluídos do score).

### L1. NF-e e DF-e (peso 10, CRITICAL)
MOC 7.0, CONFAZ, Portal NF-e. NT 2023.002 (leiaute 4.00).
- [ ] Chave tem 44 caracteres e DV módulo 11 conforme MOC 7.0.
- [ ] Modelo, série, número, CNPJ, status e eventos são validados.
- [ ] XML é comparado ao leiaute oficial vigente e assinatura é tratada fora do mock.
- [ ] Protocolo e data de autorização são preservados.
- [ ] Data de autorização >= data de emissão.
- Fonte: https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf
Aplica: `nf-e-only`, `fiscal-completo`, `df-e-outros`.

### L2. ECD (peso 9, CRITICAL)
IN RFB nº 2.003/2021, Manual Leiaute 9 de janeiro de 2026.
- [ ] Obrigatoriedade é decidida pela legislação aplicável e pela situação da empresa.
- [ ] O layout usado é o manual vigente do SPED.
- [ ] Prazo normal é o último dia útil de junho do ano seguinte, conforme art. 5º da IN RFB nº 2.003/2021.
- [ ] Situações especiais e prorrogações não são tratadas como prazo normal.
- [ ] Multa por atraso: R$ 500,00 por mês-calendário (Lei 8.218/91).
- Fonte: https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd
Aplica: `ecd-only`, `fiscal-completo`. Não aplica: `nf-e-only` (exceto se Lucro Real).

### L3. Reforma tributária (peso 8, CRITICAL)
EC 132/2023, LC 214/2025.
- [ ] IBS, CBS e IS têm regras versionadas por período.
- [ ] Em 2026, o sistema trata destaque e dispensa de recolhimento conforme orientação oficial, sem fixar alíquotas futuras.
- [ ] Pessoas físicas contribuintes da CBS/IBS e documentos eletrônicos são cobertos quando aplicável.
- [ ] Período de transição 2026-2033: regras por vigência, não hardcoded.
- [ ] Cashback e redução por setor: parametrizável, não fixo.
- Fonte: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/orientacoes-2026
Aplica: `fiscal-completo`, `nf-e-only`. Severidade em MVP: HIGH (não bloqueia, mas rastreia).

### L4. ICMS, IPI, PIS e COFINS (peso 8, HIGH)
Constituição art. 155/153/195. LC 87/96. Decreto 7.212/2010. Leis 10.637/02, 10.833/03.
- [ ] Base, alíquota, CST/CSOSN e regime tributário são compatíveis.
- [ ] ICMS-ST considera regra estadual, MVA e convênio aplicável.
- [ ] IPI consulta TIPI vigente por NCM.
- [ ] PIS/COFINS distinguem regime cumulativo (0,65% + 3,00%) e não cumulativo (1,65% + 7,60%).
- [ ] Alíquota interestadual: 7% (Sul/Sudeste -> Norte/Nordeste/CO), 12% (resto), 4% (importados).
- [ ] Simples Nacional: CSOSN (101, 102, 201, 202, 500, 900), sem destaque ICMS (geralmente).
- Fontes: Constituição, LC nº 87/1996, Decreto nº 7.212/2010, Leis nº 10.637/2002 e 10.833/2003.
Aplica: `fiscal-completo`, `nf-e-only`. Adapta por regime: Simples foca CSOSN, Lucro Real foca CST.

### L5. Manifestação do destinatário (peso 6, HIGH)
Ajuste SINIEF 07/2005, cláusulas 15-A a 15-C. Ajuste SINIEF 44/2020.
- [ ] Ciência da emissão respeita o prazo de até 10 dias quando aplicável.
- [ ] Confirmação, desconhecimento e operação não realizada respeitam o prazo aplicável, que pode chegar a 180 dias.
- [ ] Eventos são persistidos com tipo, data, protocolo e NSU.
- Fonte: https://www.confaz.fazenda.gov.br/legislacao/ajustes/2020/ajuste-sinief-44-20
Aplica: `nf-e-only`, `fiscal-completo`.

### L6. LGPD (peso 7, HIGH)
Lei nº 13.709/2018, ANPD.
- [ ] Finalidade, necessidade, acesso, retenção e canal do titular são documentados.
- [ ] Logs não expõem CNPJ, CPF, tokens ou dados de pagamento.
- [ ] O sistema não presume que todo CNPJ seja dado pessoal de pessoa natural; identifica responsáveis, sócios e representantes quando presentes.
- [ ] Retenção: 5 anos para fins fiscais (CTN art. 195), política definida para demais dados.
- [ ] DPO designado quando aplicável (LGPD art. 41).
- Fonte: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/legislacao/lei-no-13-709-de-14-de-agosto-de-2018
Aplica: todos os domínios. Severidade em produção: CRITICAL (sobe 1 nível).

### L7. Obrigações acessórias e retenções (peso 5, MEDIUM)
IN RFB 1.974/2020, 2.043/2021, 2.049/2022, 2.052/2022. Lei 10.833/03 art. 30.
- [ ] DCTFWeb, EFD-Reinf, EFD-ICMS/IPI, ECF e demais obrigações são tratadas por competência e regime.
- [ ] Retenções de IR (1,5% PJ, 1,0% serviços profissionais), CSRF (4,65%), ISS e INSS (11%) não são inferidas somente pelo CFOP.
- [ ] O calendário oficial é parametrizável e versionado.
- [ ] ECF: último dia útil de julho (IN RFB 2.049/2022). EFD-ICMS/IPI: mês seguinte (Ajuste SINIEF 09/07).
Aplica: `fiscal-completo`, `ecd-only`. Adapta por regime: Simples não tem ECF, tem DASN.

### L8. Cadeia de evidência (peso 6, HIGH)
- [ ] Cada regra fiscal tem fonte, vigência e teste associado.
- [ ] XML, eventos, protocolo, usuário e horário são preservados para auditoria.
- [ ] A aplicação separa mock, homologação e produção.
- [ ] Chave de acesso valida digito verificador módulo 11 (pesos 2-9).
Aplica: todos os domínios.

## Fase 3: Calcular score composto

Para cada controle aplicável, atribuir status:
- `PASSA` (1.0): regra implementada, teste verde, fonte vigente registrada.
- `PASSA_COM_LACUNA` (0.5): comportamento seguro no escopo atual, mas sem cobertura legal completa.
- `FALHA` (0.0): regra crítica ausente, valor fiscal calculado sem base, ou fonte desatualizada.

Fórmula:
```
score = Σ(peso_controle × status_controle) / Σ(peso_controle) × 100
```

Threshold de aprovação por fase:

| Fase | Threshold | Condição adicional |
|------|-----------|-------------------|
| MVP | >= 50% | Nenhuma lacuna CRITICAL sem plano de mitigação documentado |
| Homologação | >= 70% | Nenhuma lacuna CRITICAL sem data de resolução |
| Produção | >= 85% | Zero lacunas CRITICAL, zero HIGH sem resolução em andamento |

## Fase 4: Veredito e recomendações

- **BLOQUEIA**: score < threshold da fase, OU qualquer CRITICAL sem mitigação em produção.
- **PASSA COM LACUNA**: score >= threshold mas há lacunas rastreadas.
- **PASSA**: score = 100%, sem lacunas.

O relatório de saída deve conter:

1. **Contexto detectado**: fase, domínio, regime tributário, setor, com evidências (arquivos lidos, variáveis de ambiente).
2. **Tabela de controles**: controle, peso, severidade ajustada, status, evidência, fonte legal.
3. **Score**: valor numérico, threshold da fase, diferença, evolução vs execução anterior.
4. **Lacunas**: lista com ID, descrição, severidade ajustada, referência legal, próximo passo, status (nova/resolvida/recorrente).
5. **Recomendações contextuais**: próximas 3-5 ações priorizadas por (severidade ajustada × peso × urgência da fase).
6. **Fontes consultadas**: URLs verificadas com data de acesso.

## Memória entre execuções

Se `docs/gate-legislativo-historico.json` existir, ler antes de executar e:
- Marcar lacunas da execução anterior como `resolvida` se não aparecerem nesta.
- Marcar lacunas novas como `nova`.
- Marcar lacunas recorrentes (3+ execuções) como `recorrente` com severidade elevada.
- Atualizar o arquivo ao final com a execução atual.

Formato do histórico:
```json
{
  "ultima_execucao": "2026-08-06",
  "fase_detectada": "MVP",
  "regime_tributario": "Lucro Real",
  "score": 65.0,
  "threshold": 50,
  "lacunas": [
    {"id": "L3-1", "descricao": "...", "severidade": "HIGH", "status": "aberta", "primeira_ocorrencia": "2026-07-15"}
  ]
}
```

## Referências legais (vigentes em 2026)

- Constituição Federal: art. 155 (ICMS), art. 153 (IPI), art. 195 (PIS/COFINS).
- EC 132/2023 + LC 214/2025: Reforma Tributária (IBS, CBS, IS, transição 2026-2033).
- Lei nº 6.404/1976: art. 177 (partida dobrada), art. 278 (livros).
- Lei nº 8.218/1991: multa por atraso ECD.
- Lei nº 10.637/2002: PIS não cumulativo.
- Lei nº 10.833/2003: COFINS não cumulativo, retenções CSRF (art. 30).
- Lei nº 13.709/2018 (LGPD): proteção de dados pessoais.
- CTN (Lei nº 5.172/1966): art. 195 (prescrição 5 anos), art. 43 (créditos tributários).
- IN RFB nº 2.003/2021: SPED ECD, layout e prazo (art. 5º).
- IN RFB nº 2.049/2022: ECF (Escrituração Contábil Fiscal).
- MOC 7.0 + NT 2023.002: leiaute NF-e 4.00.
- Ajuste SINIEF 07/2005: manifestação do destinatário (cláusulas 15-A a 15-C).
- Ajuste SINIEF 44/2020: prazos de manifestação.
- Ajuste SINIEF 09/07: EFD-ICMS/IPI.
- LC nº 87/1996 (Lei Kandir): ICMS não cumulatividade.
- LC nº 116/2003: lista de serviços ISS.
- Decreto nº 7.212/2010: regulamento IPI.
- TIPI 2024: tabela de alíquotas IPI por NCM.
