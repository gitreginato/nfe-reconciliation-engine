-- Schema do banco de dados: Sistema de Contabilidade com NF-e
-- PostgreSQL 16
-- Data: 05/08/2026

-- ============================================================================
-- TABELAS DE DOMINIO (4)
-- ============================================================================

-- Plano de contas referencial (Receita Federal, Registro I051 da ECD)
CREATE TABLE IF NOT EXISTS plano_contas (
    id SERIAL PRIMARY KEY,
    codigo_referencial VARCHAR(20) UNIQUE NOT NULL,
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    conta_pai VARCHAR(20),
    natureza VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pedido de compra (origem do three-way matching)
CREATE TABLE IF NOT EXISTS pedido_compra (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(30) UNIQUE NOT NULL,
    fornecedor_cnpj VARCHAR(14) NOT NULL,
    fornecedor_nome VARCHAR(255),
    data_pedido DATE NOT NULL,
    valor_total DECIMAL(14,2) NOT NULL,
    condicao_pagamento VARCHAR(100),
    status VARCHAR(20) DEFAULT 'aberto',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Itens do pedido de compra
CREATE TABLE IF NOT EXISTS pedido_compra_item (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER REFERENCES pedido_compra(id) ON DELETE CASCADE,
    numero_item INTEGER NOT NULL,
    codigo_produto VARCHAR(60),
    descricao TEXT NOT NULL,
    ncm VARCHAR(8),
    cfop VARCHAR(4),
    unidade VARCHAR(10),
    quantidade DECIMAL(14,4) NOT NULL,
    valor_unitario DECIMAL(14,4) NOT NULL,
    valor_total DECIMAL(14,2) NOT NULL,
    UNIQUE(pedido_id, numero_item)
);

-- Recebimento de mercadoria (terceira perna do three-way matching)
CREATE TABLE IF NOT EXISTS recebimento (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER REFERENCES pedido_compra(id),
    data_recebimento DATE NOT NULL,
    responsavel VARCHAR(255),
    observacao TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Itens recebidos
CREATE TABLE IF NOT EXISTS recebimento_item (
    id SERIAL PRIMARY KEY,
    recebimento_id INTEGER REFERENCES recebimento(id) ON DELETE CASCADE,
    pedido_item_id INTEGER REFERENCES pedido_compra_item(id),
    quantidade_recebida DECIMAL(14,4) NOT NULL,
    conferido BOOLEAN DEFAULT FALSE,
    divergencia TEXT
);

-- ============================================================================
-- TABELAS PRINCIPAIS (8)
-- ============================================================================

-- Participantes (emitente, destinatario, transportador) - deve vir antes de nfe
CREATE TABLE IF NOT EXISTS participante (
    id SERIAL PRIMARY KEY,
    cnpj_cpf VARCHAR(14) UNIQUE NOT NULL,
    nome VARCHAR(255) NOT NULL,
    nome_fantasia VARCHAR(255),
    endereco TEXT,
    municipio VARCHAR(60),
    uf CHAR(2),
    cep VARCHAR(8),
    ie VARCHAR(20),
    im VARCHAR(20),
    telefone VARCHAR(20),
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela principal: NF-e
CREATE TABLE IF NOT EXISTS nfe (
    id SERIAL PRIMARY KEY,
    chave_acesso VARCHAR(44) UNIQUE NOT NULL,
    numero_nota INTEGER NOT NULL,
    serie INTEGER NOT NULL,
    modelo VARCHAR(2) NOT NULL DEFAULT '55',
    data_emissao TIMESTAMP NOT NULL,
    natureza_operacao VARCHAR(255),
    tipo_operacao CHAR(1) NOT NULL,
    valor_total DECIMAL(14,2) NOT NULL,
    valor_produtos DECIMAL(14,2),
    valor_desconto DECIMAL(14,2),
    valor_frete DECIMAL(14,2),
    valor_seguro DECIMAL(14,2),
    valor_outros DECIMAL(14,2),
    status_autorizacao VARCHAR(20) DEFAULT 'autorizada',
    origem VARCHAR(20) DEFAULT 'sefaz',
    xml_original TEXT,
    protocolo VARCHAR(20),
    data_autorizacao TIMESTAMP,
    manifestacao_destinatario VARCHAR(20),
    nsu BIGINT,
    emitente_id INTEGER REFERENCES participante(id),
    destinatario_id INTEGER REFERENCES participante(id),
    transportador_id INTEGER REFERENCES participante(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Itens da NF-e
CREATE TABLE IF NOT EXISTS nfe_item (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id) ON DELETE CASCADE,
    numero_item INTEGER NOT NULL,
    codigo_produto VARCHAR(60),
    codigo_ean VARCHAR(14),
    descricao TEXT NOT NULL,
    ncm VARCHAR(8),
    cfop VARCHAR(4),
    unidade VARCHAR(10),
    quantidade DECIMAL(14,4),
    valor_unitario DECIMAL(14,4),
    valor_total DECIMAL(14,2),
    valor_desconto DECIMAL(14,2),
    valor_frete DECIMAL(14,2),
    valor_seguro DECIMAL(14,2),
    valor_outros DECIMAL(14,2),
    -- Tributos
    vbc_icms DECIMAL(14,2),
    vbc_icms_st DECIMAL(14,2),
    vicms DECIMAL(14,2),
    vicms_st DECIMAL(14,2),
    vipi DECIMAL(14,2),
    vpis DECIMAL(14,2),
    vcofins DECIMAL(14,2),
    -- Reforma Tributaria (NT 2025.002)
    vbc_ibscbs DECIMAL(14,2),
    vibscbs DECIMAL(14,2),
    aliquota_ibscbs DECIMAL(5,2),
    UNIQUE(nfe_id, numero_item)
);

-- Tributos detalhados por item
CREATE TABLE IF NOT EXISTS nfe_tributo (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES nfe_item(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL,
    base_calculo DECIMAL(14,2),
    aliquota DECIMAL(5,2),
    valor DECIMAL(14,2),
    cst VARCHAR(3),
    csosn VARCHAR(4)
);

-- Pagamentos
CREATE TABLE IF NOT EXISTS nfe_pagamento (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id) ON DELETE CASCADE,
    forma_pagamento VARCHAR(50),
    valor_pago DECIMAL(14,2),
    bandeira VARCHAR(30),
    cnpj_credenciadora VARCHAR(14)
);

-- Eventos (cancelamento, carta de correcao, manifestacao)
CREATE TABLE IF NOT EXISTS nfe_evento (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id) ON DELETE CASCADE,
    tipo_evento VARCHAR(30),
    data_evento TIMESTAMP,
    sequencia INTEGER,
    xml_evento TEXT,
    protocolo VARCHAR(20),
    status VARCHAR(20)
);

-- Reconciliacao (matching)
CREATE TABLE IF NOT EXISTS reconciliacao (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id) UNIQUE,
    pedido_compra_id INTEGER REFERENCES pedido_compra(id),
    recebimento_id INTEGER REFERENCES recebimento(id),
    status VARCHAR(20) DEFAULT 'pending',
    tipo_match VARCHAR(20),
    divergencias JSONB,
    tolerancia_percentual DECIMAL(5,2) DEFAULT 2.00,
    data_match TIMESTAMP,
    matched_by VARCHAR(50) DEFAULT 'automatico',
    resolvido_por VARCHAR(255),
    data_resolucao TIMESTAMP,
    justificativa_resolucao TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Lancamento contabil
CREATE TABLE IF NOT EXISTS lancamento_contabil (
    id SERIAL PRIMARY KEY,
    nfe_id INTEGER REFERENCES nfe(id),
    data_lancamento DATE NOT NULL,
    numero_documento VARCHAR(30),
    historico TEXT,
    conta_debito_codigo VARCHAR(20) REFERENCES plano_contas(codigo_referencial),
    conta_credito_codigo VARCHAR(20) REFERENCES plano_contas(codigo_referencial),
    valor DECIMAL(14,2) NOT NULL,
    estornado BOOLEAN DEFAULT FALSE,
    lancamento_estorno_id INTEGER REFERENCES lancamento_contabil(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Controle de importacao DF-e
CREATE TABLE IF NOT EXISTS dfe_importacao (
    id SERIAL PRIMARY KEY,
    cnpj_consultado VARCHAR(14),
    ultimo_nsu BIGINT,
    total_documentos INTEGER,
    data_ultima_consulta TIMESTAMP,
    status VARCHAR(20),
    erro_mensagem TEXT
);

-- ============================================================================
-- INDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_nfe_chave ON nfe(chave_acesso);
CREATE INDEX IF NOT EXISTS idx_nfe_data ON nfe(data_emissao);
CREATE INDEX IF NOT EXISTS idx_nfe_status ON nfe(status_autorizacao);
CREATE INDEX IF NOT EXISTS idx_nfe_nsu ON nfe(nsu);
CREATE INDEX IF NOT EXISTS idx_nfe_emitente ON nfe(emitente_id);
CREATE INDEX IF NOT EXISTS idx_nfe_destinatario ON nfe(destinatario_id);
CREATE INDEX IF NOT EXISTS idx_participante_cnpj ON participante(cnpj_cpf);
CREATE INDEX IF NOT EXISTS idx_nfe_item_nfe ON nfe_item(nfe_id);
CREATE INDEX IF NOT EXISTS idx_nfe_item_ncm ON nfe_item(ncm);
CREATE INDEX IF NOT EXISTS idx_nfe_item_cfop ON nfe_item(cfop);
CREATE INDEX IF NOT EXISTS idx_nfe_tributo_nfe ON nfe_tributo(nfe_id);
CREATE INDEX IF NOT EXISTS idx_nfe_tributo_item ON nfe_tributo(item_id);
CREATE INDEX IF NOT EXISTS idx_nfe_evento_nfe ON nfe_evento(nfe_id);
CREATE INDEX IF NOT EXISTS idx_reconciliacao_nfe ON reconciliacao(nfe_id);
CREATE INDEX IF NOT EXISTS idx_reconciliacao_status ON reconciliacao(status);
CREATE INDEX IF NOT EXISTS idx_reconciliacao_pedido ON reconciliacao(pedido_compra_id);
CREATE INDEX IF NOT EXISTS idx_lancamento_nfe ON lancamento_contabil(nfe_id);
CREATE INDEX IF NOT EXISTS idx_lancamento_data ON lancamento_contabil(data_lancamento);
CREATE INDEX IF NOT EXISTS idx_pedido_fornecedor ON pedido_compra(fornecedor_cnpj);
CREATE INDEX IF NOT EXISTS idx_pedido_data ON pedido_compra(data_pedido);

-- ============================================================================
-- DADOS INICIAIS: Plano de contas referencial (subset)
-- ============================================================================

INSERT INTO plano_contas (codigo_referencial, nome, tipo, conta_pai, natureza) VALUES
('1', 'ATIVO', 'classe', NULL, 'D'),
('1.1', 'ATIVO CIRCULANTE', 'grupo', '1', 'D'),
('1.1.3', 'ESTOQUES', 'grupo', '1.1', 'D'),
('1.1.3.01', 'MERCADORIAS PARA REVENDA', 'conta', '1.1.3', 'D'),
('1.1.3.01.01', 'Estoque de Mercadorias para Revenda', 'subconta', '1.1.3.01', 'D'),
('1.1.5', 'TRIBUTOS A RECUPERAR', 'grupo', '1.1', 'D'),
('1.1.5.01', 'ICMS A RECUPERAR', 'conta', '1.1.5', 'D'),
('1.1.5.01.01', 'ICMS a Recuperar', 'subconta', '1.1.5.01', 'D'),
('1.1.5.02', 'IPI A RECUPERAR', 'conta', '1.1.5', 'D'),
('1.1.5.02.01', 'IPI a Recuperar', 'subconta', '1.1.5.02', 'D'),
('1.1.5.03', 'PIS A RECUPERAR', 'conta', '1.1.5', 'D'),
('1.1.5.03.01', 'PIS a Recuperar', 'subconta', '1.1.5.03', 'D'),
('1.1.5.04', 'COFINS A RECUPERAR', 'conta', '1.1.5', 'D'),
('1.1.5.04.01', 'COFINS a Recuperar', 'subconta', '1.1.5.04', 'D'),
('1.2', 'ATIVO NAO CIRCULANTE', 'grupo', '1', 'D'),
('1.2.1', 'IMOBILIZADO', 'grupo', '1.2', 'D'),
('1.2.1.01', 'MOVEIS E UTENSILOS', 'conta', '1.2.1', 'D'),
('1.2.1.01.01', 'Moveis e Utensilios', 'subconta', '1.2.1.01', 'D'),
('2', 'PASSIVO', 'classe', NULL, 'C'),
('2.1', 'PASSIVO CIRCULANTE', 'grupo', '2', 'C'),
('2.1.01', 'FORNECEDORES', 'conta', '2.1', 'C'),
('2.1.01.01', 'Fornecedores Nacionais', 'subconta', '2.1.01', 'C'),
('3', 'RECEITAS', 'classe', NULL, 'C'),
('3.1', 'RECEITAS OPERACIONAIS', 'grupo', '3', 'C'),
('3.1.01', 'RECEITA DE VENDA DE MERCADORIAS', 'conta', '3.1', 'C'),
('3.1.01.01', 'Receita de Venda de Mercadorias', 'subconta', '3.1.01', 'C'),
('4', 'CUSTOS E DESPESAS', 'classe', NULL, 'D'),
('4.1', 'CUSTOS DAS MERCADORIAS VENDIDAS', 'grupo', '4', 'D'),
('4.1.01', 'Custo de Mercadorias Vendidas', 'conta', '4.1', 'D')
ON CONFLICT (codigo_referencial) DO NOTHING;
