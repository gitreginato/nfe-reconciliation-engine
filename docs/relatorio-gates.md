# Relatório dos oito gates

## Resultado executivo

Os oito gates foram executados sobre o incremento TDD/SDD/ODD. Nenhum gate
aplicável bloqueou a entrega do incremento. Os gates de conformidade contábil e
legislativa foram classificados como **PASSA COM LACUNAS**, porque o próprio
checklist exige PVA, SEFAZ, XSD, assinatura digital e revisão profissional para
uma declaração de compliance fiscal completa.

Resultado automatizado:

- **258 testes passaram**;
- cobertura total: **72%**;
- `src/fiscal/validadores.py`: **92%**;
- `tests/unit/test_gate_contracts.py`: **4 testes** de contratos dos gates;
- `tests/integration/test_cenarios_reais.py`: **37 testes de integração**;
- `tests/integration/test_rate_limit.py`: **8 testes** com Redis real;
- `pip check`: sem dependências quebradas.

## Os oito gates

### 1. Ponytail, minimalismo

**Status: PASSA.**

- O módulo fiscal usa somente biblioteca padrão e dependências já presentes.
- Não foi adicionada nova dependência.
- Validadores foram centralizados em um único módulo.
- Os testes reutilizam as fixtures do projeto e o mock SEFAZ local.
- O contrato ODD registra explicitamente a lacuna de OpenTelemetry, em vez de
  adicionar infraestrutura sem requisito operacional definido.

### 2. Autoresearch, otimização

**Status: PASSA COM BASELINE.**

Baseline verificada:

- 258 testes, ~246 segundos no container;
- cobertura total de 72%;
- cobertura do módulo de validadores de 92%;
- 37 testes de integração de cenários reais;
- 8 testes de integração de rate limit com Redis real.

Não foi iniciado um loop autônomo de otimização porque não foi definido um
alvo de métrica para alterar, nem uma branch exclusiva aprovada. O baseline
fica registrado para uma futura otimização de tempo de integração ou cobertura.

### 3. Improve, auditoria sênior

**Status: PASSA COM LACUNAS RASTREADAS.**

As 47 lacunas encontradas foram confirmadas e estão em
`docs/relatorio-lacunas-contabeis-legislativas.md`, com categoria, severidade,
referência e próximo passo. O incremento não declara que XSD, assinatura,
PVA, autenticação, retenção LGPD ou tabelas fiscais completas estejam prontos.

### 4. Secure-code, OWASP

**Status: PASSA COM LACUNAS PREEXISTENTES.**

Verificado no incremento:

- entrada externa de resumo NF-e valida chave, CFOP, NCM e totais antes da
  persistência;
- consultas continuam em SQLAlchemy parametrizado;
- valores monetários usam `Decimal`;
- logs não registram tokens ou CNPJ completo nos novos caminhos;
- nenhuma dependência, segredo ou algoritmo criptográfico foi adicionado.

Lacunas preexistentes que permanecem registradas: autenticação e autorização
nos endpoints, criptografia em repouso e identidade digital do MVP.

### 5. NLP gate, linguagem natural

**Status: PASSA.**

- Documentação nova foi revisada em português do Brasil.
- Fontes foram citadas com URLs verificadas.
- Não há travessão, filler ou promessa de compliance absoluto.
- O relatório separa fato verificado, inferência e lacuna.

### 6. Copy gate

**Status: NÃO APLICÁVEL.**

Não foi gerada copy comercial, landing page, anúncio, e-mail de vendas ou VSL.
O gate de copy não deve ser usado para documentação técnica.

### 7. Gate contábil

**Status: PASSA COM LACUNAS.**

O contrato está em `.devin/skills/contabil-gate/SKILL.md`. Foram cobertos:

- partida dobrada;
- CFOP, NCM e compatibilidade serviço/mercadoria;
- devolução, ativo, consumo, frete e desconto;
- impostos recuperáveis e IBS/CBS de 2026;
- estorno e rastreabilidade;
- período e registros I001/I150 da ECD;
- precisão monetária e período máximo.

Permanecem como bloqueadores de produção fiscal os itens que dependem de
Tabela TIPI/CFOP vigente completa, PVA, plano referencial ECD e regras estaduais.

### 8. Gate legislativo

**Status: PASSA COM LACUNAS.**

O contrato está em `.devin/skills/legislativo-gate/SKILL.md`. A pesquisa foi
atualizada com fontes CONFAZ, SPED, Receita Federal, Planalto e ANPD. Foram
corrigidos dois pontos factuais durante a revisão:

1. prazo normal da ECD, último dia útil de junho, conforme IN RFB nº 2.003/2021;
2. prazo de manifestação por evento, Ciência da Emissão em até 10 dias e os
   demais eventos conforme hipótese aplicável, podendo chegar a 180 dias.

As lacunas legais e técnicas restantes estão listadas no relatório principal.

## Evidências

- Spec SDD: `docs/spec-testes.md`
- Contrato ODD: `docs/observability-contract.md`
- Lacunas: `docs/relatorio-lacunas-contabeis-legislativas.md`
- Gate contábil: `.devin/skills/contabil-gate/SKILL.md`
- Gate legislativo: `.devin/skills/legislativo-gate/SKILL.md`
- Testes dos contratos: `tests/unit/test_gate_contracts.py`
- Modelo de ameaças: `docs/threat-model.md`

## Limite do veredito

Este veredito aprova o incremento de código e testes no escopo do MVP. Não é
certidão de conformidade fiscal. Antes de produção, executar o arquivo gerado
no PVA, validar XML e assinatura com artefatos oficiais, homologar eventos no
SEFAZ e obter revisão contábil e jurídica.
