"""Servidor mock SEFAZ - simula a Receita Federal para testes.

Endpoints:
- GET  /health              -> status do servico
- POST /nfe-distribuicao    -> consulta DF-e por NSU (retorna resumos)
- POST /nfe-manifestacao    -> registra manifestacao do destinatario
- GET  /nfe/{chave}/xml     -> retorna XML completo da nota
- GET  /status-servico      -> status do servico SEFAZ
"""
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from src.mock_sefaz.pool_nfe import (
    POOL_NFE, get_notas_apartir_nsu, get_nfe_by_chave,
    manifestar_nfe, get_nfe_by_nsu, reset_pool,
)

app = FastAPI(title="Mock SEFAZ", description="Simulador da Receita Federal para testes")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-sefaz"}


@app.get("/status-serviço")
async def status_servico():
    """Simula NFeStatusServico: retorna que o serviço está em operação."""
    return {
        "status": "114",
        "motivo": "Serviço em Operação",
        "data_consulta": datetime.now().isoformat(),
    }


@app.post("/reset")
async def reset_mock():
    """Reseta o mock para o estado inicial (notas não manifestadas)."""
    reset_pool()
    return {"status": "ok", "motivo": "Mock resetado"}


@app.post("/nfe-distribuicao")
async def nfe_distribuicao(request: Request):
    """Simula NFeDistribuicaoDFe: retorna documentos a partir do ultimo NSU.

    Body esperado: {"ultimo_nsu": 0, "cnpj": "12345678000190"}
    """
    body = await request.json()
    ultimo_nsu = body.get("ultimo_nsu", 0)
    limite = body.get("limite", 50)

    notas = get_notas_apartir_nsu(ultimo_nsu, limite)

    if not notas:
        return {
            "status": "0",
            "motivo": "Nenhum documento localizado",
            "ultimo_nsu": ultimo_nsu,
            "documentos": [],
        }

    documentos = []
    for nota in notas:
        documentos.append({
            "nsu": nota["nsu"],
            "chave": nota["chave"],
            "emitente_cnpj": nota["emitente_cnpj"],
            "emitente_nome": nota["emitente_nome"],
            "valor_total": nota["valor_total"],
            "data_emissao": nota["data_emissao"],
            "tipo": nota["tipo"],
            "manifestada": nota["manifestada"],
            "cancelada": nota["cancelada"],
            "tem_xml_completo": nota["manifestada"],
            "protocolo_autorizacao": f"335{nota['data_emissao'].replace('-', '').replace('T', '').replace(':', '')[:14]}",
            "data_autorizacao": nota["data_emissao"],
        })

    return {
        "status": "138",
        "motivo": "Localizado documentos para o destinatário",
        "ultimo_nsu": max(n["nsu"] for n in notas),
        "total_documentos": len(documentos),
        "documentos": documentos,
    }


@app.post("/nfe-manifestação")
async def nfe_manifestacao(request: Request):
    """Simula recepcao de evento de manifestacao do destinatario.

    Body esperado: {"chave": "...", "tipo_evento": "ciencia_emissao"}
    """
    body = await request.json()
    chave = body.get("chave", "")
    tipo_evento = body.get("tipo_evento", "ciencia_emissao")

    sucesso = manifestar_nfe(chave)
    if not sucesso:
        return JSONResponse(
            status_code=404,
            content={"status": "631", "motivo": "Rejeição: Chave de acesso inválida"},
        )

    return {
        "status": "135",
        "motivo": "Evento registrado e vinculado a NF-e",
        "chave": chave,
        "tipo_evento": tipo_evento,
        "data_evento": datetime.now().isoformat(),
        "protocolo": f"135{datetime.now().strftime('%Y%m%d%H%M%S')}",
    }


@app.get("/nfe/{chave}/xml")
async def get_xml(chave: str):
    """Retorna o XML completo da nota (simulado em formato simplificado)."""
    nota = get_nfe_by_chave(chave)
    if not nota:
        return JSONResponse(
            status_code=404,
            content={"status": "631", "motivo": "Chave de acesso não encontrada"},
        )

    if not nota["manifestada"]:
        return JSONResponse(
            status_code=403,
            content={"status": "632", "motivo": "Rejeição: NF-e não manifestada"},
        )

    xml = _gerar_xml_nfe(nota)
    return PlainTextResponse(content=xml, media_type="application/xml")


@app.get("/nfe/{chave}")
async def get_resumo(chave: str):
    """Retorna o resumo de uma nota específica."""
    nota = get_nfe_by_chave(chave)
    if not nota:
        return JSONResponse(status_code=404, content={"erro": "Nota não encontrada"})

    return {
        "nsu": nota["nsu"],
        "chave": nota["chave"],
        "numero": nota["numero"],
        "serie": nota["serie"],
        "data_emissao": nota["data_emissao"],
        "emitente_cnpj": nota["emitente_cnpj"],
        "emitente_nome": nota["emitente_nome"],
        "valor_total": nota["valor_total"],
        "valor_produtos": nota.get("valor_produtos"),
        "valor_desconto": nota.get("valor_desconto"),
        "valor_frete": nota.get("valor_frete"),
        "valor_seguro": nota.get("valor_seguro"),
        "valor_outros": nota.get("valor_outros"),
        "modalidade_frete": nota.get("modalidade_frete"),
        "tipo": nota["tipo"],
        "natureza": nota["natureza"],
        "cfop": nota["cfop"],
        "manifestada": nota["manifestada"],
        "cancelada": nota["cancelada"],
        "tem_ibscbs": nota["tem_ibscbs"],
        "cenario": nota["cenario"],
        "itens": nota["itens"],
        "protocolo_autorizacao": f"335{nota['data_emissao'].replace('-', '').replace('T', '').replace(':', '')[:14]}",
        "data_autorizacao": nota["data_emissao"],
    }


@app.get("/pool")
async def listar_pool():
    """Lista todas as notas do pool (para debug e testes)."""
    return {
        "total": len(POOL_NFE),
        "notas": [
            {
                "nsu": n["nsu"],
                "chave": n["chave"],
                "emitente": n["emitente_nome"],
                "valor": n["valor_total"],
                "cenario": n["cenario"],
                "manifestada": n["manifestada"],
                "cancelada": n["cancelada"],
            }
            for n in POOL_NFE
        ],
    }


def _gerar_xml_nfe(nota: dict) -> str:
    """Gera um XML simplificado representando a NF-e (não e o XML oficial)."""
    itens_xml = ""
    for i, item in enumerate(nota["itens"], 1):
        itens_xml += f"""
    <det nItem="{i}">
      <prod>
        <cProd>{item['codigo']}</cProd>
        <xProd>{item['descricao']}</xProd>
        <NCM>{item['ncm']}</NCM>
        <CFOP>{item['cfop']}</CFOP>
        <uCom>UN</uCom>
        <qCom>{item['quantidade']}</qCom>
        <vUnCom>{item['valor_unitario']}</vUnCom>
        <vProd>{item['valor_total']}</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <orig>0</orig>
            <CST>00</CST>
            <modBC>3</modBC>
            <vBC>{item['valor_total']}</vBC>
            <pICMS>18.00</pICMS>
            <vICMS>{item['valor_total'] * 0.18:.2f}</vICMS>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>"""

    ibscbs_tag = ""
    if nota["tem_ibscbs"]:
        ibscbs_tag = """
      <gIBSCBS>
        <vBCIBSCBS>""" + str(nota["valor_total"]) + """</vBCIBSCBS>
        <pIBSCBS>1.00</pIBSCBS>
        <vIBSCBS>""" + str(nota["valor_total"] * 0.01) + """</vIBSCBS>
      </gIBSCBS>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe{nota['chave']}" versao="4.00">
    <ide>
      <cUF>35</cUF>
      <cNF>{nota['numero']:08d}</cNF>
      <natOp>{nota['natureza']}</natOp>
      <mod>{nota.get('modelo', '55')}</mod>
      <serie>{nota['serie']}</serie>
      <nNF>{nota['numero']}</nNF>
      <dhEmi>{nota['data_emissao']}</dhEmi>
      <tpNF>{'1' if nota['tipo'] == 'saída' else '0'}</tpNF>
      <idDest>1</idDest>
      <cMunFG>3550308</cMunFG>
      <tpImp>1</tpImp>
      <tpEmis>1</tpEmis>
      <cDV>{nota['chave'][-1]}</cDV>
      <tpAmb>2</tpAmb>
      <finNFe>1</finNFe>
      <indFinal>1</indFinal>
      <indPres>9</indPres>
      <procEmi>0</procEmi>
    </ide>
    <emit>
      <CNPJ>{nota['emitente_cnpj']}</CNPJ>
      <xNome>{nota['emitente_nome']}</xNome>
      <enderEmit>
        <xLgr>Rua Teste</xLgr>
        <nro>123</nro>
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
        <xLgr>Av Principal</xLgr>
        <nro>1000</nro>
        <xBairro>Centro</xBairro>
        <cMun>3550308</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
        <CEP>01000000</CEP>
      </enderDest>
    </dest>{itens_xml}
    <total>
      <ICMSTot>
        <vNF>{nota['valor_total']}</vNF>
      </ICMSTot>
    </total>{ibscbs_tag}
  </infNFe>
</NFe>"""
