"""Pool de NF-e de exemplo para o mock SEFAZ.

10 notas fiscais sinteticas cobrindo cenarios variados:
- Entrada e saida
- Com e sem IBS/CBS
- Com e sem divergencia de preco
- Cancelada
- Sem pedido de compra vinculado
- Diferentes fornecedores e CFOPs
"""
from datetime import datetime, date

# CNPJ do destinatário (a "nossa" empresa)
CNPJ_DESTINATARIO = "12345678000190"

# Pool de 10 notas: cada uma tem NSU, chave, resumo e XML completo
POOL_NFE = [
    {
        "nsu": 1,
        "chave": "35200812345678000190550010000000011000000000",
        "numero": 1,
        "serie": 1,
        "data_emissao": "2026-07-15T10:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 1500.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias para revenda",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_normal",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
            {"codigo": "002", "descricao": "Açúcar cristal 1kg", "ncm": "17019900",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 4.00, "valor_total": 400.00},
            {"codigo": "003", "descricao": "Óleo de soja 1L", "ncm": "15121911",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 6.00, "valor_total": 600.00},
        ],
    },
    {
        "nsu": 2,
        "chave": "35200811222333000144550010000000021000000008",
        "numero": 2,
        "serie": 1,
        "data_emissao": "2026-07-16T09:30:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 800.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias para revenda",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_normal_segunda_nota",
        "itens": [
            {"codigo": "004", "descricao": "Cafe torrado 500g", "ncm": "09012100",
             "cfop": "1102", "quantidade": 80, "valor_unitario": 10.00, "valor_total": 800.00},
        ],
    },
    {
        "nsu": 3,
        "chave": "35200844555666000177550010000000031000000005",
        "numero": 3,
        "serie": 1,
        "data_emissao": "2026-07-17T14:00:00",
        "emitente_cnpj": "44555666000177",
        "emitente_nome": "Móveis Industrializados do Brasil SA",
        "valor_total": 3500.00,
        "tipo": "entrada",
        "natureza": "Compra de bem para ativo imobilizado",
        "cfop": "1551",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_ativo_imobilizado",
        "itens": [
            {"codigo": "MESA01", "descricao": "Mesa de escritório 1.20m", "ncm": "94033000",
             "cfop": "1551", "quantidade": 5, "valor_unitario": 350.00, "valor_total": 1750.00},
            {"codigo": "CAD01", "descricao": "Cadeira giratória executiva", "ncm": "94013090",
             "cfop": "1551", "quantidade": 10, "valor_unitario": 175.00, "valor_total": 1750.00},
        ],
    },
    {
        "nsu": 4,
        "chave": "35200877888999000110550010000000041000000000",
        "numero": 4,
        "serie": 1,
        "data_emissao": "2026-07-18T11:00:00",
        "emitente_cnpj": "77888999000110",
        "emitente_nome": "Papelaria Central Ltda ME",
        "valor_total": 250.00,
        "tipo": "entrada",
        "natureza": "Compra de material de consumo",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": False,
        "cenario": "sem_pedido_vinculado",
        "itens": [
            {"codigo": "PAPEL-A4", "descricao": "Papel A4 branco 75g 500fls", "ncm": "48025600",
             "cfop": "1102", "quantidade": 10, "valor_unitario": 25.00, "valor_total": 250.00},
        ],
    },
    {
        "nsu": 5,
        "chave": "35200811222333000144550010000000051000000000",
        "numero": 5,
        "serie": 1,
        "data_emissao": "2026-07-19T08:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 1250.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias para revenda",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "divergencia_preco",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 6.25, "valor_total": 625.00},
            {"codigo": "002", "descricao": "Açúcar cristal 1kg", "ncm": "17019900",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
            {"codigo": "003", "descricao": "Óleo de soja 1L", "ncm": "15121911",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 1.25, "valor_total": 125.00},
        ],
    },
    {
        "nsu": 6,
        "chave": "35200811222333000144550010000000061000000007",
        "numero": 6,
        "serie": 1,
        "data_emissao": "2026-07-20T16:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 1000.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias para revenda",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "divergencia_quantidade",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 150, "valor_unitario": 5.00, "valor_total": 750.00},
            {"codigo": "002", "descricao": "Açúcar cristal 1kg", "ncm": "17019900",
             "cfop": "1102", "quantidade": 50, "valor_unitario": 4.00, "valor_total": 200.00},
            {"codigo": "003", "descricao": "Óleo de soja 1L", "ncm": "15121911",
             "cfop": "1102", "quantidade": 10, "valor_unitario": 5.00, "valor_total": 50.00},
        ],
    },
    {
        "nsu": 7,
        "chave": "35200899000110000100550010000000071000000000",
        "numero": 7,
        "serie": 1,
        "data_emissao": "2026-07-21T13:00:00",
        "emitente_cnpj": "99000110000100",
        "emitente_nome": "Consultoria Tributaria ABC Ltda",
        "valor_total": 3000.00,
        "tipo": "entrada",
        "natureza": "Prestacao de serviços de consultoria",
        "cfop": "1933",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "servico_two_way_match",
        "itens": [
            {"codigo": "SERV-CONS", "descricao": "Consultoria tributaria mensal", "ncm": "00",
             "cfop": "1933", "quantidade": 1, "valor_unitario": 3000.00, "valor_total": 3000.00},
        ],
    },
    {
        "nsu": 8,
        "chave": "35200811222333000144550010000000081000000001",
        "numero": 8,
        "serie": 1,
        "data_emissao": "2026-07-22T10:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 500.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias para revenda",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": True,
        "tem_ibscbs": True,
        "cenario": "nota_cancelada",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
        ],
    },
    {
        "nsu": 9,
        "chave": "35200822333444000155550010000000091000000009",
        "numero": 9,
        "serie": 1,
        "data_emissao": "2026-07-23T09:00:00",
        "emitente_cnpj": "22333444000155",
        "emitente_nome": "Limpeza Total Produtos de Higiene Ltda",
        "valor_total": 450.00,
        "tipo": "entrada",
        "natureza": "Compra de material de limpeza",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_normal_baixo_valor",
        "itens": [
            {"codigo": "SABAO", "descricao": "Sabão em pó 1kg", "ncm": "34022020",
             "cfop": "1102", "quantidade": 30, "valor_unitario": 15.00, "valor_total": 450.00},
        ],
    },
    {
        "nsu": 10,
        "chave": "35200855666777000188550010000000101000000018",
        "numero": 10,
        "serie": 1,
        "data_emissao": "2026-07-24T15:00:00",
        "emitente_cnpj": "55666777000188",
        "emitente_nome": "TechInfo Equipamentos Eletrônicos Ltda",
        "valor_total": 4200.00,
        "tipo": "entrada",
        "natureza": "Compra de equipamento eletrônico",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "divergencia_preco_alta",
        "itens": [
            {"codigo": "NOTE-DELL", "descricao": "Notebook Dell Inspiron 15", "ncm": "84713012",
             "cfop": "1102", "quantidade": 3, "valor_unitario": 1400.00, "valor_total": 4200.00},
        ],
    },
    # --- Cenários adicionais (cotidiano contábil) ---
    {
        "nsu": 11,
        "chave": "35200811222333000144550010000000111000000015",
        "numero": 11,
        "serie": 1,
        "data_emissao": "2026-07-25T09:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 500.00,
        "tipo": "entrada",
        "natureza": "Devolução de compra (mercadoria devolvida ao fornecedor)",
        "cfop": "1202",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "devolucao_compra",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1202", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
        ],
    },
    {
        "nsu": 12,
        "chave": "35200811222333000144550010000000121000000012",
        "numero": 12,
        "serie": 1,
        "data_emissao": "2026-07-26T10:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 1150.00,
        "valor_frete": 150.00,
        "valor_produtos": 1000.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias com frete por conta do destinatário",
        "cfop": "1102",
        "modalidade_frete": 1,
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_com_frete",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
            {"codigo": "002", "descricao": "Açúcar cristal 1kg", "ncm": "17019900",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00},
        ],
    },
    {
        "nsu": 13,
        "chave": "35200811222333000144550010000000131000000010",
        "numero": 13,
        "serie": 1,
        "data_emissao": "2026-07-27T11:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 900.00,
        "valor_desconto": 100.00,
        "valor_produtos": 1000.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias com desconto incondicionado",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_com_desconto",
        "itens": [
            {"codigo": "001", "descricao": "Farinha de trigo 1kg", "ncm": "11010010",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00,
             "valor_desconto": 50.00},
            {"codigo": "002", "descricao": "Açúcar cristal 1kg", "ncm": "17019900",
             "cfop": "1102", "quantidade": 100, "valor_unitario": 5.00, "valor_total": 500.00,
             "valor_desconto": 50.00},
        ],
    },
    {
        "nsu": 14,
        "chave": "35200811222333000144550010000000141000000017",
        "numero": 14,
        "serie": 1,
        "data_emissao": "2026-07-28T08:00:00",
        "emitente_cnpj": "11222333000144",
        "emitente_nome": "Distribuidora Alimentos SP Ltda",
        "valor_total": 1000.00,
        "tipo": "entrada",
        "natureza": "Compra de mercadorias com ICMS substituição tributária",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": True,
        "cenario": "compra_com_icms_st",
        "itens": [
            {"codigo": "CIGARRO", "descricao": "Cigarros pacote", "ncm": "24022020",
             "cfop": "1102", "quantidade": 50, "valor_unitario": 20.00, "valor_total": 1000.00,
             "vicms": 120.00, "vicms_st": 180.00, "vbc_icms_st": 1500.00},
        ],
    },
    {
        "nsu": 15,
        "chave": "35200855666777000188550010000000151000000014",
        "numero": 15,
        "serie": 1,
        "data_emissao": "2026-07-29T14:00:00",
        "emitente_cnpj": "55666777000188",
        "emitente_nome": "TechInfo Equipamentos Eletrônicos Ltda",
        "valor_total": 1000.00,
        "tipo": "entrada",
        "natureza": "Compra de equipamento eletrônico com IPI, PIS e COFINS",
        "cfop": "1102",
        "manifestada": False,
        "cancelada": False,
        "tem_ibscbs": False,
        "cenario": "compra_com_impostos_recuperaveis",
        "itens": [
            {"codigo": "MONITOR", "descricao": "Monitor LED 24 polegadas", "ncm": "85285200",
             "cfop": "1102", "quantidade": 2, "valor_unitario": 500.00, "valor_total": 1000.00,
             "vicms": 120.00, "vipi": 100.00, "vpis": 6.50, "vcofins": 30.00},
        ],
    },
]


def get_nfe_by_nsu(nsu: int) -> dict | None:
    for nfe in POOL_NFE:
        if nfe["nsu"] == nsu:
            return nfe
    return None


def get_nfe_by_chave(chave: str) -> dict | None:
    for nfe in POOL_NFE:
        if nfe["chave"] == chave:
            return nfe
    return None


def get_notas_apartir_nsu(ultimo_nsu: int, limite: int = 50) -> list[dict]:
    """Retorna notas com NSU > ultimo_nsu, ate o limite."""
    return [n for n in POOL_NFE if n["nsu"] > ultimo_nsu][:limite]


def manifestar_nfe(chave: str) -> bool:
    """Marca a nota como manifestada (ciência da emissão)."""
    nfe = get_nfe_by_chave(chave)
    if nfe:
        nfe["manifestada"] = True
        return True
    return False


def reset_pool():
    """Reseta todas as notas para o estado inicial (não manifestadas)."""
    for n in POOL_NFE:
        n["manifestada"] = False
