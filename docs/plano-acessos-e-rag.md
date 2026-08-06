# Plano de acessos governamentais, certificados e RAG jurídico-fiscal

## 1. Interpretação

Interpretei “acesso a pai do governo” como acesso às **APIs e Web Services do
governo**. Se a intenção era outra, este plano precisa ser ajustado.

O escopo escolhido é o **fluxo completo**, incluindo consulta, emissão e eventos
NF-e/DF-e, ECD, obrigações acessórias e assistente documental. O certificado
preferencial é **HSM ou certificado em nuvem**, desde que o provedor suporte
mTLS e assinatura exigidos pelos serviços oficiais. A1 em cofre é o plano de
contingência quando o serviço governamental não aceitar HSM.

O objetivo é tornar o sistema capaz de consultar documentos oficiais, preservar
as versões aplicáveis e auxiliar a equipe a verificar se código, testes e regras
contábeis estão coerentes com a legislação vigente.

RAG não será a autoridade que calcula tributos. O motor determinístico, as
fontes oficiais e a validação humana continuam sendo a autoridade. O RAG será
um auxiliar de pesquisa, documentação, comparação e rastreabilidade.

## 2. Acessos e artefatos necessários

### 2.1 Certificado ICP-Brasil da empresa

**Necessário para:** Web Services NF-e/DF-e e operações que exigem identificação
da empresa.

**Acesso a obter:**

- e-CNPJ válido da empresa;
- CNPJ-base compatível com a empresa consultada;
- ambiente de homologação e, depois, produção;
- cadeia de certificados da Autoridade Certificadora;
- autorização do representante legal para uso automatizado.

**Escolha técnica:**

- A1, arquivo armazenado em software, mais simples para serviço automatizado,
  mas exige proteção forte do arquivo e da senha;
- A3, cartão, token ou nuvem, mais adequado quando a política exige hardware ou
  HSM, mas demanda integração PKCS#11, provedor da nuvem ou dispositivo acessível;
- em produção, preferir HSM ou serviço de certificado gerenciado quando a
  política da empresa permitir, para evitar guardar o PFX no container.

O ITI informa que o A1 normalmente tem validade de um ano e o A3 de um a cinco
anos, conforme o certificado. A regra futura da ICP-Brasil também precisa ser
acompanhada, pois há transição de certificados de pessoa jurídica para selo
eletrônico em 2029.

**Nunca colocar no chat, Git, imagem Docker ou `.env` versionado:**

- arquivo `.pfx` ou `.p12`;
- senha do certificado;
- PIN de token;
- chave privada;
- certificados de produção.

**Critérios de aceite:**

- certificado carregado por secret manager ou HSM;
- senha injetada somente em runtime;
- teste de expiração e revogação;
- rotação documentada;
- logs sem serial, senha ou chave privada;
- homologação funcionando antes de produção.

Fonte: <https://www.gov.br/iti/pt-br/acesso-a-informacao/perguntas-frequentes/certificacao-digital>

### 2.2 Procuração ou Autorização de Acesso da Receita

**Necessário para:** contador ou sistema operado por terceiro acessar serviços da
empresa no e-CAC ou Portal de Serviços.

**Acesso a obter:**

- representante legal da empresa;
- pessoa ou escritório contábil outorgado;
- escopos de serviço específicos;
- período de validade;
- autorização para assinatura e transmissão da ECD, quando aplicável;
- confirmação da autorização pelo representante indicado.

Não usar usuário e senha pessoal do responsável como credencial de robô. A
procuração deve limitar os serviços e o prazo.

Fonte: <https://www.gov.br/pt-br/servicos/cadastrar-ou-cancelar-procuracao-para-acesso-ao-e-cac>

### 2.3 Web Services NF-e e NFeDistribuicaoDFe

**Necessário para:** consultar documentos de interesse, baixar XML e processar
eventos.

**Serviços que precisam ser homologados:**

- `NFeDistribuicaoDFe`, por NSU, consulta pontual e chave;
- `NFeConsultaProtocolo`;
- `NFeStatusServico`;
- `NFeRecepcaoEvento`;
- `NFeInutilizacao`;
- `NFeAutorizacao` e retorno, somente se o produto também emitir NF-e;
- serviços de contingência quando aplicáveis.

**Dados de cada UF:**

- UF autorizadora;
- URL de homologação;
- URL de produção;
- modelo 55 ou 65;
- cadeia e certificado aceitos;
- regras de timeout, rate limit e indisponibilidade;
- data de vigência da URL e da Nota Técnica.

O serviço de distribuição exige certificado digital válido e pode distribuir
DF-e de emitente, destinatário, transportador e terceiro autorizado. A consulta
também tem janela operacional de disponibilidade, portanto o sistema precisa
de sincronização por NSU, retentativa controlada e alerta de lacunas.

Fonte técnica: <https://moc.sped.fazenda.pr.gov.br/NFeDistribuicaoDFe.html>

Portal de disponibilidade e URLs: <https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx>

### 2.4 API Consulta CNPJ do SERPRO

**Necessário somente se:** a empresa quiser validar cadastro, QSA e situação
cadastral por API contratada, em vez de usar dados abertos ou consulta manual.

**Acesso a obter:**

- contrato com SERPRO, se o produto contratado exigir;
- ambiente sandbox;
- `consumer key`;
- `consumer secret`;
- endpoints de homologação e produção;
- política de franquia e custo;
- IPs autorizados, se exigidos pelo produto;
- OAuth2 com token temporário.

Nunca confundir essa API com o Web Service NF-e. São produtos e credenciais
diferentes.

Fonte: <https://apicenter.estaleiro.serpro.gov.br/documentacao/consulta-cnpj/pt/faq/>

Catálogo oficial: <https://www.gov.br/conecta/catalogo/apis/consulta-cnpj/>

### 2.5 Integra Contador

**Necessário somente se:** o sistema também for transmitir ou consultar
obrigações e serviços contábeis diretamente pela plataforma SERPRO.

**Acesso a obter:**

- contrato do produto Integra Contador;
- `consumer key` e `consumer secret`;
- e-CNPJ ICP-Brasil compatível com o contrato;
- escopos de API;
- ambiente de demonstração e produção;
- fluxo OAuth2 e JWT;
- procuração digital RFB com escopos adequados.

Fonte: <https://apicenter.estaleiro.serpro.gov.br/documentacao/api-integra-contador/pt/quick_start/>

### 2.6 SPED ECD e PVA

**Necessário para:** validar e transmitir a escrituração.

**Acesso e artefatos:**

- versão vigente do PVA ECD;
- Manual de Orientação do Leiaute vigente;
- certificado para assinatura ou procuração digital;
- empresa, CNPJ, período e situação especial;
- plano de contas e código referencial;
- recibo de transmissão;
- arquivo original e arquivo assinado para auditoria.

O PVA deve ser uma etapa obrigatória do pipeline de release fiscal. Um arquivo
que apenas passa nos testes locais não deve ser considerado transmitível.

Fonte: <https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd>

Perguntas oficiais sobre assinatura e procuração: <https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/perguntas-frequentes/sped/ecd/ecd>

### 2.7 Fontes públicas de legislação e tabelas

Estas fontes não exigem certificado da empresa, mas devem ser acessadas por
coletor com allowlist, hash e versionamento:

- Portal NF-e e MOC, CONFAZ;
- tabela CFOP do CONFAZ;
- SPED e manuais ECD;
- Receita Federal e orientações da Reforma Tributária;
- Planalto e REFLEGIS;
- LexML, para metadados e pesquisa legislativa;
- Classif, NCM e notas legais;
- TIPI;
- ANPD e legislação LGPD;
- portais das SEFAZ estaduais para regras específicas.

LexML oferece API de pesquisa com padrão SRU: <https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml>

NCM vigente em JSON/XLSX: <https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/classificacao-fiscal-de-mercadorias/download-ncm-nomenclatura-comum-do-mercosul>

### 2.8 Infraestrutura de segredos e auditoria

Antes de usar qualquer certificado ou token, obter:

- secret manager ou HSM;
- chave de criptografia gerenciada;
- cofre separado para homologação e produção;
- controle de acesso por função;
- auditoria de leitura e rotação;
- backup criptografado;
- política de retenção;
- procedimento de revogação emergencial.

O sistema atual possui campos de caminho e senha de certificado na configuração,
mas isso é apenas uma interface de MVP, não uma estratégia de gestão de
segredos. <ref_snippet file="/home/vsf/Projetos/contabilidade/src/config.py" lines="13-24" />

## 3. Comparação das arquiteturas RAG

| Tipo | Ponto forte | Limitação | Uso recomendado |
|---|---|---|---|
| RAG vetorial básico | Busca semântica simples | Perde códigos exatos, artigos, CFOP e números | Protótipo inicial |
| BM25/sparse | Excelente para termos exatos e identificadores | Não entende bem paráfrases | CFOP, NCM, artigo, número de NT |
| Hybrid RAG | Combina sparse e vetorial | Exige fusão e avaliação | Padrão recomendado |
| Parent-child/hierárquico | Recupera trecho pequeno e recompõe a seção | Indexação mais complexa | Leis, manuais e PDFs longos |
| Contextual Retrieval | Adiciona contexto ao chunk antes da busca | Aumenta custo de ingestão | Normas com artigos fragmentados |
| Reranked RAG | Reordena candidatos com modelo mais preciso | Aumenta latência | Consultas fiscais críticas |
| GraphRAG | Usa entidades e relações | Extração de grafo pode errar | Lei, artigo, alteração, CFOP, CST, NCM |
| Temporal RAG | Filtra pela vigência e data do fato | Requer versionamento correto | Legislação e ECD histórica |
| CRAG | Avalia qualidade da recuperação e corrige | Mais chamadas e complexidade | Respostas de baixo score |
| Self-RAG | Decide quando recuperar e critica a resposta | Pode ser instável e caro | Assistente avançado, não primeira versão |
| Agentic RAG | Planeja múltiplas consultas e ferramentas | Maior risco de prompt injection | Pesquisa supervisionada |
| Multimodal/layout RAG | Preserva tabelas, colunas e PDFs escaneados | OCR e infraestrutura mais complexos | Manuais, tabelas TIPI e PDFs oficiais |
| Federated RAG | Consulta vários acervos separados | Permissões e ranking difíceis | Fontes federais, estaduais e internas |

## 4. Arquitetura recomendada

### 4.1 Escolha

Usar uma arquitetura em camadas:

```text
Hybrid RAG
+ BM25 para identificadores
+ embeddings para semântica
+ RRF ou fusão equivalente
+ reranker
+ parent-child por artigo/seção
+ filtro temporal obrigatório
+ grafo jurídico leve
+ verificador de citações
+ aprovação humana para mudança de regra
```

A recomendação é **não começar com um agente autônomo**. O primeiro produto
deve ser um assistente de documentação com ferramentas read-only e respostas
citadas.

A literatura e as implementações consultadas apontam que combinar busca lexical
com vetorial melhora cobertura para termos exatos e paráfrases. Para legislação,
a hierarquia, as referências e a vigência são parte do dado, não apenas texto.

Referências técnicas:

- RAG original, Lewis et al., NeurIPS 2020:
  <https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html>
- Hybrid search e RRF: <https://learn.microsoft.com/en-us/cosmos-db/hybrid-search>
- Contextual Retrieval: <https://www.anthropic.com/engineering/contextual-retrieval>
- GraphRAG local e global: <https://microsoft.github.io/graphrag/query/local_search/>
- CRAG: <https://doi.org/10.48550/arxiv.2401.15884>
- SELF-RAG: <https://openreview.net/forum?id=jbNjgmE0OP>
- RAGCHECKER: <https://proceedings.neurips.cc/paper_files/paper/2024/file/27245589131d17368cccdfa990cbf16e-Paper-Datasets_and_Benchmarks_Track.pdf>
- RAG Security Cheat Sheet, OWASP: <https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html>

### 4.2 Separação dos acervos

Não misturar todas as fontes em um índice sem classificação. Criar coleções:

1. **Normativa oficial**, somente fontes autorizadas.
2. **Técnica fiscal**, MOC, XSD, Notas Técnicas e manuais.
3. **Tabelas**, CFOP, NCM, TIPI, CST, CSOSN e alíquotas.
4. **Legislação histórica**, com vigência e data de revogação.
5. **Documentação interna**, código, decisões e procedimentos.
6. **Evidências da empresa**, XML, pedidos, recibos e aprovações.

A resposta deve informar em qual coleção cada evidência foi encontrada.
Documento interno nunca pode substituir fonte normativa oficial.

### 4.3 Registro temporal e proveniência

Cada documento deve possuir:

```text
source_id
source_url
authority
publication_date
retrieved_at
effective_from
effective_to
status: vigente | revogado | substituído | pendente
document_type
norm_number
norm_year
parent_document_id
sha256
parser_version
review_status
```

Cada trecho deve preservar:

```text
document_id
version_id
article
paragraph
inciso
page
section_path
text_hash
source_url
valid_from
valid_to
```

Uma pergunta com data de emissão deve filtrar primeiro a vigência e só depois
aplicar similaridade semântica. Recuperar a norma mais recente para um fato
histórico é erro grave.

## 5. Pipeline seguro de legislação

### Etapa 1, catálogo de fontes

- allowlist de domínios oficiais;
- URL de entrada nunca definida livremente pelo usuário;
- bloqueio de IP interno, redirecionamento para domínio não permitido e URLs
  com esquemas diferentes de HTTPS;
- cadastro de órgão, tipo de documento e periodicidade esperada.

### Etapa 2, download isolado

Todo PDF, HTML ou planilha deve passar por:

1. download em sandbox;
2. ClamAV;
3. limite de tamanho e tempo;
4. validação de tipo real do arquivo;
5. hash SHA-256;
6. armazenamento imutável do original;
7. registro de URL, horário e resposta HTTP.

Não usar `curl | bash`, não executar arquivos baixados e não colocar o arquivo
diretamente no índice. O pipeline de segurança do ambiente é
`~/.seguranca/scripts/download-safe.sh`.

### Etapa 3, parsing

- PDF textual: extrair preservando página e posição;
- PDF escaneado: OCR isolado e marcação de confiança;
- tabelas: extrair como estrutura, não somente texto corrido;
- HTML: preservar título, seção, artigo e links;
- detectar caracteres invisíveis, texto branco, instruções embutidas e conteúdo
  fora do corpo normativo;
- rejeitar ou enviar para revisão documentos com parsing inconsistente.

### Etapa 4, normalização jurídica

Extrair:

- norma;
- artigo;
- parágrafo;
- inciso;
- item;
- alteração;
- revogação;
- vigência;
- referências cruzadas;
- tabela e linha afetada;
- obrigação criada ou removida.

### Etapa 5, indexação

Para cada trecho, gerar:

- índice BM25;
- embedding semântico;
- índice de identificadores exatos;
- ligação parent-child;
- relações no grafo;
- filtro de autoridade e vigência.

### Etapa 6, consulta

1. Classificar intenção: documentação, regra fiscal, vigência, comparação ou
   impacto no código.
2. Extrair data do fato, UF, regime, modelo de documento e identificadores.
3. Buscar por identificador exato.
4. Executar BM25 e busca vetorial em paralelo.
5. Fazer fusão RRF.
6. Recuperar o contexto pai da seção.
7. Reordenar com reranker.
8. Filtrar fontes revogadas ou incompatíveis com a data.
9. Verificar conflito entre fontes.
10. Gerar resposta com citação por afirmação.
11. Recusar conclusão quando não houver evidência suficiente.

### Etapa 7, verificação

O verificador deve responder:

- A citação realmente sustenta a afirmação?
- A fonte é oficial?
- A norma estava vigente na data?
- Existe norma posterior que alterou o trecho?
- Há conflito entre União, estado e município?
- O trecho é regra normativa ou apenas orientação?
- A mudança exige código, teste, migração ou revisão contábil?

Uma divergência deve gerar tarefa de revisão, nunca alteração automática no
motor fiscal.

## 6. Como o RAG auxiliará o sistema

### Assistente de documentação

Perguntas como:

- “Qual regra do CFOP 1.933 foi usada?”
- “Qual versão do Manual ECD estava vigente na data?”
- “Quais testes cobrem o cancelamento?”
- “Qual fonte sustenta essa alíquota?”

Resposta obrigatória: resumo, fonte, trecho, vigência, confiança e lacunas.

### Auditor de consistência

Comparar:

```text
fonte oficial -> regra normalizada -> código -> teste -> documentação
```

Exemplo:

```text
CFOP 1.933
  -> serviço ISSQN
  -> conta de despesa
  -> NCM 00 no cenário de serviço
  -> teste de compatibilidade
  -> fonte CONFAZ
```

### Monitor de mudanças

Quando uma norma muda:

1. baixar nova versão;
2. calcular hash;
3. comparar com a versão anterior;
4. identificar artigos, tabelas e vigências alterados;
5. localizar regras e testes afetados;
6. abrir tarefa de revisão;
7. exigir aprovação humana;
8. só então alterar o motor determinístico.

### Gerador de documentação

O RAG pode gerar:

- explicações para contadores;
- matriz regra-fonte-teste;
- changelog fiscal;
- checklist de homologação;
- relatório de impacto;
- documentação de CFOP, CST, NCM e ECD.

Não deve gerar sozinho:

- lançamento contábil definitivo;
- alíquota nova em produção;
- transmissão ao governo;
- exclusão de documento;
- alteração de regra sem aprovação.

## 7. Segurança do RAG

Os documentos recuperados são dados não confiáveis. Podem conter prompt
injection, texto invisível ou instruções para chamar ferramentas.

Controles obrigatórios:

- separar instruções do sistema, pergunta do usuário e documento recuperado;
- nenhuma ferramenta de escrita ou transmissão disponível para o RAG de consulta;
- ferramentas com allowlist e parâmetros validados;
- aprovação humana para download fora da allowlist, alteração de regra ou
  transmissão;
- hash e cadeia de custódia dos documentos;
- isolamento por empresa e por usuário;
- filtros de dados pessoais antes do contexto;
- limite de tamanho e número de trechos;
- resposta com citações e recusa quando a evidência for insuficiente;
- testes de poisoning, Unicode invisível, documento revogado e vazamento entre
  empresas.

A OWASP destaca que RAG não elimina risco, apenas desloca a superfície de ataque
para ingestão, embeddings, armazenamento, recuperação, geração e ferramentas.
Fonte: <https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html>

## 8. Avaliação antes de produção

Criar um conjunto dourado com perguntas reais e respostas revisadas por
contador ou advogado tributarista.

Métricas mínimas:

- Recall@5 e Recall@10 do recuperador;
- MRR e nDCG;
- precisão de citação;
- cobertura de evidência por afirmação;
- faithfulness;
- correção temporal;
- taxa de resposta “não há evidência” quando apropriado;
- taxa de recuperação de fonte revogada;
- vazamento entre empresas;
- resistência a documentos envenenados;
- latência e custo por consulta.

Separar avaliação em:

1. recuperação;
2. reranking;
3. geração;
4. verificação;
5. segurança;
6. atualização temporal.

## 9. Plano de implementação

### Fase 0, acessos e governança

- confirmar se o alvo é apenas consulta ou também transmissão;
- designar representante legal e responsável técnico;
- obter certificado de homologação;
- cadastrar procuração e escopos;
- decidir A1, A3, nuvem ou HSM;
- contratar SERPRO apenas se Consulta CNPJ ou Integra Contador forem realmente
  necessárias;
- criar cofre de segredos;
- definir fontes oficiais e política de atualização;
- nunca solicitar ou armazenar os segredos no repositório.

### Fase 1, observação sem escrita

- coletor read-only de fontes allowlisted;
- download seguro;
- hash e metadados;
- armazenamento de versões;
- diff de documentos;
- catálogo pesquisável;
- sem chamada de transmissão ao governo.

### Fase 2, busca híbrida documental

- busca exata por número, artigo, CFOP, NCM e NT;
- BM25;
- embeddings;
- fusão RRF;
- parent-child;
- filtros de órgão, UF, data e vigência;
- resposta com citação.

### Fase 3, grafo jurídico-fiscal

Entidades:

```text
Norma -> artigo -> obrigação
Norma -> altera -> norma anterior
CFOP -> representa -> operação
NCM -> classifica -> mercadoria
CST -> aplica-se-a -> regime
Regra -> implementada-por -> função
Regra -> coberta-por -> teste
Documento -> substitui -> versão anterior
```

Começar com um grafo pequeno e determinístico. Não gerar grafo completo sem
revisão dos vínculos extraídos.

### Fase 4, auditor de consistência

- comparar fonte e código;
- comparar fonte e testes;
- detectar regra sem teste;
- detectar teste sem fonte;
- detectar código com alíquota fora da vigência;
- gerar relatório de divergências;
- exigir aprovação antes de alterar regras.

### Fase 5, integração controlada com governo

- apenas homologação;
- certificado segregado de produção;
- chamadas read-only primeiro;
- transmissão atrás de feature flag;
- confirmação humana para eventos e ECD;
- logs de auditoria sem dados sensíveis;
- testes de indisponibilidade e duplicidade.

### Fase 6, produção

Só liberar depois de:

- homologação por UF;
- PVA validando ECD;
- assinatura verificada;
- backup restaurado em teste;
- RBAC ativo;
- monitoramento ativo;
- fontes e versões auditáveis;
- revisão contábil e jurídica;
- plano de revogação do certificado;
- runbook de incidente.

## 10. Decisões recomendadas

1. Começar com **Hybrid RAG temporal e citável**, não com agente autônomo.
2. Usar busca exata para códigos e artigos, BM25 para texto legal e embeddings
   para perguntas conceituais.
3. Adicionar grafo jurídico leve depois que o catálogo temporal estiver correto.
4. Usar CRAG ou verificador separado para consultas de baixa confiança.
5. Manter regras fiscais em código determinístico, com o RAG apenas como
   auxiliar de descoberta e auditoria.
6. Manter o coletor e o índice normativo separados dos documentos internos da
   empresa.
