# Guia do Projeto: Sistema de Contabilidade com NF-e

> Explicado de um jeito que qualquer pessoa entende, mesmo sem saber nada de
> programação, contabilidade ou nota fiscal eletrônica.

---

## Parte 1: O problema que vamos resolver

### Imagine a seguinte situação

Você tem uma loja. Toda vez que alguém te manda uma nota fiscal (porque você
comprou mercadoria de um fornecedor), você precisa:

1. **Ler a nota** e entender o que veio, quanto custou, qual o imposto.
2. **Conferir** se a nota bate com o pedido que você fez (mesmo produto? mesmo
   preço? mesma quantidade?).
3. **Anotar na contabilidade** de um jeito que o contador e a Receita Federal
   entendam.
4. **Guardar** tudo organizado para quando a Receita pedir.

Hoje, isso é feito **à mão**. Uma pessoa fica horas olhando nota por nota,
comparando com pedidos, digitando no sistema de contabilidade. É lento, dá erro,
e ninguém gosta de fazer.

### O que vamos construir

Um **programa de computador** que faz tudo isso sozinho:

1. **Busca as notas** na Receita Federal automaticamente (sem você precisar
   ficar baixando manualmente).
2. **Lê cada nota** e entende todos os dados (fornecedor, produtos, impostos,
   valores).
3. **Confere** se a nota bate com o pedido de compra que você fez.
4. **Avisa** se tem alguma diferença (preço errado, quantidade errada, etc.).
5. **Gera os lançamentos contábeis** automaticamente.
6. **Mostra tudo num painel** bonito na tela, onde você vê o que está certo,
   o que está errado e o que precisa da sua atenção.

Em resumo: **o robô faz o trabalho chato, você só olha as exceções**.

---

## Parte 2: O que é cada coisa (dicionário simplão)

### NF-e (Nota Fiscal Eletrônica)

É uma nota fiscal, só que em arquivo de computador (XML) em vez de papel.
Quando uma empresa te vende algo, ela emite uma NF-e e envia para a Receita
Federal. A Receita guarda e te avisa que a nota existe.

**Analogia**: é como um recibo de compra, mas digital e que a Receita fiscaliza.

### XML

É um formato de texto para guardar dados estruturados. Parece com HTML (aquele
das páginas web), mas serve para dados, não para telas.

```xml
<nota>
  <fornecedor>Padaria São João</fornecedor>
  <valor>50.00</valor>
</nota>
```

**Analogia**: é como um formulário preenchido que o computador sabe ler.

### Receita Federal (SEFAZ)

É o órgão do governo que cuida dos impostos. No caso de notas fiscais, cada
estado tem uma SEFAZ (Secretaria da Fazenda). A Receita Federal junta tudo no
"Ambiente Nacional".

**Analogia**: é como o correio das notas fiscais. Quem emite entrega lá, quem
recebe vai buscar lá.

### NFeDistribuicaoDFe

É o nome do "serviço de busca" da Receita. Você pergunta "tem alguma nota nova
para meu CNPJ?" e ele responde com as notas.

**Analogia**: é como checar a caixa de correio para ver se chegou carta nova.

### CNPJ

É o "CPF da empresa". Todo mundo tem CPF. Toda empresa tem CNPJ. A Receita usa
o CNPJ para saber de quem é cada nota.

### Certificado Digital A1

É como se fosse a "identidade digital" da empresa. É um arquivo de computador
(.pfx ou .p12) que prova que você é realmente a empresa. Sem ele, a Receita não
deixa você buscar notas.

**Analogia**: é como a carteira de identidade, mas para o computador. Sem ela,
o sistema da Receita não te reconhece.

### Manifestação do Destinatário

Quando uma nota chega para você na Receita, ela vem só com o "resumo" (valor
total, fornecedor, data). Para ver a nota completa (com todos os itens), você
precisa dizer "eu sei que essa nota existe". Isso se chama manifestação.

Existem 4 tipos:

1. **Ciência da Emissão**: "sei que a nota existe, mas ainda não confirmo se
   recebi".
2. **Confirmação da Operação**: "sim, recebi a mercadoria e a nota está certa".
3. **Desconhecimento**: "não reconheço essa operação, não comprei nada desse
   fornecedor".
4. **Operação não Realizada**: "a operação foi combinada mas não aconteceu".

**Analogia**: é como quando o carteiro te avisa que tem uma carta. Você precisa
dizer "ok, eu sei" para ele te entregar a carta completa.

### Reconciliação (Three-way matching)

É o processo de conferir se 3 coisas batem:

1. **Pedido de compra**: o que você pediu para o fornecedor.
2. **Recebimento**: o que realmente chegou na sua porta.
3. **Nota fiscal**: o que o fornecedor está cobrando.

Se os 3 baterem, tudo certo. Se algum for diferente, tem problema.

**Analogia**: é como conferir a conta do restaurante. Você pediu (cardápio),
veio a comida (prato), e a conta (nota). Se os 3 baterem, paga. Se não, chama o
garçom.

### Tolerância

Ninguém é perfeito. Se o preço veio 1% diferente do pedido, tudo bem. Se veio
20% diferente, tem problema. A tolerância é o "quanto de diferença eu aceito
sem me preocupar".

No nosso sistema:
- Preço: aceita até 2% de diferença.
- Quantidade: aceita até 5% de diferença.
- Data: aceita até 3 dias de diferença.

**Analogia**: é como quando você vai no mercado e o preço da banana subiu 10
centavos. Você não briga por isso. Mas se dobrou, você questiona.

### CFOP (Código Fiscal de Operações e Prestações)

É um código de 4 dígitos que diz "que tipo de operação é essa". Exemplos:

- **1102**: compra de mercadoria para revender (dentro do estado).
- **1551**: compra de bem para o ativo imobilizado (comprar uma máquina).
- **5102**: venda de mercadoria (para cliente dentro do estado).

O CFOP determina como o lançamento contábil é feito (qual conta debitar, qual
creditar).

**Analogia**: é como a etiqueta que você cola numa caixa dizendo "isto é
comida", "isto é roupa", "isto é ferramenta". O sistema usa a etiqueta para
saber onde guardar.

### Lançamento Contábil

Na contabilidade, tudo é registrado em "débito e crédito". Não é débito de
cartão. É assim:

- **Débito**: onde o valor entrou (ex.: estoque aumentou).
- **Crédito**: de onde o valor saiu (ex.: deve ao fornecedor).

Sempre tem que bater: soma do débito = soma do crédito.

**Analogia**: é como uma balança de dois pratos. Se você põe 50 de um lado,
tem que pôr 50 do outro. Senão a balança não equilibra.

### Plano de Contas Referencial

A Receita Federal criou um "plano de contas padrão" para todas as empresas. Em
vez de cada empresa usar nomes diferentes ("estoque", "mercadorias",
"produtos"), todo mundo usa o mesmo código (ex.: 1.1.3.01.01 = estoque de
mercadorias).

Isso permite que a Receita cruze dados entre empresas.

**Analogia**: é como se todos os restaurantes do Brasil usassem o mesmo cardápio
com os mesmos números. "Prato 1" é arroz em qualquer lugar. Facilita comparar.

### SPED (Sistema Público de Escrituração Digital)

É o sistema da Receita que recebe as obrigações contábeis e fiscais das
empresas por arquivo digital. Tem várias partes:

- **ECD** (Escrituração Contábil Digital): os lançamentos contábeis do ano.
- **ECF** (Escrituração Contábil Fiscal): a apuração do IRPJ e CSLL.
- **EFD ICMS/IPI**: a apuração do ICMS e IPI por mês.
- **EFD Contribuições**: a apuração do PIS e COFINS por mês.

A Receita cruza tudo isso para achar inconsistências.

**Analogia**: é como a Receita pedir 4 relatórios diferentes da sua empresa e
depois conferir se os números batem entre eles. Se não bater, você é intimado.

### Reforma Tributária (IBS e CBS)

A partir de 2026, o Brasil está mudando os impostos. PIS, COFINS, ICMS e ISS
estão sendo substituídos por:

- **CBS** (Contribuição sobre Bens e Serviços): imposto federal.
- **IBS** (Imposto sobre Bens e Serviços): imposto estadual + municipal.
- **Imposto Seletivo**: para produtos prejudiciais (cigarro, bebida).

A partir de **03/08/2026**, toda NF-e precisa ter os campos de IBS e CBS
preenchidos. Senão a Receita rejeita a nota.

**Analogia**: é como se o governo mudasse as regras do jogo no meio da partida.
Todo mundo precisa se adaptar.

---

## Parte 3: As peças do sistema (o que cada uma faz)

### 1. Importador DF-e

**O que faz**: conecta na Receita Federal, busca notas novas, traz para o nosso
banco.

**Analogia**: é o carteiro do sistema. Sai de manhã, busca as cartas (notas) no
correio (Receita), traz para casa (banco de dados).

### 2. Parser XML

**O que faz**: lê o arquivo XML da nota e transforma em dados que o sistema
entende (fornecedor, itens, valores, impostos).

**Analogia**: é como alguém que abre a carta e lê em voz alta para você, em
vez de você mesmo ter que decifrar a letra.

### 3. Banco de dados (PostgreSQL)

**O que faz**: guarda tudo de forma organizada. As notas, os fornecedores, os
itens, os impostos, as reconciliações, os lançamentos contábeis.

**Analogia**: é como um armário com gavetas etiquetadas. Cada gaveta guarda um
tipo de coisa. Você pode buscar rápido quando precisar.

### 4. Motor de Reconciliação

**O que faz**: pega cada nota que chegou e tenta achar o pedido de compra
correspondente. Compara valores, quantidades, datas. Se bater, marca como
"conferido". Se não bater, marca como "divergente".

**Analogia**: é como um conferente de supermercado. Ele olha a nota fiscal, olha
o que está no carrinho, e diz "tudo certo" ou "tem diferença".

### 5. Gerador de Lançamentos Contábeis

**O que faz**: para cada nota reconciliada, gera o lançamento contábil
automático (qual conta debitar, qual creditar) baseado no CFOP.

**Analogia**: é como um tradutor. A nota fala "compra de mercadoria para
revenda" (CFOP 1102), e o tradutor escreve no livro contábil "débito estoque,
crédito fornecedores".

### 6. Dashboard (painel web)

**O que faz**: mostra tudo na tela. Quantas notas importadas, quantas
conferidas, quantas com problema, valor total. Você clica e vê o detalhe.

**Analogia**: é como o painel do carro. Você não precisa abrir o capô para saber
se está tudo bem. O painel te avisa se tem problema.

### 7. Mock SEFAZ (para testes)

**O que faz**: simula a Receita Federal no seu computador, para você testar o
sistema sem precisar de certificado digital real nem CNPJ.

**Analogia**: é como um simulador de voo. Você aprende a pilotar sem precisar de
avião de verdade.

---

## Parte 4: As tecnologias (o que é cada uma)

### Python

A linguagem de programação que vamos usar. É a mais usada para análise de dados
no Brasil. Fácil de ler, muita biblioteca, comunidade grande.

**Analogia**: é o idioma que o sistema fala. Python é como o português: todo
mundo entende, muita gente fala.

### FastAPI

É o framework que cria a parte web do sistema (a API e o painel).

**Analogia**: é como o esqueleto de uma casa. Você não constrói do zero, usa o
esqueleto e vai colocando as paredes, o telhado, os móveis.

### PostgreSQL

O banco de dados. Guarda tudo de forma organizada e permite buscar rápido.

**Analogia**: é como um Excel muito poderoso que aguenta milhões de linhas sem
travar.

### Redis

Um banco de dados mais simples e rápido, usado para coisas temporárias (fila de
importação, controle de "qual foi a última nota buscada").

**Analogia**: é como um bloco de notas ao lado do telefone. Você anota rápido
para não esquecer, mas não guarda para sempre.

### Docker

Cria "containers" que isolam o sistema. Em vez de instalar PostgreSQL, Redis e
tudo mais direto no seu computador, o Docker cria ambientes separados que
rodam igual em qualquer máquina.

**Analogia**: é como levar uma maleta com tudo que você precisa. Abre a maleta,
monta seu escritório, e quando acaba, fecha e leva embora. Não suja o lugar.

### nfelib

A biblioteca Python que lê e escreve XML de notas fiscais. Foi feita pela
Akretion, uma empresa que mantém a localização brasileira do Odoo (um ERP
mundial) desde 2009.

**Analogia**: é como um dicionário português-inglês. Você não precisa saber
inglês para traduzir, o dicionário faz para você.

### erpbrasil.edoc

A biblioteca Python que faz a comunicação com a Receita (via webservice SOAP,
com certificado digital).

**Analogia**: é como o telefone que você usa para ligar para a Receita. Você
não precisa entender como o telefone funciona por dentro, só discar.

### pytest

A ferramenta que roda os testes. Você escreve "dado isso, quando faço aquilo,
espero este resultado", e o pytest verifica se está certo.

**Analogia**: é como um inspetor de qualidade na fábrica. Ele pega cada peça,
testa, e diz "aprovada" ou "reprovada".

---

## Parte 5: Como o sistema funciona (passo a passo)

### Fluxo completo, do início ao fim

```
1. A empresa "Padaria São João" te vende farinha.
   Ela emite uma NF-e e envia para a Receita Federal.

2. A Receita Federal guarda a NF-e e avisa que tem nota nova
   para o seu CNPJ.

3. O nosso Importador DF-e conecta na Receita (com certificado)
   e pergunta: "tem nota nova?"
   A Receita responde: "sim, tem uma do CNPJ 12.345.678/0001-90".

4. O Importador envia "Ciência da Emissão" para a Receita.
   A Receita responde: "ok, agora você pode ver a nota completa".

5. O Importador busca a nota completa (XML) e entrega para o Parser.

6. O Parser lê o XML e extrai:
   - Fornecedor: Padaria São João (CNPJ 12.345.678/0001-90)
   - Item 1: 10 sacos de farinha, R$ 25 cada, total R$ 250
   - ICMS: R$ 50
   - Valor total da nota: R$ 250

7. O sistema guarda tudo no PostgreSQL (tabelas nfe, participante,
   nfe_item, nfe_tributo).

8. O Motor de Reconciliação pega a nota e procura:
   "Tem algum pedido de compra da Padaria São João no valor de R$ 250?"
   Encontra o pedido PC-001.

9. O Motor compara:
   - Pedido: 10 sacos a R$ 25 = R$ 250
   - Nota: 10 sacos a R$ 25 = R$ 250
   - Tudo bate! Marca como "matched".

10. O Gerador de Lançamentos Contábeis pega a nota reconciliada
    e gera:
    - Débito: Estoque de Mercadorias (1.1.3.01.01) R$ 200
    - Débito: ICMS a Recuperar (1.1.5.01.01) R$ 50
    - Crédito: Fornecedores (2.1.01.01.01) R$ 250

11. O Dashboard mostra:
    "Notas importadas hoje: 1"
    "Notas conferidas: 1"
    "Notas com problema: 0"
    "Valor total: R$ 250"

12. No fim do mês, você exporta tudo para o contador.
    Ele usa para gerar o SPED e entregar à Receita.
```

### E quando tem problema?

```
1. A empresa "Fábrica de Móveis" te manda uma nota de 20 cadeiras
   a R$ 100 cada = R$ 2.000.

2. Mas você tinha pedido 20 cadeiras a R$ 80 cada = R$ 1.600.

3. O Motor de Reconciliação compara:
   - Pedido: 20 cadeiras a R$ 80 = R$ 1.600
   - Nota: 20 cadeiras a R$ 100 = R$ 2.000
   - Diferença de preço: 25% (acima da tolerância de 2%)

4. O Motor marca como "divergent" e registra:
   "Divergência de preço: esperado R$ 80, recebido R$ 100,
    diferença 25% no item 1 (cadeira)."

5. O Dashboard mostra:
    "Notas com problema: 1"
    Você clica e vê o detalhe da divergência.

6. Você decide:
    - Aceitar a divergência (pagar os R$ 2.000)
    - Rejeitar a nota (pedir nova nota com preço certo)
    - Negociar com o fornecedor

7. O sistema registra sua decisão na trilha de auditoria:
    "Usuário Lucas aceitou divergência em 05/08/2026,
     justificativa: fornecedor reajustou preço."
```

---

## Parte 6: Como testar sem ter empresa nem certificado

### Você não precisa de empresa real para desenvolver

O sistema tem um **modo de teste** que simula tudo:

1. **Mock SEFAZ**: um servidor falso que finge ser a Receita. Retorna notas de
   exemplo quando o sistema pergunta "tem nota nova?".

2. **Notas de exemplo**: o nfelib já vem com notas fiscais reais (anonimizadas)
   dentro do repositório. Usamos elas para testar o parser.

3. **Gerador sintético**: uma função que cria notas fiscais falsas com
   diferentes cenários (com divergência, sem divergência, cancelada, com IBS,
   etc.) para testar o motor de reconciliação.

### Quando você for usar de verdade

Você precisa de:

1. **CNPJ**: sua empresa precisa ter um CNPJ ativo.
2. **Certificado digital A1**: compra em uma autoridade certificadora
   (Serasa, Certisign, etc.). Custa R$ 200 a R$ 400 por ano.
3. **Computador ligado**: o importador precisa rodar periodicamente para buscar
   notas novas.

### Para emissão de notas (fase 2)

Você usa uma API comercial (NFE.io ou BrasilNFe) que cuida de tudo:
certificado, comunicação com SEFAZ, DANFE. Você paga por nota emitida
(R$ 0,10 a R$ 0,50 por nota).

---

## Parte 7: Estrutura do projeto (onde fica cada coisa)

```
contabilidade/
├── src/                    # Código do sistema
│   ├── importador/         # Importador DF-e (busca notas na Receita)
│   ├── parser/             # Parser XML (lê as notas)
│   ├── persistencia/       # Guarda no banco de dados
│   ├── reconciliacao/      # Motor de reconciliação (conferir notas)
│   ├── contabilidade/      # Gerador de lançamentos contábeis
│   ├── dashboard/          # Painel web (FastAPI + Jinja2)
│   └── mock_sefaz/         # Mock da Receita para testes
├── tests/                  # Testes automatizados
├── docker/                 # Configuração do Docker
│   ├── docker-compose.yml  # Sobe PostgreSQL + Redis + sistema
│   └── Dockerfile          # Receita para criar o container
├── schemas/                # Schemas XSD da Receita (validação XML)
├── docs/                   # Documentação
│   ├── guia-simples.md     # Este arquivo
│   ├── spec.md             # Especificação técnica
│   └── kanban.md           # Quadro de tarefas
├── AGENTS.md               # Guia para agentes de IA (Devin, etc.)
├── requirements.txt        # Lista de dependências (versões pinadas)
└── README.md               # Apresentação do projeto
```

---

## Parte 8: O que cada arquivo faz

### requirements.txt

Lista todas as bibliotecas Python que o sistema usa, com versão exata. Isso
garante que o sistema rode igual em qualquer computador.

**Analogia**: é como a lista de ingredientes de uma receita. Se você trocar a
marca da farinha, o bolo pode dar errado.

### docker-compose.yml

Configuração que diz "suba um PostgreSQL, um Redis e o sistema, todos
conectados". Um comando só sobe tudo.

**Analogia**: é como o botão "ligar" do carro. Você não precisa ligar cada peça
separada, o botão liga tudo de uma vez.

### Dockerfile

Receita para criar a "imagem" do sistema. Diz qual versão do Python, quais
bibliotecas, qual código incluir.

**Analogia**: é como a planta de uma casa. Diz onde vai cada cômodo, qual
material, qual acabamento.

### AGENTS.md

Guia para agentes de IA (como eu, Devin) que forem trabalhar no projeto. Diz
quais comandos rodar, quais convenções seguir, onde está cada coisa.

**Analogia**: é como o manual do funcionário novo. Diz onde fica a cafeteira,
qual o horário, como usar o sistema de ponto.

### spec.md

A especificação técnica do sistema. O "contrato" que diz o que o sistema deve
fazer. Cada funcionalidade tem um critério de aceitação testável.

**Analogia**: é como o contrato de obra. Diz quantos cômodos, qual tamanho,
qual acabamento. Se o pedreiro fizer diferente, você aponta o contrato.

### kanban.md

O quadro de tarefas. Mostra o que já foi feito, o que está sendo feito e o que
vai ser feito. Organizado em colunas (Backlog, To Do, Doing, Done).

**Analogia**: é como um quadro de avisos com post-its. Cada post-it é uma
tarefa. Você move de uma coluna para outra conforme avança.

---

## Parte 9: Como rodar o sistema (quando estiver pronto)

### Primeira vez

```bash
# 1. Entrar na pasta do projeto
cd /home/vsf/Projetos/contabilidade

# 2. Subir os containers (PostgreSQL + Redis + sistema)
docker compose up -d

# 3. Rodar as migrações do banco (criar as tabelas)
docker compose exec app alembic upgrade head

# 4. Abrir o navegador
# O dashboard vai estar em http://localhost:8000
```

### Para importar notas

```bash
# Importação manual (dispara uma busca na Receita)
curl -X POST http://localhost:8000/api/importacao/executar
```

Ou pelo dashboard: botão "Importar notas agora".

### Para testar

```bash
# Rodar todos os testes
docker compose exec app pytest

# Rodar com cobertura
docker compose exec app pytest --cov=src
```

### Para parar

```bash
docker compose down
```

---

## Parte 10: Perguntas frequentes

### "Eu preciso saber programar para usar?"

Não. O sistema vai ter uma interface web. Você usa pelo navegador, como
qualquer site. Programar é só para quem quiser modificar o sistema.

### "Eu preciso de certificado digital para testar?"

Não. O modo de teste (MOCK_SEFAZ=true) simula a Receita. Você testa tudo sem
certificado.

### "O sistema funciona para qualquer empresa?"

O MVP é para uma empresa só (single-tenant). Na fase 2, pode virar
multi-empresa.

### "O sistema emite notas fiscais?"

Não no MVP. A emissão vai ser feita por API comercial (NFE.io ou BrasilNFe) na
fase 2. O MVP só importa e reconcilia notas que você recebeu.

### "O sistema substitui o contador?"

Não. O sistema faz o trabalho operacional (importar, conferir, lançar). O
contador continua sendo necessário para interpretar, planejar tributos e
assinar documentos. O sistema é uma ferramenta para o contador, não um
substituto.

### "O sistema serve para NFS-e (nota de serviço)?"

Não no MVP. NFS-e municipal tem um padrão diferente para cada cidade (mais de
450 padrões no Brasil). Fica para a fase 2.

### "E a reforma tributária (IBS/CBS)?"

O sistema já está sendo construído com os campos de IBS e CBS (NT 2025.002
v1.50). A partir de 03/08/2026, toda nota precisa ter esses campos. Nosso
schema do banco já tem as colunas `vbc_ibscbs`, `vibscbs`, `aliquota_ibscbs`.

### "Quanto custa rodar?"

Para desenvolver e testar: **zero** (tudo open source, Docker local).

Para produzir:
- Certificado A1: R$ 200 a R$ 400/ano.
- Hospedagem (se quiser na nuvem): R$ 30 a R$ 100/mês.
- Emissão de notas (fase 2, API comercial): R$ 0,10 a R$ 0,50 por nota.

### "É seguro?"

O sistema segue as práticas OWASP de secure coding:
- Senhas e certificados nunca ficam no código (sempre em variável de ambiente).
- Queries SQL sempre parametrizadas (sem injeção SQL).
- Validação de input externo (XML da Receita é validado contra XSD).
- Logs sem dados sensíveis (CNPJ mascarado, valores não logados em produção).
- Dependências pinadas (versão exata, sem risco de atualização maliciosa).

---

## Parte 11: Funcionalidades da Fase 7 (fechamento de lacunas)

A Fase 7 fechou 8 lacunas que estavam faltando para o sistema estar completo
no escopo offline (sem certificado nem APIs governamentais).

### 1. Cálculo tributário determinístico

O sistema agora **calcula** ICMS, ICMS-ST, IPI, PIS e COFINS por item, não
apenas valida os campos que vieram na nota.

**Analogia**: antes o sistema só conferia se o imposto veio escrito na nota.
Agora ele mesmo faz a conta: "valor vezes alíquota = imposto".

As alíquotas são parametrizadas por tabela (origem, destino, NCM, CST), nunca
inventadas. Se a tabela não tem a alíquota, o sistema avisa com um alerta em
vez de calcular errado.

### 2. Apuração mensal

Novo endpoint: `GET /api/apuracao/{ano}/{mes}`

Fecha o mês e calcula:
- **Créditos**: impostos recuperáveis das entradas (compras)
- **Débitos**: impostos gerados nas saídas (vendas)
- **Saldo a recolher**: débitos menos créditos (se positivo)
- **Saldo a compensar**: créditos maiores que débitos (se negativo)

**Analogia**: é como fechar a carteira no fim do mês. Quanto entrou, quanto
saiu, e quanto você precisa pagar (ou quanto sobrou).

### 3. SPED/ECD layout oficial

O exportador ECD agora gera os blocos completos do Leiaute 9 (IN RFB
2.003/2021):
- Bloco 0: abertura
- Bloco I: identificação, plano de contas, lançamentos
- Bloco J: demonstrações (DRE e Balanço Patrimonial)
- Bloco K: livro caixa e livro razão auxiliar
- Bloco 9: encerramento e totais

**Analogia**: antes o sistema gerava um CSV simples. Agora gera no formato
que o programa da Receita (PVA ECD) aceita.

### 4. Manifestação do destinatário automatizada

Novos endpoints:
- `POST /api/manifestacao/executar`: manifesta em lote
- `GET /api/manifestacao/pendentes`: lista notas pendentes

O sistema identifica notas que precisam de manifestação, verifica prazos
legais (10 dias para ciência, 180 para confirmação) e manifesta em lote,
respeitando o rate limit da SEFAZ.

**Analogia**: antes você tinha que manifestar nota por nota. Agora o sistema
faz sozinho: "tem 50 notas sem ciência, vou manifestar todas, respeitando o
limite de 3 por segundo".

### 5. CI/CD pipeline automatizado

GitHub Actions roda automaticamente em todo push e pull request:
- Testes unitários
- Testes de integração
- Cobertura mínima de 70%
- Lint (ruff)

**Analogia**: é como um inspetor que verifica tudo automaticamente toda vez
que você muda algo no código. Se algo quebra, ele avisa antes de ir para
produção.

### 6. Cobertura de testes do gerador e ECD

Foram adicionados 29 testes dedicados:
- 15 testes do gerador de lançamentos contábeis
- 14 testes do exportador ECD

Cobrem: todos os CFOPs, estorno, idempotência, partida dobrada, DRE, balanço,
validações de período e CNPJ.

### 7. Rate limit exercitado em testes de integração

8 testes que exercitam o rate limiter contra Redis real:
- Limite de chamadas por janela
- Bloqueio da 4ª chamada
- Sanitização de chave
- Janelas independentes
- Reset após expiração

### 8. Parser XML com validação XSD

16 testes que exercitam:
- Validação estrutural (campos obrigatórios do layout 4.00)
- Validação XSD com lxml contra schema oficial
- Proteção contra XXE (XML External Entity)
- Limite de tamanho (prevenção de DoS)
- Rejeição de XML mal formado

**Analogia**: antes o sistema só checava se os campos existiam. Agora ele
valida contra o schema oficial da Receita, igual ao que o PVA usa.

---

## Parte 12: Como demonstrar o sistema (roteiro para entrevista)

### Subir o ambiente

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

### Rodar os testes

```bash
docker exec contabilidade-app python -m pytest -q
```

Resultado: **258 testes passando**.

### Importar notas do mock SEFAZ

```bash
curl -s -X POST http://localhost:8000/api/importacao/executar
```

### Reconciliar

```bash
curl -s -X POST http://localhost:8000/api/reconciliacao/popular-pedidos
curl -s -X POST http://localhost:8000/api/reconciliacao/executar
```

### Gerar lançamentos contábeis

```bash
curl -s -X POST http://localhost:8000/api/lancamentos/executar
```

### Apurar impostos do mês

```bash
curl -s http://localhost:8000/api/apuracao/2026/7
```

### Manifestar em lote

```bash
curl -s -X POST http://localhost:8000/api/manifestacao/executar
```

### Exportar ECD

```bash
curl -s "http://localhost:8000/api/export/ecd?data_inicio=2026-07-01&data_fim=2026-07-31"
```

### Abrir o dashboard

Navegador: `http://localhost:8000`

---

## Parte 13: Glossário rápido (para consultar quando esquecer)

| Palavra | O que é (em 1 frase) |
|---|---|
| NF-e | Nota fiscal em arquivo de computador (XML) |
| NFS-e | Nota fiscal de serviço eletrônica (municipal) |
| CT-e | Nota fiscal de transporte |
| MDF-e | Manifesto de carga (agrupa vários CT-e) |
| DANFE | Impressão da NF-e (o papel que acompanha a carga) |
| XML | Formato de texto para dados estruturados |
| CNPJ | CPF da empresa |
| SEFAZ | Secretaria da Fazenda (estadual) |
| Receita Federal | Órgão federal dos impostos |
| Certificado A1 | Identidade digital da empresa |
| DF-e | Documento fiscal eletrônico (nome genérico) |
| NSU | Número sequencial único (identificador da nota na Receita) |
| Manifestação | Dizer à Receita que você sabe que a nota existe |
| CFOP | Código que diz o tipo de operação (compra, venda, etc.) |
| NCM | Código do produto (classificação internacional) |
| ICMS | Imposto estadual sobre circulação de mercadorias |
| IPI | Imposto federal sobre produtos industrializados |
| PIS | Imposto federal sobre faturamento |
| COFINS | Imposto federal sobre faturamento |
| IBS | Novo imposto estadual/municipal (substitui ICMS/ISS) |
| CBS | Novo imposto federal (substitui PIS/COFINS) |
| SPED | Sistema da Receita que recebe obrigações digitais |
| ECD | Escrituração contábil digital (lançamentos do ano) |
| ECF | Escrituração contábil fiscal (apuração do IRPJ) |
| EFD | Escrituração fiscal digital (ICMS/IPI mensal) |
| Reconciliação | Conferir se nota, pedido e recebimento batem |
| Three-way matching | Conferir 3 coisas: pedido + recebimento + nota |
| Tolerância | Quanta diferença você aceita sem se preocupar |
| Lançamento contábil | Débito e crédito no livro da contabilidade |
| Plano de contas referencial | Plano de contas padrão da Receita |
| Mock SEFAZ | Receita falsa para testar sem certificado |
| Dashboard | Painel na tela com tudo resumido |
| PostgreSQL | Banco de dados relacional |
| Redis | Banco de dados rápido para coisas temporárias |
| Docker | Sistema de containers (ambientes isolados) |
| Python | Linguagem de programação |
| FastAPI | Framework web para Python |
| nfelib | Biblioteca que lê XML de notas fiscais |
| erpbrasil.edoc | Biblioteca que fala com a Receita |
| pytest | Ferramenta de testes |
| TDD | Test-Driven Development (teste antes do código) |
| SDD | Spec-Driven Development (spec antes do código) |
| Kanban | Quadro de tarefas em colunas |
| MVP | Minimum Viable Product (versão mínima que funciona) |
