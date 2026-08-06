"""Testes de cobertura para validador_xml.py e validadores.py.

Cobre buracos de cobertura identificados pelo relatorio:
- src/importador/validador_xml.py: 70% -> 95%+
- src/fiscal/validadores.py: 92% -> 98%+
"""
import importlib
import os
import sys
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.importador.validador_xml import (
    validar_xml_nfe,
    validar_com_xsd_oficial,
    ResultadoValidacao,
    _extract_tag,
)
from src.fiscal.validadores import (
    validar_cnpj, validar_cpf, validar_ncm, validar_cfop,
    validar_cfop_compatibilidade, categoria_contabil_cfop,
    validar_chave_acesso_dv, validar_protocolo,
    validar_cst_icms, validar_csosn, validar_cst_pis_cofins,
    validar_partida_dobrada, validar_valor_total_nfe,
    validar_periodo_ecd, calcular_prazo_entrega_ecd,
    validar_prazo_manifestacao, mascara_cnpj, mascara_chave,
)

XSD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "schemas", "nfe", "nfe_v4.00_simplificado.xsd"
)

# XML base valido SEM namespace (cobre _extract_tag sem namespace, linha 47)
XML_BASE = """<?xml version="1.0" encoding="UTF-8"?>
<NFe>
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <ide>
      <cUF>35</cUF>
      <natOp>Compra</natOp>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>1</nNF>
      <dhEmi>2026-07-15T10:00:00-03:00</dhEmi>
      <tpNF>0</tpNF>
      <idDest>1</idDest>
      <cMunFG>3550308</cMunFG>
      <tpImp>1</tpImp>
      <tpEmis>1</tpEmis>
      <cDV>0</cDV>
      <tpAmb>2</tpAmb>
      <finNFe>1</finNFe>
      <indFinal>1</indFinal>
      <indPres>1</indPres>
      <procEmi>0</procEmi>
    </ide>
    <emit>
      <CNPJ>11222333000144</CNPJ>
      <xNome>Empresa Teste</xNome>
      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
      </enderEmit>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>001</cProd>
        <xProd>Produto</xProd>
        <NCM>11010010</NCM>
        <CFOP>1102</CFOP>
        <uCom>UN</uCom>
        <qCom>1</qCom>
        <vUnCom>10.00</vUnCom>
        <vProd>10.00</vProd>
      </prod>
      <imposto/>
    </det>
    <total>
      <ICMSTot>
        <vNF>10.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>"""

# XML com NFe aninhado em outra raiz (cobre linhas 95-98: busca em root.iter)
XML_NFE_ANINHADO = XML_BASE.replace(
    "<NFe>\n", "<enviNFe>\n<NFe>\n"
).replace(
    "</NFe>", "</NFe>\n</enviNFe>"
)

# XML sem elemento NFe (cobre linhas 101-103)
XML_SEM_NFE = '<?xml version="1.0" encoding="UTF-8"?>\n<enviNFe><outro>dados</outro></enviNFe>'

# XML mal formado (cobre linhas 84-88: except no parse)
XML_MAL_FORMADO = '<?xml version="1.0"?>\n<NFe><infNFe versao="4.00"'

# XML vazio (cobre linhas 61-64)
XML_VAZIO = ""

# XML apenas com espacos (cobre linhas 61-64)
XML_SO_ESPACOS = "   \n  "

# --- Variacoes do XML_BASE para cobrir linhas especificas ---

# Linha 120-121: versao ausente em infNFe
XML_SEM_VERSAO = XML_BASE.replace('versao="4.00" Id=', 'Id=')

# Linha 123: versao nao suportada (aviso)
XML_VERSAO_NAO_SUPORTADA = XML_BASE.replace('versao="4.00"', 'versao="2.00"')

# Linha 136-137: emit ausente
XML_SEM_EMIT = XML_BASE.replace(
    """    <emit>
      <CNPJ>11222333000144</CNPJ>
      <xNome>Empresa Teste</xNome>
      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
      </enderEmit>
    </emit>
""", ""
)

# Linha 165-166: ICMSTot ausente em total
XML_SEM_ICMSTOT = XML_BASE.replace(
    """      <ICMSTot>
        <vNF>10.00</vNF>
      </ICMSTot>""", ""
)

# Linha 170-171: vNF ausente em ICMSTot
XML_SEM_VNF = XML_BASE.replace("<vNF>10.00</vNF>", "")

# Linha 176: Id nao comeca com NFe (aviso)
XML_ID_SEM_NFE = XML_BASE.replace(
    'Id="NFe35200811222333000144550010000000011000000001"', 'Id="ABC123"'
)

# Linha 180-181: chave de acesso invalida (nao 44 digitos)
XML_CHAVE_INVALIDA = XML_BASE.replace(
    'Id="NFe35200811222333000144550010000000011000000001"', 'Id="NFe123"'
)

# Linha 209-210: campo obrigatorio ausente em ide
XML_IDE_SEM_NATOP = XML_BASE.replace("<natOp>Compra</natOp>", "")

# Linha 215-216: cUF invalido (nao numerico)
XML_CUF_INVALIDO = XML_BASE.replace("<cUF>35</cUF>", "<cUF>XYZ</cUF>")

# Linha 221: modelo nao padrao (aviso)
XML_MOD_NAO_PADRAO = XML_BASE.replace("<mod>55</mod>", "<mod>99</mod>")

# Linha 226: dhEmi fora do formato ISO 8601 (aviso)
XML_DHEMI_FORA_FORMATO = XML_BASE.replace(
    "<dhEmi>2026-07-15T10:00:00-03:00</dhEmi>", "<dhEmi>15/07/2026</dhEmi>"
)

# Linha 235-236: emit sem CNPJ e sem CPF
XML_SEM_CNPJ_CPF = XML_BASE.replace("<CNPJ>11222333000144</CNPJ>", "")

# Linha 238-239: CNPJ invalido (nao 14 digitos)
XML_CNPJ_INVALIDO = XML_BASE.replace("<CNPJ>11222333000144</CNPJ>", "<CNPJ>123</CNPJ>")

# Linha 241-242: CPF invalido (nao 11 digitos)
XML_CPF_INVALIDO = XML_BASE.replace(
    "<CNPJ>11222333000144</CNPJ>", "<CPF>123</CPF>"
)

# Linha 247-248: xNome ausente em emit
XML_SEM_XNOME = XML_BASE.replace("<xNome>Empresa Teste</xNome>", "")

# Linha 253-254: enderEmit ausente
XML_SEM_ENDER = XML_BASE.replace(
    """      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
      </enderEmit>""", ""
)

# Linha 259-260: xMun ausente no endereco
XML_SEM_XMUN = XML_BASE.replace("<xMun>Sao Paulo</xMun>", "")

# Linha 262-263: UF invalida no endereco
XML_UF_INVALIDA = XML_BASE.replace("<UF>SP</UF>", "<UF>XYZ</UF>")

# Linha 270-272: prod ausente em det
XML_SEM_PROD = XML_BASE.replace(
    """      <prod>
        <cProd>001</cProd>
        <xProd>Produto</xProd>
        <NCM>11010010</NCM>
        <CFOP>1102</CFOP>
        <uCom>UN</uCom>
        <qCom>1</qCom>
        <vUnCom>10.00</vUnCom>
        <vProd>10.00</vProd>
      </prod>""", ""
)

# Linha 278-279: campo ausente em prod
XML_PROD_SEM_CPROD = XML_BASE.replace("<cProd>001</cProd>", "")

# Linha 284: NCM fora do padrao (aviso)
XML_NCM_FORA_PADRAO = XML_BASE.replace("<NCM>11010010</NCM>", "<NCM>123</NCM>")

# Linha 289-290: CFOP invalido (nao 4 digitos)
XML_CFOP_INVALIDO = XML_BASE.replace("<CFOP>1102</CFOP>", "<CFOP>ABC</CFOP>")

# Linha 295-296: imposto ausente em det
XML_SEM_IMPOSTO = XML_BASE.replace("<imposto/>", "")


# ===========================================================================
# Testes do validador XML estrutural
# ===========================================================================

class TestValidadorXmlEstrutural:
    """Cobre linhas faltantes em validar_xml_nfe e funcoes auxiliares."""

    def test_xml_valido_sem_namespace(self):
        """XML valido sem namespace (cobre linha 47: _extract_tag sem namespace)."""
        r = validar_xml_nfe(XML_BASE)
        assert r.valido, f"Erros: {r.erros}"

    def test_extract_tag_sem_namespace(self):
        """Cobre linha 47: _extract_tag com tag sem namespace."""
        class FakeElem:
            tag = "NFe"
        assert _extract_tag(FakeElem()) == "NFe"

    def test_extract_tag_com_namespace(self):
        """_extract_tag com namespace (cobre caminho com '}' na tag)."""
        class FakeElem:
            tag = "{http://www.portalfiscal.inf.br/nfe}NFe"
        assert _extract_tag(FakeElem()) == "NFe"

    def test_xml_nfe_aninhado(self):
        """Cobre linhas 95-98: busca NFe em root.iter() quando raiz nao e NFe."""
        r = validar_xml_nfe(XML_NFE_ANINHADO)
        # Encontra NFe aninhado; nao deve ter erro de "NFe nao encontrado"
        assert not any("NFe nao encontrado" in e for e in r.erros)

    def test_xml_sem_nfe(self):
        """Cobre linhas 101-103: elemento NFe nao encontrado."""
        r = validar_xml_nfe(XML_SEM_NFE)
        assert not r.valido
        assert any("NFe nao encontrado" in e for e in r.erros)

    def test_xml_mal_formado(self):
        """Cobre linhas 84-88: XML mal formado rejeitado no parse."""
        r = validar_xml_nfe(XML_MAL_FORMADO)
        assert not r.valido
        assert any("mal formado" in e.lower() for e in r.erros)

    def test_xml_vazio(self):
        """Cobre linhas 61-64: XML vazio rejeitado."""
        r = validar_xml_nfe(XML_VAZIO)
        assert not r.valido
        assert "XML vazio" in r.erros[0]

    def test_xml_so_espacos(self):
        """Cobre linhas 61-64: XML com apenas espacos rejeitado."""
        r = validar_xml_nfe(XML_SO_ESPACOS)
        assert not r.valido
        assert "XML vazio" in r.erros[0]

    def test_xml_sem_versao(self):
        """Cobre linhas 120-121: atributo versao ausente em infNFe."""
        r = validar_xml_nfe(XML_SEM_VERSAO)
        assert not r.valido
        assert any("versao" in e.lower() for e in r.erros)

    def test_xml_versao_nao_suportada(self):
        """Cobre linha 123: versao nao suportada gera aviso."""
        r = validar_xml_nfe(XML_VERSAO_NAO_SUPORTADA)
        assert any("Versao nao suportada" in e for e in r.avisos)

    def test_xml_sem_emit(self):
        """Cobre linhas 136-137: elemento emit nao encontrado."""
        r = validar_xml_nfe(XML_SEM_EMIT)
        assert not r.valido
        assert any("emit" in e for e in r.erros)

    def test_xml_sem_icmstot(self):
        """Cobre linhas 165-166: ICMSTot nao encontrado."""
        r = validar_xml_nfe(XML_SEM_ICMSTOT)
        assert not r.valido
        assert any("ICMSTot" in e for e in r.erros)

    def test_xml_sem_vnf(self):
        """Cobre linhas 170-171: vNF ausente em ICMSTot."""
        r = validar_xml_nfe(XML_SEM_VNF)
        assert not r.valido
        assert any("vNF" in e for e in r.erros)

    def test_xml_id_sem_nfe(self):
        """Cobre linha 176: Id nao comeca com NFe gera aviso."""
        r = validar_xml_nfe(XML_ID_SEM_NFE)
        assert any("NFe" in a for a in r.avisos)

    def test_xml_chave_invalida(self):
        """Cobre linhas 180-181: chave de acesso invalida."""
        r = validar_xml_nfe(XML_CHAVE_INVALIDA)
        assert not r.valido
        assert any("Chave de acesso" in e for e in r.erros)

    def test_xml_ide_sem_campo_obrigatorio(self):
        """Cobre linhas 209-210: campo obrigatorio ausente em ide."""
        r = validar_xml_nfe(XML_IDE_SEM_NATOP)
        assert not r.valido
        assert any("natOp" in e for e in r.erros)

    def test_xml_cuf_invalido(self):
        """Cobre linhas 215-216: cUF invalido."""
        r = validar_xml_nfe(XML_CUF_INVALIDO)
        assert not r.valido
        assert any("cUF" in e for e in r.erros)

    def test_xml_mod_nao_padrao(self):
        """Cobre linha 221: modelo nao padrao gera aviso."""
        r = validar_xml_nfe(XML_MOD_NAO_PADRAO)
        assert any("Modelo nao padrao" in a for a in r.avisos)

    def test_xml_dhemi_fora_formato(self):
        """Cobre linha 226: dhEmi fora do formato ISO 8601 gera aviso."""
        r = validar_xml_nfe(XML_DHEMI_FORA_FORMATO)
        assert any("dhEmi" in a for a in r.avisos)

    def test_xml_emit_sem_cnpj_cpf(self):
        """Cobre linhas 235-236: CNPJ ou CPF obrigatorio ausente."""
        r = validar_xml_nfe(XML_SEM_CNPJ_CPF)
        assert not r.valido
        assert any("CNPJ ou CPF" in e for e in r.erros)

    def test_xml_cnpj_invalido(self):
        """Cobre linhas 238-239: CNPJ invalido em emit."""
        r = validar_xml_nfe(XML_CNPJ_INVALIDO)
        assert not r.valido
        assert any("CNPJ invalido" in e for e in r.erros)

    def test_xml_cpf_invalido(self):
        """Cobre linhas 241-242: CPF invalido em emit."""
        r = validar_xml_nfe(XML_CPF_INVALIDO)
        assert not r.valido
        assert any("CPF invalido" in e for e in r.erros)

    def test_xml_sem_xnome(self):
        """Cobre linhas 247-248: xNome obrigatorio ausente."""
        r = validar_xml_nfe(XML_SEM_XNOME)
        assert not r.valido
        assert any("xNome" in e for e in r.erros)

    def test_xml_sem_ender(self):
        """Cobre linhas 253-254: enderEmit ausente."""
        r = validar_xml_nfe(XML_SEM_ENDER)
        assert not r.valido
        assert any("enderEmit" in e or "enderDest" in e for e in r.erros)

    def test_xml_sem_xmun(self):
        """Cobre linhas 259-260: xMun ausente no endereco."""
        r = validar_xml_nfe(XML_SEM_XMUN)
        assert not r.valido
        assert any("xMun" in e for e in r.erros)

    def test_xml_uf_invalida(self):
        """Cobre linhas 262-263: UF invalida no endereco."""
        r = validar_xml_nfe(XML_UF_INVALIDA)
        assert not r.valido
        assert any("UF" in e for e in r.erros)

    def test_xml_det_sem_prod(self):
        """Cobre linhas 270-272: elemento prod ausente em det."""
        r = validar_xml_nfe(XML_SEM_PROD)
        assert not r.valido
        assert any("prod ausente" in e for e in r.erros)

    def test_xml_prod_sem_cprod(self):
        """Cobre linhas 278-279: campo cProd ausente em prod."""
        r = validar_xml_nfe(XML_PROD_SEM_CPROD)
        assert not r.valido
        assert any("cProd" in e for e in r.erros)

    def test_xml_ncm_fora_padrao(self):
        """Cobre linha 284: NCM fora do padrao gera aviso."""
        r = validar_xml_nfe(XML_NCM_FORA_PADRAO)
        assert any("NCM" in a for a in r.avisos)

    def test_xml_cfop_invalido(self):
        """Cobre linhas 289-290: CFOP invalido em prod."""
        r = validar_xml_nfe(XML_CFOP_INVALIDO)
        assert not r.valido
        assert any("CFOP" in e for e in r.erros)

    def test_xml_det_sem_imposto(self):
        """Cobre linhas 295-296: elemento imposto ausente em det."""
        r = validar_xml_nfe(XML_SEM_IMPOSTO)
        assert not r.valido
        assert any("imposto" in e for e in r.erros)

    def test_resultado_validacao_defaults(self):
        """Testa estrutura de retorno ResultadoValidacao com defaults."""
        rv = ResultadoValidacao(valido=True)
        assert rv.valido is True
        assert rv.erros == []
        assert rv.avisos == []

    def test_resultado_validacao_com_erros(self):
        """Testa ResultadoValidacao com erros e avisos preenchidos."""
        rv = ResultadoValidacao(
            valido=False,
            erros=["erro1", "erro2"],
            avisos=["aviso1"],
        )
        assert rv.valido is False
        assert len(rv.erros) == 2
        assert len(rv.avisos) == 1


# ===========================================================================
# Testes de fallback de imports e parse
# ===========================================================================

class TestValidadorXmlImports:
    """Cobre linhas 25-32 (fallback de imports) e 77-83 (branches de parse)."""

    @pytest.fixture(autouse=True)
    def _restore_mod(self):
        """Garante que o modulo original seja restaurado apos cada teste."""
        import src.importador.validador_xml as mod
        self._mod_key = "src.importador.validador_xml"
        self._saved_mod = sys.modules.get(self._mod_key)
        yield
        if self._saved_mod is not None:
            sys.modules[self._mod_key] = self._saved_mod

    def test_fallback_sem_defusedxml_com_lxml(self):
        """Cobre linhas 25-29: defusedxml indisponivel, lxml disponivel."""
        with patch.dict(sys.modules, {
            "defusedxml": None,
            "defusedxml.ElementTree": None,
        }):
            sys.modules.pop(self._mod_key, None)
            new_mod = importlib.import_module(self._mod_key)
            assert new_mod._USE_DEFUSED is False
            assert new_mod._USE_LXML is True

    def test_fallback_sem_defusedxml_sem_lxml(self):
        """Cobre linhas 30-32: nem defusedxml nem lxml disponiveis."""
        with patch.dict(sys.modules, {
            "defusedxml": None,
            "defusedxml.ElementTree": None,
            "lxml": None,
            "lxml.etree": None,
        }):
            sys.modules.pop(self._mod_key, None)
            new_mod = importlib.import_module(self._mod_key)
            assert new_mod._USE_DEFUSED is False
            assert new_mod._USE_LXML is False

    def test_parse_via_lxml(self):
        """Cobre linhas 77-81: parse via lxml quando defusedxml desativado."""
        import src.importador.validador_xml as mod
        from lxml import etree as _lxml_etree

        orig_defused = mod._USE_DEFUSED
        orig_lxml = mod._USE_LXML
        had_lxml_etree = hasattr(mod, "_lxml_etree")

        mod._USE_DEFUSED = False
        mod._USE_LXML = True
        mod._lxml_etree = _lxml_etree

        try:
            r = mod.validar_xml_nfe(XML_BASE)
            assert r.valido, f"Erros: {r.erros}"
        finally:
            mod._USE_DEFUSED = orig_defused
            mod._USE_LXML = orig_lxml
            if not had_lxml_etree:
                del mod._lxml_etree

    def test_parse_via_et_puro(self):
        """Cobre linha 83: parse via xml.etree puro (sem defusedxml nem lxml)."""
        import src.importador.validador_xml as mod

        orig_defused = mod._USE_DEFUSED
        orig_lxml = mod._USE_LXML

        mod._USE_DEFUSED = False
        mod._USE_LXML = False

        try:
            r = mod.validar_xml_nfe(XML_BASE)
            assert r.valido, f"Erros: {r.erros}"
        finally:
            mod._USE_DEFUSED = orig_defused
            mod._USE_LXML = orig_lxml


# ===========================================================================
# Testes de validacao XSD
# ===========================================================================

class TestValidadorXmlXSD:
    """Cobre linhas 314-315: validar_com_xsd_oficial sem lxml instalado."""

    def test_xsd_sem_lxml_disponivel(self):
        """Cobre linhas 314-315: retorna erro quando lxml nao instalado."""
        import src.importador.validador_xml as mod

        with patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
            r = mod.validar_com_xsd_oficial(XML_BASE, XSD_PATH)
            assert not r.valido
            assert any("lxml" in e.lower() for e in r.erros)


# ===========================================================================
# Testes de edge cases em validadores.py
# ===========================================================================

class TestValidadoresEdgeCases:
    """Cobre linhas faltantes em src/fiscal/validadores.py."""

    # --- Linhas 159, 165: validar_cfop_compatibilidade ---

    def test_cfop_compatibilidade_cfop_invalido(self):
        """Linha 159: retorna False quando CFOP invalido."""
        assert validar_cfop_compatibilidade("9999", "0") is False

    def test_cfop_compatibilidade_tipo_invalido(self):
        """Linha 165: retorna False quando tipo_operacao nao e 0 nem 1."""
        assert validar_cfop_compatibilidade("1102", "2") is False

    # --- Linha 213: categoria_contabil_cfop ---

    def test_categoria_contabil_generico_cfop_6xxx(self):
        """Linha 213: CFOP 6xxx valido retorna 'generico' (nao 1 nem 5)."""
        assert categoria_contabil_cfop("6101") == "generico"

    # --- Linhas 269, 279: validar_cpf ---

    def test_cpf_vazio(self):
        """Linha 269: retorna False quando CPF vazio."""
        assert validar_cpf("") is False
        assert validar_cpf(None) is False

    def test_cpf_dv1_errado(self):
        """Linha 279: retorna False quando primeiro digito verificador errado."""
        # CPF 11144477735 tem dv1=3; mudar dígito 9 para 4 faz dv1 != 4
        assert validar_cpf("11144477745") is False

    def test_cpf_com_letras(self):
        """CPF com letras e rejeitado apos re.sub remover nao-digitos."""
        assert validar_cpf("111.444.777-AB") is False

    # --- Linhas 332, 339, 346: validar_cst_icms, validar_csosn, validar_cst_pis_cofins ---

    def test_cst_icms_vazio(self):
        """Linha 332: retorna False quando CST ICMS vazio."""
        assert validar_cst_icms("") is False
        assert validar_cst_icms(None) is False

    def test_csosn_vazio(self):
        """Linha 339: retorna False quando CSOSN vazio."""
        assert validar_csosn("") is False
        assert validar_csosn(None) is False

    def test_cst_pis_cofins_vazio(self):
        """Linha 346: retorna False quando CST PIS/COFINS vazio."""
        assert validar_cst_pis_cofins("") is False
        assert validar_cst_pis_cofins(None) is False

    def test_cst_icms_fora_lista(self):
        """CST ICMS fora da lista de valores validos."""
        assert validar_cst_icms("15") is False

    def test_csosn_fora_lista(self):
        """CSOSN fora da lista de valores validos."""
        assert validar_csosn("999") is False

    # --- Linhas 413, 415, 427, 429: validar_valor_total_nfe ---

    def test_valor_total_nfe_com_int(self):
        """Linhas 413, 415: conversao de int para Decimal."""
        assert validar_valor_total_nfe(1000, 1000) is True

    def test_valor_total_nfe_com_seguro_e_outros(self):
        """Linhas 427, 429: valor_seguro e valor_outros somados."""
        assert validar_valor_total_nfe(
            Decimal("1200"), Decimal("1000"),
            valor_seguro=Decimal("100"),
            valor_outros=Decimal("100"),
        ) is True

    # --- Linhas 473, 480: validar_periodo_ecd ---

    def test_periodo_ecd_data_none(self):
        """Linha 473: retorna False quando data_inicio ou data_fim e None."""
        valido, msg = validar_periodo_ecd(None, date(2026, 1, 1))
        assert not valido
        assert "obrigatorias" in msg.lower()

    def test_periodo_ecd_dias_negativo_fake(self):
        """Linha 480: dias < 0 sem disparar data_inicio > data_fim.

        Usa subclasse de date que override __gt__ para retornar False,
        permitindo que dias < 0 seja alcancado sem o guard anterior.
        """
        class FakeDate(date):
            def __gt__(self, other):
                return False

        valido, msg = validar_periodo_ecd(
            FakeDate(2026, 12, 31), FakeDate(2026, 1, 1)
        )
        assert not valido
        assert "invalido" in msg.lower()

    # --- Linha 498: calcular_prazo_entrega_ecd ---

    def test_prazo_entrega_ecd_2028(self):
        """Linha 498: 30/06/2029 e sabado, volta para sexta (29/06).

        Ano calendario 2028 tem entrega em 2029; 30/06/2029 cai no sabado,
        acionando o loop que recua para o ultimo dia util.
        """
        prazo = calcular_prazo_entrega_ecd(2028)
        assert prazo.year == 2029
        assert prazo.month == 6
        assert prazo.day == 29
        assert prazo.weekday() == 4  # sexta-feira

    # --- Linha 528: validar_prazo_manifestacao ---

    def test_prazo_manifestacao_data_none(self):
        """Linha 528: retorna False quando data_emissao ou data_manifestacao e None."""
        assert validar_prazo_manifestacao(None, date(2026, 1, 1)) is False
        assert validar_prazo_manifestacao(date(2026, 1, 1), None) is False

    # --- Linhas 545, 555: mascara_cnpj, mascara_chave ---

    def test_mascara_cnpj_vazio(self):
        """Linha 545: retorna string vazia quando CNPJ vazio."""
        assert mascara_cnpj("") == ""
        assert mascara_cnpj(None) == ""

    def test_mascara_chave_vazia(self):
        """Linha 555: retorna string vazia quando chave vazia."""
        assert mascara_chave("") == ""
        assert mascara_chave(None) == ""

    # --- Edge cases adicionais pedidos ---

    def test_cnpj_com_letras(self):
        """CNPJ com letras e rejeitado apos re.sub."""
        assert validar_cnpj("11.222.333/0001-AB") is False

    def test_cnpj_muito_curto(self):
        """CNPJ muito curto e rejeitado."""
        assert validar_cnpj("123") is False

    def test_ncm_vazio(self):
        """NCM vazio e rejeitado."""
        assert validar_ncm("") is False

    def test_cfop_muito_curto(self):
        """CFOP muito curto e rejeitado."""
        assert validar_cfop("12") is False

    def test_chave_acesso_uf_invalida(self):
        """Chave de acesso com UF invalida (99) e rejeitada."""
        assert validar_chave_acesso_dv("99200812345678000190550010000000011000000001") is False

    def test_chave_acesso_mes_invalido(self):
        """Chave de acesso com mes 13 e rejeitada."""
        assert validar_chave_acesso_dv("35201312345678000190550010000000011000000001") is False

    def test_protocolo_muito_curto(self):
        """Protocolo muito curto e rejeitado."""
        assert validar_protocolo("12345") is False
