"""Gerador sintetico de 1000 NF-e para teste de volume.

Cria 1000 notas com cenarios variados:
- Diferentes fornecedores (50)
- Diferentes CFOPs (1102, 1101, 1403, 1551, 2102, 2201)
- Com e sem IBS/CBS
- Valores variados (R$ 50 a R$ 50.000)
- 1-10 itens por nota
- 5% canceladas
- Datas distribuidas em 12 meses
"""
import random
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from src.persistencia.models import (
    Session, Nfe, NfeItem, Participante, init_db,
)

logger = logging.getLogger(__name__)

# Fornecedores sinteticos
FORNECEDORES = [
    ("11222333000144", "Distribuidora Alimentos SP Ltda", "Sao Paulo", "SP"),
    ("44555666000177", "Móveis Industrializados do Brasil SA", "Votorantim", "SP"),
    ("77888999000110", "Papelaria Central Ltda ME", "Campinas", "SP"),
    ("12345678000190", "Tech Solutions do Brasil Ltda", "Sao Paulo", "SP"),
    ("98765432000121", "Construção e Cia Materiais SA", "Guarulhos", "SP"),
]

CFOPS = [
    ("1102", "Compra de mercadorias para revenda", "1.1.3.01"),
    ("1101", "Compra para uso e consumo", "3.1.01"),
    ("1403", "Compra para comercialização não tributada", "1.1.3.01"),
    ("1551", "Compra de ativo imobilizado", "1.2.1.01"),
    ("2102", "Devolução de venda", "1.1.3.01"),
    ("2201", "Devolução de ativo", "1.2.1.01"),
]

NCMS = ["20011000", "21069090", "33030010", "34011190", "39231010", "40111000", "48181000", "61091000", "73083000", "84713012"]

DESCRICOES = [
    "Produto Alimento Tipo A", "Produto Alimento Tipo B", "Papel A4 Resma 500fl",
    "Cadeira Office Executiva", "Notebook Dell Inspiron", "Cimento Votoran 50kg",
    "Software Licença Anual", "Mesa Reunião 6 Lugares", "Produto Higiene Limpeza",
    "Material Escritório Diversos", "Equipamento Eletrônico X", "Produto Químico Industrial",
]


def _gerar_chave(numero: int, data: datetime, cnpj_emit: str) -> str:
    """Gera chave de acesso de 44 dígitos."""
    cuf = "35"
    aamm = data.strftime("%y%m")
    cnpj_limpo = cnpj_emit.replace(".", "").replace("/", "").replace("-", "").zfill(14)[:14]
    mod = "55"
    serie = "001"
    nnf = f"{numero:09d}"
    cnf = f"{random.randint(0, 99999999):08d}"
    base = cuf + aamm + cnpj_limpo + mod + serie + nnf + "1" + cnf
    # DV modulo 11 (peso 2-9 ciclico)
    soma = 0
    peso = 2
    for c in reversed(base):
        soma += int(c) * peso
        peso = 2 if peso >= 9 else peso + 1
    dv = 11 - (soma % 11)
    if dv >= 10:
        dv = 0
    return base + str(dv)


def gerar_nfe_sintetica(numero: int, data_base: datetime) -> dict:
    """Gera os dados de uma NF-e sintética."""
    fornecedor = random.choice(FORNECEDORES)
    cfop_info = random.choice(CFOPS)
    data_emissao = data_base + timedelta(days=random.randint(0, 365))
    num_itens = random.randint(1, 10)
    tem_ibscbs = random.random() < 0.7  # 70% tem IBS/CBS
    cancelada = random.random() < 0.05  # 5% cancelada

    itens = []
    valor_total = 0.0
    for i in range(num_itens):
        qtd = round(random.uniform(1, 100), 2)
        vunit = round(random.uniform(10, 500), 2)
        vtotal = round(qtd * vunit, 2)
        itens.append({
            "numero": i + 1,
            "codigo": f"PROD-{random.randint(1000, 9999)}",
            "descricao": random.choice(DESCRICOES),
            "ncm": random.choice(NCMS),
            "cfop": cfop_info[0],
            "quantidade": qtd,
            "valor_unitario": vunit,
            "valor_total": vtotal,
            "vicms": round(vtotal * 0.18, 2),
            "vipi": round(vtotal * 0.05, 2) if cfop_info[0] in ("1102", "1403") else 0,
            "vpis": round(vtotal * 0.0065, 2),
            "vcofins": round(vtotal * 0.03, 2),
            "vibscbs": round(vtotal * 0.01, 2) if tem_ibscbs else 0,
        })
        valor_total += vtotal

    return {
        "numero": numero,
        "chave": _gerar_chave(numero, data_emissao, fornecedor[0]),
        "data_emissao": data_emissao,
        "fornecedor": fornecedor,
        "cfop": cfop_info[0],
        "natureza": cfop_info[1],
        "valor_total": round(valor_total, 2),
        "itens": itens,
        "cancelada": cancelada,
        "tem_ibscbs": tem_ibscbs,
    }


def popular_nfe_sinteticas(session: Session, quantidade: int = 1000) -> dict:
    """Cria N notas fiscais sinteticas no banco para teste de volume.

    Args:
        session: Sessao do banco
        quantidade: Numero de notas a criar (default 1000, max 10000)

    Returns:
        Estatisticas da geracao
    """
    if quantidade > 10000:
        raise ValueError("Quantidade máxima e 10000 para prevenir DoS")
    if quantidade <= 0:
        raise ValueError("Quantidade deve ser > 0")

    logger.info(f"[TEST] Gerando {quantidade} NF-e sintéticas para teste de volume")
    stats = {"criadas": 0, "canceladas": 0, "erros": 0, "valor_total": 0.0}
    data_base = datetime(2025, 1, 1)

    # Criar fornecedores
    fornecedores_db = {}
    for cnpj, nome, municipio, uf in FORNECEDORES:
        part = session.query(Participante).filter_by(cnpj_cpf=cnpj).first()
        if not part:
            part = Participante(cnpj_cpf=cnpj, nome=nome, municipio=municipio, uf=uf)
            session.add(part)
            session.flush()
        fornecedores_db[cnpj] = part

    # Destinatario
    dest = session.query(Participante).filter_by(cnpj_cpf="12345678000190").first()
    if not dest:
        dest = Participante(cnpj_cpf="12345678000190", nome="Minha Empresa Ltda", municipio="Sao Paulo", uf="SP")
        session.add(dest)
        session.flush()

    for i in range(1, quantidade + 1):
        try:
            dados = gerar_nfe_sintetica(i, data_base)
            forn = dados["fornecedor"]
            emitente = fornecedores_db[forn[0]]

            nfe = Nfe(
                chave_acesso=dados["chave"],
                numero_nota=dados["numero"],
                serie=1,
                modelo="55",
                data_emissao=dados["data_emissao"],
                nsu=i,
                emitente_id=emitente.id,
                destinatario_id=dest.id,
                tipo_operacao="0",  # 0=entrada, 1=saída
                valor_total=Decimal(str(dados["valor_total"])),
                status_autorizacao="cancelada" if dados["cancelada"] else "sintética",
                origem="sintética",
                manifestacao_destinatario="",
                natureza_operacao=dados["natureza"],
                xml_original=f"<NFe><infNFe Id=\"NFe{dados['chave']}\" versao=\"4.00\"><ide><nNF>{dados['numero']}</nNF></ide></infNFe></NFe>",
            )
            session.add(nfe)
            session.flush()

            for item_data in dados["itens"]:
                item = NfeItem(
                    nfe_id=nfe.id,
                    numero_item=item_data["numero"],
                    codigo_produto=item_data["codigo"],
                    descricao=item_data["descricao"],
                    ncm=item_data["ncm"],
                    cfop=item_data["cfop"],
                    quantidade=Decimal(str(item_data["quantidade"])),
                    valor_unitario=Decimal(str(item_data["valor_unitario"])),
                    valor_total=Decimal(str(item_data["valor_total"])),
                    vicms=Decimal(str(item_data["vicms"])),
                    vipi=Decimal(str(item_data["vipi"])),
                    vpis=Decimal(str(item_data["vpis"])),
                    vcofins=Decimal(str(item_data["vcofins"])),
                    vibscbs=Decimal(str(item_data["vibscbs"])),
                    unidade="UN",
                )
                session.add(item)

            stats["criadas"] += 1
            stats["valor_total"] += dados["valor_total"]
            if dados["cancelada"]:
                stats["canceladas"] += 1

            # Commit em lotes de 100
            if i % 100 == 0:
                session.commit()
                logger.info(f"Geradas {i}/{quantidade} notas...")

        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao gerar nota {i}: {e}")
            stats["erros"] += 1

    session.commit()
    logger.info(f"Geração concluida: {stats}")
    return stats


if __name__ == "__main__":
    init_db()
    s = Session()
    try:
        stats = popular_nfe_sinteticas(s, 1000)
        print(f"Resultado: {stats}")
    finally:
        s.close()
