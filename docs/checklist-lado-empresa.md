# Checklist do lado da empresa

## Objetivo

Este documento separa o que depende do sistema demonstrável do que depende de
processos, acessos e decisões internas da empresa. Nada desta lista precisa ser
resolvido para demonstrar o MVP com dados sintéticos e mock SEFAZ.

## 1. Responsáveis e processo

A empresa precisa definir:

- responsável pelo processo fiscal;
- responsável pelo processo contábil;
- responsável pela aprovação financeira;
- contador responsável e CRC;
- responsável técnico de TI;
- responsável por certificados e acessos;
- responsável por proteção de dados;
- fluxo de aprovação de divergências;
- fluxo de correção de lançamentos;
- prazo interno para conferência de notas;
- procedimento de fechamento mensal.

O sistema deve receber os nomes dos responsáveis, mas não deve depender de
credenciais pessoais compartilhadas.

## 2. Escopo operacional a confirmar

A empresa precisa esclarecer, em reunião:

- o que significa ETR no processo interno;
- se o trabalho será apenas auxiliar financeiro ou também fiscal/contábil;
- quais tipos de nota entram no processo;
- se o lançamento é feito no ERP ou em outro sistema;
- quem confere pedido, recebimento e nota;
- quem autoriza uma divergência;
- se pagamentos ficam no ERP, banco ou planilha;
- se existe integração por arquivo, API ou digitação;
- quais relatórios são obrigatórios no fechamento.

O MVP atual demonstra importação, reconciliação, lançamentos e exportação. Ele
não presume como a empresa trabalha.

## 3. Cadastros e regras internas

A empresa precisa fornecer ou aprovar:

- plano de contas;
- contas para estoque, despesas, fornecedores e impostos;
- mapeamento CFOP para contas;
- mapeamento NCM e tipo de produto;
- regra de ativo imobilizado;
- regra de material de consumo;
- regra de serviço;
- regra de devolução;
- regra de frete;
- regra de desconto;
- regra de impostos recuperáveis;
- tolerância de preço;
- tolerância de quantidade;
- tolerância de data;
- exigência de pedido de compra;
- exigência de recebimento;
- política para nota sem pedido;
- política para nota cancelada;
- política para lançamento manual.

Sem essas decisões, o sistema só pode demonstrar regras genéricas e deixar o
mapeamento como configuração pendente.

## 4. Dados que a empresa precisa disponibilizar

Para homologação, solicitar dados anonimizados ou ambiente de teste:

- exemplos de XML autorizados;
- exemplos de XML cancelados;
- nota de devolução;
- nota de serviço;
- nota com frete;
- nota com desconto;
- nota com ICMS-ST;
- nota com IPI, PIS e COFINS;
- pedidos de compra;
- recebimentos;
- contas contábeis;
- lançamentos esperados;
- relatórios atuais;
- arquivos ECD já transmitidos, se a empresa autorizar;
- exemplos de divergências reais.

Nunca usar dados reais de funcionário, cliente ou fornecedor na demonstração
sem autorização. Para a entrevista, usar somente o mock e dados sintéticos.

## 5. Acessos que dependem da empresa

Estes itens não devem ser improvisados pelo desenvolvedor:

### Certificados

- e-CNPJ ou certificado equivalente;
- decisão entre HSM, nuvem e A1;
- autorização para uso automatizado;
- cadeia de certificados;
- política de rotação e revogação;
- ambiente de homologação;
- ambiente de produção separado.

### Receita e e-CAC

- Autorização de Acesso ou procuração RFB;
- escopo para ECD;
- escopo para serviços contábeis, se aplicável;
- validade da procuração;
- responsável pela confirmação.

### SEFAZ

- UF de cada estabelecimento;
- inscrição estadual;
- autorização para NF-e/DF-e;
- URLs oficiais de homologação;
- URLs oficiais de produção;
- serviços liberados;
- regras específicas da UF.

### SERPRO

Somente se contratado pela empresa:

- Consulta CNPJ;
- Integra Contador;
- consumer key;
- consumer secret;
- escopos;
- ambiente sandbox;
- ambiente de produção;
- franquia e custo.

### Infraestrutura

- banco de produção;
- secret manager;
- HSM ou serviço de certificado;
- backups;
- monitoramento;
- rede e allowlist;
- política de acesso ao ERP;
- ambiente de homologação.

## 6. Aprovações necessárias

Antes de usar dados ou transmitir qualquer arquivo, a empresa precisa aprovar:

- uso de dados fiscais;
- uso de dados pessoais;
- retenção de XML;
- armazenamento de certificados;
- integração com ERP;
- transmissão de eventos;
- transmissão da ECD;
- usuários autorizados;
- relatórios oficiais;
- critérios de auditoria.

## 7. O que não é necessário para a demonstração

Para mostrar o sistema na entrevista, não são necessários:

- certificado real;
- senha de certificado;
- acesso ao e-CAC;
- procuração RFB;
- acesso de produção à SEFAZ;
- contrato SERPRO;
- dados reais de clientes ou fornecedores;
- conexão com o ERP da empresa;
- transmissão de ECD;
- emissão real de NF-e.

## 8. Critério de passagem para homologação

O sistema pode sair da demonstração e entrar em homologação quando a empresa
entregar:

- responsável de negócio;
- regras de contabilização aprovadas;
- dados anonimizados;
- certificado de homologação;
- UF e inscrição estadual;
- ambiente separado;
- plano de testes;
- autorização de acesso;
- critério de aceite contábil;
- procedimento de rollback.

## 9. Regra de segurança

O desenvolvedor nunca deve pedir para receber por mensagem:

- PFX/P12;
- senha;
- PIN;
- chave privada;
- consumer secret;
- token OAuth;
- senha de e-CAC;
- cookie de sessão;
- chave de banco de produção.

Esses dados devem ser cadastrados pela empresa no cofre ou no ambiente seguro
dela.
