"""Testes do validador XML de NF-e (estrutural e XSD)."""
import pytest
from src.importador.validador_xml import (
    validar_xml_nfe,
    validar_com_xsd_oficial,
    ResultadoValidacao,
)
import os

XSD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "schemas", "nfe", "nfe_v4.00_simplificado.xsd"
)

# XML válido de NF-e 4.00 (simplificado, com namespace)
XML_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <ide>
      <cUF>35</cUF>
      <natOp>Compra de mercadorias</natOp>
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
      <xNome>Distribuidora Alimentos SP Ltda</xNome>
      <enderEmit>
        <xLgr>Rua das Flores</xLgr>
        <nro>100</nro>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
        <CEP>01000000</CEP>
      </enderEmit>
    </emit>
    <dest>
      <CNPJ>12345678000190</CNPJ>
      <xNome>Minha Empresa Ltda</xNome>
      <enderDest>
        <xLgr>Av Paulista</xLgr>
        <xBairro>Bela Vista</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
      </enderDest>
    </dest>
    <det nItem="1">
      <prod>
        <cProd>001</cProd>
        <xProd>Farinha de trigo 1kg</xProd>
        <NCM>11010010</NCM>
        <CFOP>1102</CFOP>
        <uCom>UN</uCom>
        <qCom>100</qCom>
        <vUnCom>5.00</vUnCom>
        <vProd>500.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <orig>0</orig>
            <CST>00</CST>
            <modBC>3</modBC>
            <vBC>500.00</vBC>
            <pICMS>18.00</pICMS>
            <vICMS>90.00</vICMS>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vNF>500.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>"""

# XML sem infNFe
XML_SEM_INFNFE = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <ide>
    <cUF>35</cUF>
  </ide>
</NFe>"""

# XML mal formado
XML_MAL_FORMADO = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <ide>
      <cUF>35</cUF>
    """

# XML sem ide
XML_SEM_IDE = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <emit>
      <CNPJ>11222333000144</CNPJ>
      <xNome>Teste</xNome>
      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>SP</xMun>
        <UF>SP</UF>
      </enderEmit>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>001</cProd>
        <xProd>Teste</xProd>
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

# XML sem itens
XML_SEM_ITENS = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <ide>
      <cUF>35</cUF>
      <natOp>Teste</natOp>
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
      <xNome>Teste</xNome>
      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>SP</xMun>
        <UF>SP</UF>
      </enderEmit>
    </emit>
    <total>
      <ICMSTot>
        <vNF>0.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>"""

# XML vazio
XML_VAZIO = ""

# XML muito grande (simular DoS)
XML_GIGANTE = "x" * (11 * 1024 * 1024)


class TestValidacaoEstrutural:
    def test_xml_valido(self):
        r = validar_xml_nfe(XML_VALIDO)
        assert r.valido
        assert len(r.erros) == 0

    def test_xml_vazio(self):
        r = validar_xml_nfe(XML_VAZIO)
        assert not r.valido
        assert "XML vazio" in r.erros[0]

    def test_xml_mal_formado(self):
        r = validar_xml_nfe(XML_MAL_FORMADO)
        assert not r.valido
        assert any("mal formado" in e.lower() for e in r.erros)

    def test_xml_sem_infnfe(self):
        r = validar_xml_nfe(XML_SEM_INFNFE)
        assert not r.valido
        assert any("infNFe" in e for e in r.erros)

    def test_xml_sem_ide(self):
        r = validar_xml_nfe(XML_SEM_IDE)
        assert not r.valido
        assert any("ide" in e for e in r.erros)

    def test_xml_sem_itens(self):
        r = validar_xml_nfe(XML_SEM_ITENS)
        assert not r.valido
        assert any("det" in e.lower() or "item" in e.lower() for e in r.erros)

    def test_xml_gigante_bloqueado(self):
        r = validar_xml_nfe(XML_GIGANTE)
        assert not r.valido
        assert any("tamanho" in e.lower() for e in r.erros)

    def test_xml_com_versao_valida(self):
        r = validar_xml_nfe(XML_VALIDO)
        # Não deve ter erro de versão
        assert not any("versao" in e.lower() for e in r.erros)

    def test_xml_sem_total(self):
        xml = XML_VALIDO.replace("<total>", "").replace("</total>", "")
        xml = xml.replace('<ICMSTot><vNF>500.00</vNF></ICMSTot>', "")
        r = validar_xml_nfe(xml)
        assert not r.valido


class TestValidacaoXSD:
    def test_xsd_xml_valido(self):
        r = validar_com_xsd_oficial(XML_VALIDO, XSD_PATH)
        assert r.valido, f"Erros XSD: {r.erros}"

    def test_xsd_xml_sem_ide_falha(self):
        r = validar_com_xsd_oficial(XML_SEM_IDE, XSD_PATH)
        assert not r.valido

    def test_xsd_xml_mal_formado_falha(self):
        r = validar_com_xsd_oficial(XML_MAL_FORMADO, XSD_PATH)
        assert not r.valido

    def test_xsd_xml_sem_itens_falha(self):
        r = validar_com_xsd_oficial(XML_SEM_ITENS, XSD_PATH)
        # det é maxOccurs=990 mas minOccurs default é 1
        assert not r.valido

    def test_xsd_caminho_inexistente(self):
        r = validar_com_xsd_oficial(XML_VALIDO, "/caminho/inexistente.xsd")
        assert not r.valido
        assert any("Erro" in e for e in r.erros)

    def test_xsd_xml_vazio_falha(self):
        r = validar_com_xsd_oficial("", XSD_PATH)
        assert not r.valido


class TestProtecaoXXE:
    """Testa que o parser é resistente a XXE (XML External Entity)."""

    XML_XXE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00" Id="NFe35200811222333000144550010000000011000000001">
    <ide>
      <cUF>35</cUF>
      <natOp>&xxe;</natOp>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>1</nNF>
      <dhEmi>2026-07-15T10:00:00</dhEmi>
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
      <xNome>Teste</xNome>
      <enderEmit>
        <xLgr>Rua</xLgr>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>SP</xMun>
        <UF>SP</UF>
      </enderEmit>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>001</cProd>
        <xProd>Teste</xProd>
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

    def test_xxe_nao_expande(self):
        """O parser não deve expandir entidades externas."""
        r = validar_xml_nfe(self.XML_XXE)
        # Não deve conter conteúdo de /etc/passwd
        for erro in r.erros:
            assert "root:" not in erro
            assert "/bin/" not in erro
