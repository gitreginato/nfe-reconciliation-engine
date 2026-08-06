"""Validacao de XML de NF-e baseada no layout 4.00 (Pacote 010b v1.30).

Como o schema XSD oficial da Receita tem ~200 arquivos interdependentes,
esta validacao verifica estruturalmente os campos obrigatorios do XML
conforme o Manual de Integracao do Contribuinte v6.004.

Para validacao XSD completa, usar `lxml.etree.XMLSchema` com o pacote
de schemas da Receita (ver metodo `validar_com_xsd_oficial`).
"""
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Limite maximo de tamanho do XML (10MB) para prevenir DoS
MAX_XML_SIZE = 10 * 1024 * 1024

# Tenta usar defusedxml (protecao contra XXE). Se nao disponivel, usa lxml com resolve_entities=False.
_USE_DEFUSED = False
_USE_LXML = False
try:
    from defusedxml import ElementTree as ET
    _USE_DEFUSED = True
except ImportError:
    try:
        from lxml import etree as _lxml_etree
        _USE_LXML = True
        from xml.etree import ElementTree as ET  # fallback para API compativel
    except ImportError:
        from xml.etree import ElementTree as ET
        logger.warning("defusedxml/lxml nao instalado. XML parsing sem protecao XXE.")


@dataclass
class ResultadoValidacao:
    valido: bool
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _extract_tag(elem) -> str:
    """Extrai o nome da tag sem o namespace."""
    tag = elem.tag
    if "}" in tag:
        return tag.split("}")[1]
    return tag


def validar_xml_nfe(xml_str: str) -> ResultadoValidacao:
    """Valida um XML de NF-e verificando campos obrigatorios do layout 4.00.

    Args:
        xml_str: String com o XML da NF-e

    Returns:
        ResultadoValidacao com erros e avisos
    """
    resultado = ResultadoValidacao(valido=True)

    if not xml_str or not xml_str.strip():
        resultado.valido = False
        resultado.erros.append("XML vazio")
        return resultado

    # 0. Verificar tamanho maximo (prevenir DoS)
    if len(xml_str) > MAX_XML_SIZE:
        resultado.valido = False
        resultado.erros.append(f"XML excede tamanho maximo de {MAX_XML_SIZE} bytes")
        logger.warning(f"XML rejeitado por tamanho: {len(xml_str)} bytes")
        return resultado

    # 1. Parse do XML (com protecao XXE se defusedxml/lxml disponivel)
    try:
        if _USE_DEFUSED:
            root = ET.fromstring(xml_str)
        elif _USE_LXML:
            root = _lxml_etree.fromstring(
                xml_str.encode("utf-8"),
                _lxml_etree.XMLParser(resolve_entities=False, no_network=True),
            )
        else:
            root = ET.fromstring(xml_str)
    except Exception as e:
        resultado.valido = False
        resultado.erros.append(f"XML mal formado: {e}")
        logger.warning(f"XML mal formado rejeitado: {e}")
        return resultado

    # 2. Encontrar elemento NFe
    nfe_elem = None
    if _extract_tag(root) == "NFe":
        nfe_elem = root
    else:
        for elem in root.iter():
            if _extract_tag(elem) == "NFe":
                nfe_elem = elem
                break

    if nfe_elem is None:
        resultado.valido = False
        resultado.erros.append("Elemento NFe nao encontrado")
        return resultado

    # 3. Verificar infNFe
    inf_nfe = None
    for elem in nfe_elem:
        if _extract_tag(elem) == "infNFe":
            inf_nfe = elem
            break

    if inf_nfe is None:
        resultado.valido = False
        resultado.erros.append("Elemento infNFe nao encontrado")
        return resultado

    # 4. Verificar atributo versao
    versao = inf_nfe.get("versao")
    if not versao:
        resultado.erros.append("Atributo 'versao' ausente em infNFe")
        resultado.valido = False
    elif versao not in ("4.00", "3.10"):
        resultado.avisos.append(f"Versao nao suportada: {versao}")

    # 5. Verificar ide (identificacao)
    ide = _find_child(inf_nfe, "ide")
    if ide is None:
        resultado.erros.append("Elemento ide nao encontrado")
        resultado.valido = False
    else:
        _validar_ide(ide, resultado)

    # 6. Verificar emit
    emit = _find_child(inf_nfe, "emit")
    if emit is None:
        resultado.erros.append("Elemento emit nao encontrado")
        resultado.valido = False
    else:
        _validar_participante(emit, "emit", resultado)

    # 7. Verificar dest
    dest = _find_child(inf_nfe, "dest")
    if dest is None:
        resultado.avisos.append("Elemento dest ausente (opcional para alguns modelos)")
    else:
        _validar_participante(dest, "dest", resultado)

    # 8. Verificar itens (det)
    dets = [e for e in inf_nfe if _extract_tag(e) == "det"]
    if not dets:
        resultado.erros.append("Nenhum item (det) encontrado")
        resultado.valido = False
    else:
        for i, det in enumerate(dets, 1):
            _validar_item(det, i, resultado)

    # 9. Verificar total
    total = _find_child(inf_nfe, "total")
    if total is None:
        resultado.erros.append("Elemento total nao encontrado")
        resultado.valido = False
    else:
        icms_tot = _find_child(total, "ICMSTot")
        if icms_tot is None:
            resultado.erros.append("Elemento ICMSTot nao encontrado")
            resultado.valido = False
        else:
            v_nf = _find_child(icms_tot, "vNF")
            if v_nf is None or not v_nf.text:
                resultado.erros.append("Campo vNF (valor total) ausente")
                resultado.valido = False

    # 10. Verificar chave de acesso (44 digitos)
    chave = inf_nfe.get("Id", "")
    if not chave.startswith("NFe"):
        resultado.avisos.append("Atributo Id em infNFe deveria comecar com 'NFe'")
    else:
        chave_num = chave[3:]
        if not re.match(r"^\d{44}$", chave_num):
            resultado.erros.append(f"Chave de acesso invalida: {chave_num}")
            resultado.valido = False

    if resultado.erros:
        resultado.valido = False

    return resultado


def _find_child(parent, tag_name: str):
    """Encontra o primeiro filho com a tag especificada (ignorando namespace)."""
    for elem in parent:
        if _extract_tag(elem) == tag_name:
            return elem
    return None


def _find_text(parent, tag_name: str) -> str | None:
    """Encontra o texto de um filho, ou None."""
    child = _find_child(parent, tag_name)
    return child.text if child is not None and child.text else None


def _validar_ide(ide, resultado: ResultadoValidacao):
    """Valida campos obrigatorios do elemento ide."""
    campos_obrigatorios = ["cUF", "natOp", "mod", "serie", "nNF", "dhEmi", "tpNF", "idDest", "cMunFG", "tpImp", "tpEmis", "cDV", "tpAmb", "finNFe", "indFinal", "indPres", "procEmi"]
    for campo in campos_obrigatorios:
        val = _find_text(ide, campo)
        if not val:
            resultado.erros.append(f"Campo obrigatorio ausente em ide: {campo}")
            resultado.valido = False

    # Validar cUF (codigo UF: 11-53)
    cuf = _find_text(ide, "cUF")
    if cuf and not re.match(r"^\d{2}$", cuf):
        resultado.erros.append(f"cUF invalido: {cuf}")
        resultado.valido = False

    # Validar modelo (55=NF-e, 65=NFC-e)
    mod = _find_text(ide, "mod")
    if mod and mod not in ("55", "65"):
        resultado.avisos.append(f"Modelo nao padrao: {mod}")

    # Validar dhEmi (formato ISO 8601)
    dh_emi = _find_text(ide, "dhEmi")
    if dh_emi and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", dh_emi):
        resultado.avisos.append(f"dhEmi fora do formato ISO 8601: {dh_emi}")


def _validar_participante(part, nome: str, resultado: ResultadoValidacao):
    """Valida campos obrigatorios de emit/dest."""
    # CNPJ ou CPF e obrigatorio (um dos dois)
    cnpj = _find_text(part, "CNPJ")
    cpf = _find_text(part, "CPF")
    if not cnpj and not cpf:
        resultado.erros.append(f"{nome}: CNPJ ou CPF obrigatorio ausente")
        resultado.valido = False
    elif cnpj and not re.match(r"^\d{14}$", cnpj):
        resultado.erros.append(f"{nome}: CNPJ invalido: {cnpj}")
        resultado.valido = False
    elif cpf and not re.match(r"^\d{11}$", cpf):
        resultado.erros.append(f"{nome}: CPF invalido: {cpf}")
        resultado.valido = False

    # xNome e obrigatorio
    xnome = _find_text(part, "xNome")
    if not xnome:
        resultado.erros.append(f"{nome}: xNome obrigatorio ausente")
        resultado.valido = False

    # Ender e obrigatorio
    ender = _find_child(part, "enderEmit") if nome == "emit" else _find_child(part, "enderDest")
    if ender is None:
        resultado.erros.append(f"{nome}: enderEmit/enderDest obrigatorio ausente")
        resultado.valido = False
    else:
        xmun = _find_text(ender, "xMun")
        uf = _find_text(ender, "UF")
        if not xmun:
            resultado.erros.append(f"{nome}: xMun ausente no endereco")
            resultado.valido = False
        if not uf or not re.match(r"^[A-Z]{2}$", uf):
            resultado.erros.append(f"{nome}: UF invalida no endereco")
            resultado.valido = False


def _validar_item(det, num: int, resultado: ResultadoValidacao):
    """Valida um item (det) da NF-e."""
    prod = _find_child(det, "prod")
    if prod is None:
        resultado.erros.append(f"Item {num}: elemento prod ausente")
        resultado.valido = False
        return

    campos_prod = ["cProd", "xProd", "NCM", "CFOP", "uCom", "qCom", "vUnCom", "vProd"]
    for campo in campos_prod:
        val = _find_text(prod, campo)
        if not val:
            resultado.erros.append(f"Item {num}: campo {campo} ausente em prod")
            resultado.valido = False

    # NCM deve ter 8 digitos (ou 00 para isentos)
    ncm = _find_text(prod, "NCM")
    if ncm and not re.match(r"^\d{8}$|^00$", ncm):
        resultado.avisos.append(f"Item {num}: NCM fora do padrao: {ncm}")

    # CFOP deve ter 4 digitos
    cfop = _find_text(prod, "CFOP")
    if cfop and not re.match(r"^\d{4}$", cfop):
        resultado.erros.append(f"Item {num}: CFOP invalido: {cfop}")
        resultado.valido = False

    # Imposto e obrigatorio
    imposto = _find_child(det, "imposto")
    if imposto is None:
        resultado.erros.append(f"Item {num}: elemento imposto ausente")
        resultado.valido = False


def validar_com_xsd_oficial(xml_str: str, xsd_path: str) -> ResultadoValidacao:
    """Valida XML contra o schema XSD oficial da Receita.

    Requer o pacote de schemas XSD da Receita (Pacote de Liberação 010b)
    disponivel em xsd_path. Usa lxml para validacao.

    Args:
        xml_str: String com o XML da NF-e
        xsd_path: Caminho para o arquivo nfe_v4.00.xsd

    Returns:
        ResultadoValidacao
    """
    try:
        from lxml import etree
    except ImportError:
        return ResultadoValidacao(
            valido=False,
            erros=["lxml nao instalado. Instale com: pip install lxml"],
        )

    resultado = ResultadoValidacao(valido=True)
    try:
        schema_doc = etree.parse(xsd_path)
        schema = etree.XMLSchema(schema_doc)
        xml_doc = etree.fromstring(xml_str.encode("utf-8"))
        if not schema.validate(xml_doc):
            for error in schema.error_log:
                resultado.erros.append(f"Linha {error.line}: {error.message}")
            resultado.valido = False
    except Exception as e:
        resultado.valido = False
        resultado.erros.append(f"Erro ao validar XSD: {e}")

    return resultado
