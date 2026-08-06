# Relatório de lacunas contábeis, fiscais, legislativas e técnicas

## Escopo e verificação

Este relatório consolida a pesquisa solicitada e a análise do código atual. O
projeto agora tem testes TDD, SDD e ODD, dois gates novos e 258 testes verdes.
Isso não significa que o sistema esteja certificado para produção fiscal. O
mock ainda não substitui o PVA, o ambiente SEFAZ, a assinatura ICP-Brasil ou a
revisão de um profissional habilitado.

A execução final foi `258 passed`, com cobertura total de 72%. O módulo novo de
validadores ficou com 92% de cobertura. A cobertura do dashboard permaneceu em
43%, portanto ainda há endpoints sem testes específicos.

Foram verificadas fontes oficiais na web:

1. MOC 7.0, CONFAZ: <https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf>
2. Leiaute NF-e/NFC-e, CONFAZ: <https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-anexo-i-leiaute-e-rv.pdf>
3. Tabela CFOP vigente, CONFAZ: <https://www.confaz.fazenda.gov.br/legislacao/ajustes/sinief/cfop_cvsn_1-6.24>
4. ECD, página oficial do SPED: <https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd>
5. Manual ECD Leiaute 9, janeiro de 2026: <https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd/manuais-e-documentos-tecnicos/manual_de_orientacao_da_ecd_leiaute_9_janeiro_2026.pdf/@@display-file/file>
6. IN RFB nº 2.003/2021, texto publicado pelo SPED: <http://sped.rfb.gov.br/pagina/show/5727>
7. Orientações da Receita para 2026: <https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/orientacoes-2026>
8. LC nº 214 compilada, Planalto: <https://planalto.gov.br/ccivil_03/leis/lcp/lcp214compilado.htm>
9. Ajuste SINIEF 44/2020, CONFAZ: <https://www.confaz.fazenda.gov.br/legislacao/ajustes/2020/ajuste-sinief-44-20>
10. LGPD compilada, ANPD: <https://www.gov.br/anpd/pt-br/centrais-de-conteudo/legislacao/lei-no-13-709-de-14-de-agosto-de-2018>

## Correções factuais incorporadas

- O prazo normal da ECD foi corrigido de maio para o último dia útil de junho,
  conforme o Manual ECD de janeiro de 2026 e o art. 5º da IN RFB nº 2.003/2021.
- Ciência da Emissão não usa automaticamente o prazo de 180 dias. A fonte do
  CONFAZ informa até 10 dias para Ciência da Emissão; os demais eventos têm
  prazos próprios, que podem chegar a 180 dias.
- As alíquotas futuras de IBS/CBS não devem ser tratadas como uma tabela fixa sem
  vigência e fonte. O código de teste mantém a fase de 2026 parametrizada e
  marca a necessidade de atualização legal para os períodos seguintes.
- CFOP 1.252 não é um CFOP genérico de consultoria: a tabela do CONFAZ o define
  para compra de energia elétrica por estabelecimento industrial. O cenário de
  consultoria foi corrigido para CFOP 1.933, serviço sujeito ao ISSQN.
- A legislação da LGPD protege dados relacionados a pessoa natural. CNPJ de
  pessoa jurídica não deve ser classificado automaticamente como dado pessoal,
  mas CPF, nomes, contatos, responsáveis, sócios e representantes podem ser.

## 47 lacunas identificadas

### Contábeis, 12

1. **Partida dobrada completa**, CRITICAL. Validar contrapartida, natureza e
   fechamento do diário, além do valor por lançamento.
2. **Plano de contas com hierarquia**, HIGH. Validar níveis, conta-pai e
   distinção entre contas analíticas e sintéticas.
3. **Registro I200 completo**, HIGH. Incluir e validar indicador, número único,
   data no período e lançamentos extemporâneos.
4. **Histórico obrigatório no I250**, MEDIUM. Validar histórico não vazio,
   histórico padronizado e participante quando aplicável.
5. **Débitos e créditos por período**, CRITICAL. Conferir o diário contra os
   saldos periódicos e a soma das partidas.
6. **Registro I052**, MEDIUM. Gerar aglutinação somente para contas analíticas.
7. **Natureza contábil**, HIGH. Impedir combinação incoerente entre classes e
   natureza devedora ou credora.
8. **Encerramento do exercício**, MEDIUM. Gerar lançamentos de encerramento e
   validar saldo zero das contas de resultado.
9. **Código referencial ECD/I051**, HIGH. Mapear e validar o código oficial.
10. **Moeda funcional**, MEDIUM. Implementar campos `VL_LCTO_MF` e indicador
    quando a escrituração exigir moeda funcional.
11. **Centro de custos**, MEDIUM. Validar `COD_CCUS` contra o cadastro vigente.
12. **Balancete diário I300/I310**, MEDIUM. Gerar e conferir os saldos quando
    a modalidade de escrituração exigir.

### Fiscais, 18

13. **CFOP oficial**, CRITICAL. A lista local é apenas um subconjunto e precisa
    de sincronização versionada com a tabela vigente do CONFAZ.
14. **NCM vigente/TIPI**, CRITICAL. O código valida formato, mas não consulta a
    tabela TIPI nem detecta códigos extintos.
15. **Chave de acesso**, CRITICAL. O validador local calcula DV, mas a estrutura
    completa, CNPJ/CPF alfanumérico e regra por documento ainda exigem cobertura.
16. **Protocolo**, HIGH. Há validação de 15 ou 17 dígitos, mas falta validar a
    estrutura e a regra por UF e modelo.
17. **CST/CSOSN**, HIGH. Há allowlist mínima, mas falta matriz regime, CFOP,
    imposto e versão de tabela.
18. **Grupo IBS/CBS**, CRITICAL. Falta validar o grupo fiscal completo do XML,
    base, alíquota, valor e vigência da Nota Técnica.
19. **Transição IBS/CBS**, HIGH. Falta uma fonte versionada por vigência, ente
    e operação; não se deve fixar alíquotas futuras no código.
20. **CST de PIS/COFINS**, HIGH. A allowlist não substitui a validação por
    regime, natureza da receita e EFD-Contribuições.
21. **ICMS-ST**, MEDIUM. Falta cálculo completo de MVA, base ajustada e regras
    estaduais ou de convênio.
22. **IPI**, MEDIUM. Falta consultar a TIPI por NCM e validar a alíquota vigente.
23. **CFOP x NCM**, HIGH. Existe teste de compatibilidade serviço/mercadoria,
    mas falta matriz oficial completa.
24. **CNPJ/CPF do documento**, HIGH. Há validadores locais, mas o fluxo de
    importação ainda não bloqueia todos os participantes inválidos.
25. **Inscrição estadual**, MEDIUM. Falta validador por UF e regra para ISENTO.
26. **Data de emissão**, MEDIUM. Há teste de data futura, mas falta vínculo
    completo com competência, autorização e situação especial.
27. **Total da NF-e**, CRITICAL. Há cálculo local com frete e desconto, mas o
    XML completo precisa validar todos os totais, tributos e arredondamentos.
28. **Unidades de medida**, LOW. Falta tabela de unidades e conversão `uCom`/
    `uTrib`.
29. **Código do produto**, LOW. Falta bloquear vazio e tamanho superior ao
    limite do leiaute.
30. **NF-e complementar, ajuste e estorno**, MEDIUM. Falta tratar `finNFe`,
    chave referenciada e vínculo com a nota original.

### Legislativas, 10

31. **Obrigatoriedade ECD**, CRITICAL. A decisão precisa considerar a obrigação
    de escrituração comercial e a situação jurídica, não somente um limiar
    simplificado de faturamento.
32. **Prazo ECD**, HIGH. O prazo normal foi corrigido para junho; faltam
    situações especiais, prorrogações e calendário oficial parametrizado.
33. **Obrigações IBS/CBS em 2026**, CRITICAL. Falta controlar a emissão dos
    documentos eletrônicos e as DeRE quando disponibilizadas.
34. **Fase de 2026**, MEDIUM. Falta distinguir destaque, dispensa de recolhimento
    e cumprimento das obrigações acessórias conforme orientação vigente.
35. **Penalidades da transição**, MEDIUM. Falta política versionada para
    dispensa ou aplicação de penalidades, sem inferência automática.
36. **CNPJ de pessoa física contribuinte**, MEDIUM. Falta regra para o prazo e
    para o enquadramento informado pela Receita.
37. **Manifestação do destinatário**, HIGH. Falta separar o prazo de Ciência da
    Emissão, de até 10 dias, dos demais eventos.
38. **Rate limit SEFAZ**, HIGH. O sistema tem limitador local, mas precisa ser
    calibrado contra limites e respostas oficiais por serviço e ambiente.
39. **Guarda documental**, MEDIUM. Falta política operacional de retenção,
    arquivamento e bloqueio de exclusão antes do prazo aplicável.
40. **LGPD**, HIGH. Falta governança completa, base legal, canal do titular,
    política de retenção e controles de acesso.

### Técnicas, 7

41. **XSD oficial**, HIGH. O mock usa XML simplificado; falta validar pacote
    oficial vigente antes de persistir em homologação/produção.
42. **Assinatura digital**, HIGH. Falta validar assinatura XML e cadeia ICP-Brasil.
43. **Contingência**, MEDIUM. Falta tratar `tpEmis`, EPEC, FS-DA, SVC e NFC-e
    off-line.
44. **Compressão**, LOW. Falta suporte opcional a lotes comprimidos quando a
    Nota Técnica vigente exigir ou recomendar.
45. **Consulta por NSU**, MEDIUM. O fluxo inicial consulta a partir do último
    NSU, mas não expõe consulta pontual e paginação por NSU.
46. **Eventos**, HIGH. Falta processar cancelamento, CC-e, encerramento e
    sequência de eventos com regras de prazo.
47. **CNAE**, LOW. Falta validar CNAE vigente e compatibilidade com a operação.

## Priorização de execução

### Bloqueadores antes de produção fiscal

- XSD e assinatura digital;
- chave, CNPJ/CPF, CFOP, NCM, CST e totais completos;
- ECD válida no PVA, com registros e regras do leiaute vigente;
- IBS/CBS por Nota Técnica e vigência;
- autenticação, autorização e governança LGPD;
- eventos de cancelamento e manifestação.

### Próximo ciclo

- plano de contas e registros ECD I200/I250/I052/I300/I310;
- ICMS-ST, IPI, PIS/COFINS e retenções;
- NSU pontual, contingência e eventos;
- política de retenção e calendário de obrigações.

## Veredito

Os testes e contratos novos passaram no escopo implementado. O gate contábil e
o gate legislativo ficam como **PASSA COM LACUNAS**, porque os 47 itens acima
estão explicitamente rastreados e não foram mascarados como conformidade legal.
Para declarar o sistema fiscalmente pronto, os bloqueadores devem ser
implementados e validados no PVA, SEFAZ de homologação e com revisão contábil.
