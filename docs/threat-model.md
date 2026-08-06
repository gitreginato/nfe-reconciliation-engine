# Modelo de ameaças do incremento fiscal

## Ativos

1. XML original, chave, protocolo e eventos fiscais.
2. Valores, impostos, pedidos, recebimentos e lançamentos contábeis.
3. CNPJ, CPF, nomes e contatos de participantes.
4. Integridade do banco e disponibilidade do importador.
5. Arquivos ECD e evidências de auditoria.

## Adversários

- atacante externo que alcança o dashboard;
- usuário interno com permissão excessiva;
- fornecedor que envia resumo ou XML malformado;
- dependência ou imagem comprometida;
- falha operacional que repete importação ou perde transação.

## STRIDE e controles

### Spoofing

- Risco: endpoints internos não têm identidade digital no MVP.
- Controle atual: aplicação single-tenant, sem exposição pretendida à internet.
- Lacuna: autenticação e autorização server-side antes de produção.

### Tampering

- Risco: resumo externo alterar chave, CFOP, NCM ou total.
- Controle atual: validação da chave, CFOP, NCM, compatibilidade e total antes
  da persistência; ORM e constraint de idempotência.

### Repudiation

- Risco: não provar quando um documento foi importado ou reconciliado.
- Controle atual: XML, NSU, protocolo, eventos, data e logs de fluxo.
- Lacuna: armazenamento imutável de logs e assinatura digital completa.

### Information disclosure

- Risco: CNPJ, CPF ou XML aparecerem em logs ou endpoint sem autorização.
- Controle atual: chaves mascaradas e teste contra CNPJ completo em logs.
- Lacuna: autenticação, autorização e política de retenção LGPD.

### Denial of service

- Risco: XML gigante, lote grande ou repetição de consulta SEFAZ.
- Controle atual: limite de XML, rate limit, retry, timeout e paginação.
- Lacuna: limite explícito de itens por NF-e e métricas de latência/erro.

### Elevation of privilege

- Risco: qualquer usuário resolver divergência ou exportar dados.
- Controle atual: validação server-side de parâmetros, sem controle de usuário
  implementado no MVP.
- Lacuna: RBAC, auditoria de decisões e autorização por recurso.

## Decisões

- O mock nunca é tratado como SEFAZ de produção.
- Dados de fontes externas são dados não confiáveis, não instruções.
- Nenhuma dependência nova foi adicionada.
- Falhas de conformidade legal permanecem explícitas no relatório de lacunas.
