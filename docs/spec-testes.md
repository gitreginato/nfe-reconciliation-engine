# Spec: Testes TDD/SDD/ODD e Gates Contábil/Legislativo

## Status: Aprovado
## Data: 2026-07-30
## Versão: 1.0

## 1. Objetivo

Expandir a cobertura de testes do sistema de reconciliação NF-e de 20 para 80+ testes,
abrangendo cenários reais do cotidiano contábil, validações fiscais e legislativas,
e observabilidade (ODD).

## 2. Critérios de aceitação testáveis

### 2.1 Testes unitários (TDD) - `tests/unit/test_validadores.py`
- [x] Validar CFOP contra tabela oficial (Ajuste SINIEF 07/05)
- [x] Validar NCM (8 dígitos ou "00" para serviços)
- [x] Validar CNPJ com dígito verificador (módulo 11)
- [x] Validar CPF com dígito verificador
- [x] Validar chave de acesso com DV módulo 11 (MOC 7.0)
- [x] Validar protocolo (15-17 dígitos)
- [x] Validar CST/CSOSN (Ajuste SINIEF 04/04)
- [x] Validar partida dobrada (Lei 6.404/76 art. 177)
- [x] Validar valor total NF-e (soma itens + frete - desconto)
- [x] Validar alíquotas IBS/CBS por fase (EC 132/2023)
- [x] Validar período ECD (máx 366 dias)
- [x] Validar registros ECD I001 e I150
- [x] Validar prazo de entrega ECD (IN RFB nº 2.003/2021)
- [x] Validar obrigatoriedade ECD (IN RFB 2.003/2021)
- [x] Validar prazo de manifestação por evento, ciência em até 10 dias e demais eventos conforme prazo aplicável, até 180 dias (Ajuste SINIEF 07/2005 e 44/2020)
- [x] Mascarar CNPJ e chave (LGPD art. 5)

### 2.2 Testes de integração (TDD) - `tests/integration/test_cenarios_reais.py`
- [x] Cenário 1: Devolução de compra (CFOP 1202) gera lançamento invertido
- [x] Cenário 2: Nota com frete por conta do destinatário
- [x] Cenário 3: Nota com desconto incondicionado (valor líquido)
- [x] Cenário 4: Nota com ICMS substituição tributária
- [x] Cenário 5: Nota de ativo imobilizado (CFOP 1551)
- [x] Cenário 7: Estorno completo de nota cancelada
- [x] Cenário 8: Resolução manual de divergência via API
- [x] Cenário 9: Nota de serviço (two-way match, NCM "00")
- [x] Cenário 10: Reconciliação com tolerância zero
- [x] Cenário 11: Reconciliação com tolerância alta
- [x] Cenário 12: Nota com IPI recuperável
- [x] Cenário 13: Nota com PIS/COFINS recuperável
- [x] Cenário 18: ECD com saldo inicial zero
- [x] Cenário 19: ECD com múltiplas contas analíticas
- [x] Cenário 20: ECD com lançamento de estorno
- [x] Cenário 21: ECD com período de 1 dia
- [x] Cenário 22: Partida dobrada global fecha
- [x] Cenário 23: Valor total = soma itens + frete - desconto
- [x] Cenário 24: CFOP x NCM compatível
- [x] Cenário 26: Importação incremental com 15 notas

### 2.3 Testes de observabilidade (ODD) - `tests/integration/test_cenarios_reais.py`
- [x] Log de importação registra estatísticas
- [x] Log de reconciliação registra status
- [x] Log de lançamentos registra quantidade
- [x] Logs não expõem CNPJ completo (LGPD)
- [x] Dashboard expõe métricas observáveis
- [x] API paginada expõe total para observabilidade

### 2.4 Gates novos
- [x] `contabil-gate`: 12 controles (partida dobrada, plano de contas, CFOP, NCM, CST, ECD, reconciliação, impostos, estorno, rastreabilidade, precisão, período)
- [x] `legislativo-gate`: 10 controles (NF-e, SPED ECD, reforma tributária, ICMS, IPI, PIS/COFINS, LGPD, retenções, DF-e, prazos)

`[x]` indica que há teste automatizado para o comportamento do MVP. Não indica
que a tabela fiscal, o XSD, o PVA ou a legislação foram integralmente
implementados; as lacunas estão no relatório legislativo.

## 3. Arquitetura

### 3.1 Novo módulo: `src/fiscal/validadores.py`
Centraliza todas as validações fiscais e contábeis:
- Tabelas oficiais (CFOP, CST, CSOSN, UF, alíquotas IBS/CBS)
- Funções de validação (CNPJ, CPF, chave DV, NCM, partida dobrada)
- Funções de máscara (LGPD)
- Funções de cálculo (prazo ECD, obrigatoriedade)

### 3.2 Mock SEFAZ expandido
5 novos cenários no `pool_nfe.py`:
- NSU 11: Devolução de compra (CFOP 1202)
- NSU 12: Compra com frete (modalidade 1)
- NSU 13: Compra com desconto incondicionado
- NSU 14: Compra com ICMS substituição tributária
- NSU 15: Compra com IPI, PIS e COFINS recuperáveis

### 3.3 Importador expandido
`dfe.py` agora persiste campos adicionais:
- valor_produtos, valor_frete, valor_desconto, valor_seguro, valor_outros
- vicms, vicms_st, vbc_icms_st, vipi, vpis, vcofins nos itens

### 3.4 Gerador expandido
`gerador.py` agora mapeia CFOPs de devolução (1201, 1202):
- Débito em Fornecedores (2.1.01)
- Crédito em Estoque (1.1.3.01)
- Inverte a lógica de compra normal

## 4. Referências legais

- Lei 6.404/1976 art. 177 (partida dobrada)
- NT 2023.002 (leiaute NF-e 4.00)
- MOC 7.0 (Manual de Orientação do Contribuinte)
- TIPI 2024 (Decreto 11.158/2022)
- Ajuste SINIEF 07/05 (tabela CFOP)
- Ajuste SINIEF 04/04 (CST ICMS)
- Ajuste SINIEF 07/10 (manifestação do destinatário)
- EC 132/2023 (Reforma Tributária: IBS/CBS)
- LC 214/2025 (Reforma Tributária: transição)
- IN RFB nº 2.003/2021 (SPED ECD layout e prazo)
- IN RFB 2.003/2021 (obrigatoriedade ECD)
- Lei 13.709/2018 (LGPD)
