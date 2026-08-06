"""Dashboard principal - FastAPI + Jinja2.

Endpoints:
- GET  /                          -> dashboard com metricas e lista de notas
- GET  /notas/{chave}             -> visao detalhada e auditavel de uma NF-e
- GET  /crossover                 -> visao de ligacoes entre documentos
- GET  /crossover/{chave}         -> crossover de uma nota especifica
- POST /api/importacao/executar   -> dispara importacao DF-e
- GET  /api/dashboard             -> metricas em JSON
- GET  /api/notas                 -> lista de notas em JSON
- GET  /api/notas/{chave}         -> detalhe de uma nota em JSON
- GET  /api/crossover/{chave}     -> crossover de uma nota em JSON
"""
from datetime import datetime
from decimal import Decimal
from html import escape as html_escape
import csv
import io
import logging
from fastapi import FastAPI, Depends, HTTPException, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

logger = logging.getLogger(__name__)

from src.persistencia.models import (
    get_session, Nfe, NfeItem, NfeTributo, NfePagamento, NfeEvento,
    Participante, Reconciliacao, LancamentoContabil, PedidoCompra,
    DfeImportacao,
)
from src.importador.dfe import executar_importacao
from src.reconciliacao.motor import executar_reconciliacao, popular_pedidos_demo
from src.contabilidade.gerador import executar_lancamentos
from src.contabilidade.ecd import ExportadorECD
from src.fiscal.apuracao import apurar_mes_dict
from src.importador.manifestacao import executar_manifestacao_automatica, identificar_notas_pendentes
from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas
from tests.gerador_sintetico import popular_nfe_sinteticas
from src.config import settings

app = FastAPI(
    title="Sistema de Contabilidade com NF-e",
    description="Importação, reconciliação e gestão de notas fiscais eletronicas",
    version="0.2.0",
)

CSS = """
body { font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
h1 { color: #2c3e50; margin-bottom: 5px; }
h2 { color: #2c3e50; margin-top: 30px; }
h3 { color: #34495e; }
a { color: #3498db; text-decoration: none; }
a:hover { text-decoration: underline; }
.nav { margin: 10px 0; }
.nav a { margin-right: 15px; padding: 6px 14px; background: #ecf0f1; border-radius: 6px; font-size: 14px; }
.nav a:hover { background: #d5dbdb; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; margin: 20px 0; }
.card { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h3 { margin: 0 0 6px 0; color: #7f8c8d; font-size: 12px; text-transform: uppercase; }
.card .value { font-size: 26px; font-weight: bold; color: #2c3e50; }
.status { margin-top: 10px; padding: 10px; background: #e8f5e9; border-radius: 6px; color: #2e7d32; font-size: 14px; }
.status.mock { background: #fff3e0; color: #e65100; }
.btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 15px; margin: 10px 0; }
.btn:hover { background: #2980b9; }
.btn:disabled { background: #bdc3c7; cursor: wait; }
.btn-sec { background: #2ecc71; }
.btn-sec:hover { background: #27ae60; }
table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 10px 0; }
th { background: #2c3e50; color: white; padding: 10px; text-align: left; font-size: 12px; text-transform: uppercase; }
td { padding: 8px 10px; border-bottom: 1px solid #eee; font-size: 13px; }
tr:hover { background: #f8f9fa; }
.section-title { margin-top: 30px; margin-bottom: 10px; color: #2c3e50; }
#resultado { margin: 10px 0; padding: 10px; border-radius: 6px; display: none; }
#resultado.sucesso { background: #e8f5e9; color: #2e7d32; }
#resultado.erro { background: #ffebee; color: #c62828; }
.badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
.badge-green { background: #e8f5e9; color: #2e7d32; }
.badge-red { background: #ffebee; color: #c62828; }
.badge-yellow { background: #fff8e1; color: #f57f17; }
.badge-blue { background: #e3f2fd; color: #1565c0; }
.badge-gray { background: #eceff1; color: #455a64; }
.detalhe-box { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 10px 0; }
.detalhe-box h3 { margin-top: 0; }
.detalhe-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.detalhe-item { padding: 8px; border-bottom: 1px solid #f0f0f0; }
.detalhe-label { color: #7f8c8d; font-size: 12px; text-transform: uppercase; }
.detalhe-value { font-size: 15px; font-weight: 500; }
.crossover-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 20px 0; }
.crossover-node { background: white; border: 2px solid #3498db; border-radius: 8px; padding: 15px; min-width: 150px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.crossover-node.matched { border-color: #2ecc71; }
.crossover-node.divergent { border-color: #e74c3c; }
.crossover-node.pending { border-color: #f39c12; }
.crossover-node.empty { border-color: #bdc3c7; opacity: 0.5; }
.crossover-node h4 { margin: 0 0 5px 0; font-size: 13px; color: #7f8c8d; text-transform: uppercase; }
.crossover-node .node-value { font-size: 16px; font-weight: bold; color: #2c3e50; }
.crossover-arrow { font-size: 24px; color: #bdc3c7; }
.xml-box { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; overflow-x: auto; max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
"""


def _badge(status: str) -> str:
    colors = {
        "autorizada": "badge-green",
        "cancelada": "badge-red",
        "matched": "badge-green",
        "divergent": "badge-red",
        "pending": "badge-yellow",
        "ciencia_emissao": "badge-blue",
    }
    cls = colors.get(status, "badge-gray")
    return f'<span class="badge {cls}">{status}</span>'


def _fmt_money(v) -> str:
    """Formata valor monetário para exibição em BRL.

    Usa Decimal internamente para precisão, converte para float apenas
    na formatação final (borda de apresentação).
    """
    if not v:
        return "R$ 0,00"
    if isinstance(v, Decimal):
        return f"R$ {float(v.quantize(Decimal('0.01'))):,.2f}"
    return f"R$ {float(v):,.2f}"


def _to_float(v) -> float:
    """Converte Decimal para float com quantização de 2 casas.

    Garante que valores monetários sejam serializados com precisão
    consistente (2 casas decimais), evitando artefatos de float.
    """
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v.quantize(Decimal("0.01")))
    return float(v)


def _fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "-"


def _fmt_datetime(d) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if d else "-"


def _esc(s) -> str:
    """Escapa string para prevenir XSS em templates HTML."""
    return html_escape(str(s)) if s is not None else "-"


def _validar_chave(chave: str) -> bool:
    """Valida formato da chave de acesso (44 dígitos numéricos)."""
    return bool(chave) and len(chave) == 44 and chave.isdigit()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "contabilidade",
        "version": "0.2.0",
        "timestamp": datetime.now().isoformat(),
        "mock_sefaz": settings.mock_sefaz,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(session: Session = Depends(get_session)):
    """Dashboard inicial com métricas e lista de notas."""
    try:
        from sqlalchemy import func
        total_notas = session.query(func.count(Nfe.id)).scalar() or 0
        total_participantes = session.query(func.count(Participante.id)).scalar() or 0
        total_reconciliacoes = session.query(func.count(Reconciliacao.id)).scalar() or 0
        total_lancamentos = session.query(func.count(LancamentoContabil.id)).scalar() or 0
        valor_total = session.query(func.coalesce(func.sum(Nfe.valor_total), 0)).scalar() or 0
        notas_canceladas = session.query(func.count(Nfe.id)).filter(
            Nfe.status_autorizacao == "cancelada"
        ).scalar() or 0
        notas = session.query(Nfe).order_by(Nfe.data_emissao.desc()).limit(50).all()
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard: {e}")
        total_notas = total_participantes = total_reconciliacoes = total_lancamentos = 0
        valor_total = 0
        notas_canceladas = 0
        notas = []

    notas_html = ""
    if notas:
        for n in notas:
            status_badge = _badge(n.status_autorizacao)
            origem_badge = _badge(n.origem or "sefaz")
            protocolo_str = n.protocolo[:15] + "..." if n.protocolo and len(n.protocolo) > 15 else (n.protocolo or "Sem protocolo")
            notas_html += f"""
            <tr style="cursor: pointer;" onclick="window.location='/notas/{n.chave_acesso}'">
                <td><strong>{n.numero_nota}</strong></td>
                <td>{_fmt_date(n.data_emissao)}</td>
                <td>{_esc(n.emitente.nome) if n.emitente else '-'}</td>
                <td>{_fmt_money(n.valor_total)}</td>
                <td>{status_badge}</td>
                <td>{origem_badge}</td>
                <td><span style="font-size: 11px; color: #666;">{_esc(protocolo_str)}</span></td>
                <td>{_badge(n.manifestacao_destinatario) if n.manifestacao_destinatario else '-'}</td>
                <td><a href="/crossover/{n.chave_acesso}">Ver ligacoes</a></td>
            </tr>"""
    else:
        notas_html = '<tr><td colspan="9" style="text-align: center; color: #999; padding: 20px;">Nenhuma nota importada. Clique em "Importar Notas" acima.</td></tr>'

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contabilidade - Dashboard</title>
    <style>{CSS}</style>
</head>
<body>
    <h1>Sistema de Contabilidade com NF-e</h1>
    <div class="status {'mock' if settings.mock_sefaz else ''}">
        Ambiente: {settings.sefaz_ambiente} | Mock SEFAZ: {'ativo' if settings.mock_sefaz else 'inativo'}
    </div>

    <div class="nav">
        <a href="/">Dashboard</a>
        <a href="/crossover">Crossover de Documentos</a>
    </div>

    <button class="btn" id="btn-importar" onclick="importarNotas()">Importar Notas da Receita</button>
    <button class="btn btn-sec" id="btn-pedidos" onclick="popularPedidos()">Criar Pedidos Demo</button>
    <button class="btn" id="btn-reconciliar" onclick="reconciliar()" style="background: #9b59b6;">Reconciliar Notas</button>
    <button class="btn" id="btn-lancamentos" onclick="gerarLancamentos()" style="background: #e67e22;">Gerar Lançamentos Contábeis</button>
    <a class="btn" href="/api/export/csv?tipo=notas" style="background: #34495e;">Exportar Notas (CSV)</a>
    <a class="btn" href="/api/export/csv?tipo=reconciliacoes" style="background: #34495e;">Exportar Reconciliações (CSV)</a>
    <a class="btn" href="/api/export/csv?tipo=lancamentos" style="background: #34495e;">Exportar Lançamentos (CSV)</a>
    <a class="btn" href="#" onclick="exportarECD()" style="background: #16a085;">Exportar ECD (SPED)</a>
    <input type="date" id="ecd_data_inicio" value="{datetime.now().strftime('%Y-%m-01')}" style="padding: 6px; border-radius: 4px; border: 1px solid #ccc;">
    <input type="date" id="ecd_data_fim" value="{datetime.now().strftime('%Y-%m-%d')}" style="padding: 6px; border-radius: 4px; border: 1px solid #ccc;">
    <div id="resultado"></div>

    <div class="grid">
        <div class="card"><h3>Notas Importadas</h3><div class="value">{total_notas}</div></div>
        <div class="card"><h3>Notas Canceladas</h3><div class="value" style="color: #e74c3c;">{notas_canceladas}</div></div>
        <div class="card"><h3>Participantes</h3><div class="value">{total_participantes}</div></div>
        <div class="card"><h3>Reconciliações</h3><div class="value">{total_reconciliacoes}</div></div>
        <div class="card"><h3>Lançamentos Contábeis</h3><div class="value">{total_lancamentos}</div></div>
        <div class="card"><h3>Valor Total Importado</h3><div class="value">{_fmt_money(valor_total)}</div></div>
    </div>

    <h2 class="section-title">Notas Importadas</h2>
    <table>
        <thead><tr>
            <th>Número</th><th>Data</th><th>Emitente</th><th>Valor</th>
            <th>Status</th><th>Origem</th><th>Protocolo</th><th>Manifestação</th><th>Crossover</th>
        </tr></thead>
        <tbody>{notas_html}</tbody>
    </table>

    <script>
    async function importarNotas() {{
        const btn = document.getElementById('btn-importar');
        const resultado = document.getElementById('resultado');
        btn.disabled = true;
        btn.textContent = 'Importando...';
        resultado.style.display = 'none';
        try {{
            const resp = await fetch('/api/importacao/executar', {{ method: 'POST' }});
            const data = await resp.json();
            if (data.status === 'ok') {{
                const s = data.estatisticas;
                resultado.className = 'sucesso';
                resultado.style.display = 'block';
                resultado.textContent = `Consultadas: ${{s.consultadas}}, Importadas: ${{s.importadas}}, Duplicadas: ${{s.duplicadas}}, Canceladas: ${{s.canceladas}}, Erros: ${{s.erros}}`;
                setTimeout(() => location.reload(), 2000);
            }} else {{
                resultado.className = 'erro';
                resultado.style.display = 'block';
                resultado.textContent = 'Erro: ' + (data.mensagem || 'desconhecido');
            }}
        }} catch (e) {{
            resultado.className = 'erro';
            resultado.style.display = 'block';
            resultado.textContent = 'Erro de conexão: ' + e.message;
        }} finally {{
            btn.disabled = false;
            btn.textContent = 'Importar Notas da Receita';
        }}
    }}

    async function popularPedidos() {{
        const btn = document.getElementById('btn-pedidos');
        const resultado = document.getElementById('resultado');
        btn.disabled = true;
        btn.textContent = 'Criando...';
        resultado.style.display = 'none';
        try {{
            const resp = await fetch('/api/reconciliacao/popular-pedidos', {{ method: 'POST' }});
            const data = await resp.json();
            resultado.className = data.status === 'ok' ? 'sucesso' : 'erro';
            resultado.style.display = 'block';
            if (data.status === 'ok') {{
                resultado.textContent = `Pedidos criados: ${{data.resultado.criados}} (${{data.resultado.pedidos?.join(', ') || 'já existiam'}})`;
                setTimeout(() => location.reload(), 2000);
            }} else {{
                resultado.textContent = 'Erro: ' + (data.mensagem || 'desconhecido');
            }}
        }} catch (e) {{
            resultado.className = 'erro';
            resultado.style.display = 'block';
            resultado.textContent = 'Erro: ' + e.message;
        }} finally {{
            btn.disabled = false;
            btn.textContent = 'Criar Pedidos Demo';
        }}
    }}

    async function reconciliar() {{
        const btn = document.getElementById('btn-reconciliar');
        const resultado = document.getElementById('resultado');
        btn.disabled = true;
        btn.textContent = 'Reconciliando...';
        resultado.style.display = 'none';
        try {{
            const resp = await fetch('/api/reconciliacao/executar', {{ method: 'POST' }});
            const data = await resp.json();
            resultado.className = data.status === 'ok' ? 'sucesso' : 'erro';
            resultado.style.display = 'block';
            if (data.status === 'ok') {{
                const s = data.estatisticas;
                resultado.textContent = `Reconciliadas: ${{s.reconciliadas}}, Matched: ${{s.matched}}, Divergent: ${{s.divergent}}, Pending: ${{s.pending}}, Erros: ${{s.erros}}`;
                setTimeout(() => location.reload(), 2000);
            }} else {{
                resultado.textContent = 'Erro: ' + (data.mensagem || 'desconhecido');
            }}
        }} catch (e) {{
            resultado.className = 'erro';
            resultado.style.display = 'block';
            resultado.textContent = 'Erro: ' + e.message;
        }} finally {{
            btn.disabled = false;
            btn.textContent = 'Reconciliar Notas';
        }}
    }}

    async function gerarLancamentos() {{
        const btn = document.getElementById('btn-lancamentos');
        const resultado = document.getElementById('resultado');
        btn.disabled = true;
        btn.textContent = 'Gerando...';
        resultado.style.display = 'none';
        try {{
            const resp = await fetch('/api/lancamentos/executar', {{ method: 'POST' }});
            const data = await resp.json();
            resultado.className = data.status === 'ok' ? 'sucesso' : 'erro';
            resultado.style.display = 'block';
            if (data.status === 'ok') {{
                const s = data.estatisticas;
                resultado.textContent = `Notas processadas: ${{s.notas_processadas}}, Lancamentos gerados: ${{s.lancamentos_gerados}}, Puladas: ${{s.notas_puladas}}, Erros: ${{s.erros}}`;
                setTimeout(() => location.reload(), 2000);
            }} else {{
                resultado.textContent = 'Erro: ' + (data.mensagem || 'desconhecido');
            }}
        }} catch (e) {{
            resultado.className = 'erro';
            resultado.style.display = 'block';
            resultado.textContent = 'Erro: ' + e.message;
        }} finally {{
            btn.disabled = false;
            btn.textContent = 'Gerar Lançamentos Contábeis';
        }}
    }}
    </script>
</body>
</html>
    """


@app.get("/notas/{chave}", response_class=HTMLResponse)
async def detalhe_nfe(chave: str, session: Session = Depends(get_session)):
    """Visao detalhada e auditável de uma NF-e."""
    if not _validar_chave(chave):
        raise HTTPException(status_code=400, detail="Chave de acesso inválida (44 dígitos numéricos)")
    nfe = session.query(Nfe).filter_by(chave_acesso=chave).first()
    if not nfe:
        raise HTTPException(status_code=404, detail="NF-e não encontrada")

    emitente = nfe.emitente
    destinatario = nfe.destinatario
    itens = nfe.itens
    eventos = nfe.eventos
    pagamentos = nfe.pagamentos
    reconciliacoes = nfe.reconciliacoes
    lancamentos = nfe.lancamentos

    # Itens
    itens_html = ""
    for item in itens:
        ibscbs_html = ""
        if item.vibscbs:
            ibscbs_html = f"""
            <tr><td>Base IBS/CBS</td><td>{_fmt_money(item.vbc_ibscbs)}</td></tr>
            <tr><td>Aliquota IBS/CBS</td><td>{_to_float(item.aliquota_ibscbs):.2f}%</td></tr>
            <tr><td>Valor IBS/CBS</td><td>{_fmt_money(item.vibscbs)}</td></tr>"""
        itens_html += f"""
        <tr style="cursor: pointer;" onclick="toggleItem('item-{item.id}')">
            <td>{item.numero_item}</td>
            <td>{_esc(item.codigo_produto) if item.codigo_produto else '-'}</td>
            <td>{_esc(item.descricao)}</td>
            <td>{item.ncm or '-'}</td>
            <td>{item.cfop or '-'}</td>
            <td>{_to_float(item.quantidade) if item.quantidade else 0} {_esc(item.unidade) if item.unidade else ''}</td>
            <td>{_fmt_money(item.valor_unitario)}</td>
            <td>{_fmt_money(item.valor_total)}</td>
        </tr>
        <tr id="item-{item.id}" style="display: none; background: #fafafa;">
            <td colspan="8" style="padding: 15px;">
                <table style="box-shadow: none; margin: 0;">
                    <tr><td style="width: 200px; color: #7f8c8d;">ICMS</td><td>{_fmt_money(item.vicms)}</td></tr>
                    <tr><td style="color: #7f8c8d;">ICMS ST</td><td>{_fmt_money(item.vicms_st)}</td></tr>
                    <tr><td style="color: #7f8c8d;">IPI</td><td>{_fmt_money(item.vipi)}</td></tr>
                    <tr><td style="color: #7f8c8d;">PIS</td><td>{_fmt_money(item.vpis)}</td></tr>
                    <tr><td style="color: #7f8c8d;">COFINS</td><td>{_fmt_money(item.vcofins)}</td></tr>
                    {ibscbs_html}
                </table>
            </td>
        </tr>"""

    # Eventos
    eventos_html = ""
    if eventos:
        for ev in eventos:
            eventos_html += f"""
            <tr>
                <td>{_badge(ev.tipo_evento)}</td>
                <td>{_fmt_datetime(ev.data_evento)}</td>
                <td>{ev.protocolo or '-'}</td>
                <td>{_badge(ev.status) if ev.status else '-'}</td>
            </tr>"""
    else:
        eventos_html = '<tr><td colspan="4" style="color: #999; text-align: center;">Nenhum evento</td></tr>'

    # Pagamentos
    pag_html = ""
    if pagamentos:
        for p in pagamentos:
            pag_html += f"""
            <tr>
                <td>{p.forma_pagamento or '-'}</td>
                <td>{_fmt_money(p.valor_pago)}</td>
                <td>{p.bandeira or '-'}</td>
            </tr>"""
    else:
        pag_html = '<tr><td colspan="3" style="color: #999; text-align: center;">Sem informacao de pagamento</td></tr>'

    # Reconciliacoes
    rec_html = ""
    if reconciliacoes:
        for r in reconciliacoes:
            rec_html += f"""
            <tr>
                <td>{_badge(r.status)}</td>
                <td>{r.tipo_match or '-'}</td>
                <td>{r.matched_by}</td>
                <td>{_fmt_datetime(r.data_match)}</td>
                <td>{r.justificativa_resolucao or '-'}</td>
            </tr>"""
    else:
        rec_html = '<tr><td colspan="5" style="color: #999; text-align: center;">Sem reconciliação (fase 3)</td></tr>'

    # Lançamentos
    lan_html = ""
    if lancamentos:
        for l in lancamentos:
            estorno = ' <span class="badge badge-red">estornado</span>' if l.estornado else ''
            lan_html += f"""
            <tr>
                <td>{_fmt_date(l.data_lancamento)}</td>
                <td>{l.conta_debito_codigo or '-'}</td>
                <td>{l.conta_credito_codigo or '-'}</td>
                <td>{_fmt_money(l.valor)}</td>
                <td>{_esc(l.historico) if l.historico else '-'}{estorno}</td>
            </tr>"""
    else:
        lan_html = '<tr><td colspan="5" style="color: #999; text-align: center;">Sem lançamento contabil (fase 4)</td></tr>'

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NF-e {nfe.numero_nota} - Detalhe</title>
    <style>{CSS}</style>
</head>
<body>
    <div class="nav">
        <a href="/">&larr; Voltar ao Dashboard</a>
        <a href="/crossover/{chave}">Ver Crossover desta Nota</a>
    </div>

    <h1>NF-e Número {nfe.numero_nota}</h1>
    <p style="color: #7f8c8d; font-family: monospace; font-size: 13px;">Chave: {nfe.chave_acesso}</p>

    <div class="grid">
        <div class="card"><h3>Status</h3><div class="value">{_badge(nfe.status_autorizacao)}</div></div>
        <div class="card"><h3>Origem</h3><div class="value">{_badge(nfe.origem or 'sefaz')}</div></div>
        <div class="card"><h3>Valor Total</h3><div class="value">{_fmt_money(nfe.valor_total)}</div></div>
        <div class="card"><h3>Data Emissão</h3><div class="value" style="font-size: 18px;">{_fmt_date(nfe.data_emissao)}</div></div>
        <div class="card"><h3>Protocolo SEFAZ</h3><div class="value" style="font-size: 14px; word-break: break-all;">{_esc(nfe.protocolo or 'Sem protocolo')}</div></div>
        <div class="card"><h3>Data Autorização</h3><div class="value" style="font-size: 16px;">{_fmt_date(nfe.data_autorizacao) if nfe.data_autorizacao else '-'}</div></div>
        <div class="card"><h3>NSU</h3><div class="value">{nfe.nsu or '-'}</div></div>
        <div class="card"><h3>Modelo</h3><div class="value">{nfe.modelo}</div></div>
    </div>

    <h2>Emitente</h2>
    <div class="detalhe-box">
        <div class="detalhe-grid">
            <div class="detalhe-item"><div class="detalhe-label">CNPJ</div><div class="detalhe-value">{_esc(emitente.cnpj_cpf) if emitente else '-'}</div></div>
            <div class="detalhe-item"><div class="detalhe-label">Nome</div><div class="detalhe-value">{_esc(emitente.nome) if emitente else '-'}</div></div>
            <div class="detalhe-item"><div class="detalhe-label">Municipio</div><div class="detalhe-value">{_esc(emitente.municipio) if emitente else '-'}</div></div>
            <div class="detalhe-item"><div class="detalhe-label">UF</div><div class="detalhe-value">{_esc(emitente.uf) if emitente else '-'}</div></div>
        </div>
    </div>

    <h2>Destinatario</h2>
    <div class="detalhe-box">
        <div class="detalhe-grid">
            <div class="detalhe-item"><div class="detalhe-label">CNPJ</div><div class="detalhe-value">{_esc(destinatario.cnpj_cpf) if destinatario else '-'}</div></div>
            <div class="detalhe-item"><div class="detalhe-label">Nome</div><div class="detalhe-value">{_esc(destinatario.nome) if destinatario else '-'}</div></div>
        </div>
    </div>

    <h2>Itens (clique para ver tributos)</h2>
    <table>
        <thead><tr>
            <th>N.</th><th>Codigo</th><th>Descricao</th><th>NCM</th><th>CFOP</th>
            <th>Qtd</th><th>V. Unit.</th><th>V. Total</th>
        </tr></thead>
        <tbody>{itens_html}</tbody>
    </table>

    <h2>Eventos</h2>
    <table>
        <thead><tr><th>Tipo</th><th>Data</th><th>Protocolo</th><th>Status</th></tr></thead>
        <tbody>{eventos_html}</tbody>
    </table>

    <h2>Pagamentos</h2>
    <table>
        <thead><tr><th>Forma</th><th>Valor</th><th>Bandeira</th></tr></thead>
        <tbody>{pag_html}</tbody>
    </table>

    <h2>Reconciliacao</h2>
    <table>
        <thead><tr><th>Status</th><th>Tipo Match</th><th>Por</th><th>Data</th><th>Justificativa</th></tr></thead>
        <tbody>{rec_html}</tbody>
    </table>

    <h2>Lancamentos Contabeis</h2>
    <table>
        <thead><tr><th>Data</th><th>Debito</th><th>Credito</th><th>Valor</th><th>Historico</th></tr></thead>
        <tbody>{lan_html}</tbody>
    </table>

    <h2>XML Original</h2>
    <div class="xml-box">{_esc(nfe.xml_original) if nfe.xml_original else 'Sem XML'}</div>

    <script>
    function toggleItem(id) {{
        const el = document.getElementById(id);
        el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
    }}
    </script>
</body>
</html>
    """


@app.get("/crossover", response_class=HTMLResponse)
async def crossover_lista(session: Session = Depends(get_session)):
    """Visao geral de crossover: ligacoes entre documentos."""
    notas = session.query(Nfe).order_by(Nfe.data_emissao.desc()).all()

    cards_html = ""
    for n in notas:
        rec = n.reconciliacoes[0] if n.reconciliacoes else None
        lan = n.lancamentos[0] if n.lancamentos else None
        rec_status = rec.status if rec else "sem_reconciliacao"
        rec_cls = "matched" if rec_status == "matched" else ("divergent" if rec_status == "divergent" else ("pending" if rec_status == "pending" else "empty"))
        lan_cls = "" if lan else "empty"

        cards_html += f"""
        <div class="detalhe-box" style="cursor: pointer;" onclick="window.location='/crossover/{n.chave_acesso}'">
            <h3>NF-e {n.numero_nota} - {_esc(n.emitente.nome) if n.emitente else '?'}</h3>
            <div class="crossover-flow">
                <div class="crossover-node">
                    <h4>NF-e</h4>
                    <div class="node-value">{_fmt_money(n.valor_total)}</div>
                </div>
                <div class="crossover-arrow">&rarr;</div>
                <div class="crossover-node {rec_cls}">
                    <h4>Reconciliacao</h4>
                    <div class="node-value">{rec_status}</div>
                </div>
                <div class="crossover-arrow">&rarr;</div>
                <div class="crossover-node {lan_cls}">
                    <h4>Lancamento</h4>
                    <div class="node-value">{len(n.lancamentos)} lanc.</div>
                </div>
            </div>
        </div>"""

    if not cards_html:
        cards_html = '<div class="detalhe-box"><p style="color: #999; text-align: center;">Nenhuma nota importada. <a href="/">Importar notas primeiro.</a></p></div>'

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crossover de Documentos</title>
    <style>{CSS}</style>
</head>
<body>
    <div class="nav">
        <a href="/">&larr; Voltar ao Dashboard</a>
    </div>

    <h1>Crossover de Documentos</h1>
    <p style="color: #7f8c8d;">Mostra as ligacoes diretas entre NF-e, Pedido de Compra, Recebimento, Reconciliação e Lancamento Contabil.</p>

    <h2>Legenda</h2>
    <div class="crossover-flow">
        <div class="crossover-node matched"><h4>Verde</h4><div class="node-value">Matched</div></div>
        <div class="crossover-node divergent"><h4>Vermelho</h4><div class="node-value">Divergente</div></div>
        <div class="crossover-node pending"><h4>Amarelo</h4><div class="node-value">Pendente</div></div>
        <div class="crossover-node empty"><h4>Cinza</h4><div class="node-value">Sem dado</div></div>
    </div>

    {cards_html}
</body>
</html>
    """


@app.get("/crossover/{chave}", response_class=HTMLResponse)
async def crossover_nfe(chave: str, session: Session = Depends(get_session)):
    """Crossover detalhado de uma NF-e: todas as ligacoes."""
    if not _validar_chave(chave):
        raise HTTPException(status_code=400, detail="Chave de acesso inválida")
    nfe = session.query(Nfe).filter_by(chave_acesso=chave).first()
    if not nfe:
        raise HTTPException(status_code=404, detail="NF-e não encontrada")

    rec = nfe.reconciliacoes[0] if nfe.reconciliacoes else None
    pedido = rec.pedido if rec and rec.pedido else None
    recebimento = rec.recebimento if rec and rec.recebimento else None
    lancamentos = nfe.lancamentos

    rec_status = rec.status if rec else "sem_reconciliacao"
    rec_cls = "matched" if rec_status == "matched" else ("divergent" if rec_status == "divergent" else ("pending" if rec_status == "pending" else "empty"))

    # Pedido
    if pedido:
        pedido_cls = "matched"
        pedido_html = f"""
        <div class="crossover-node {pedido_cls}">
            <h4>Pedido de Compra</h4>
            <div class="node-value">{_esc(pedido.numero)}</div>
            <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                {_fmt_money(pedido.valor_total)}<br>
                {_fmt_date(pedido.data_pedido)}<br>
                {_esc(pedido.fornecedor_nome or pedido.fornecedor_cnpj)}
            </div>
        </div>"""
    else:
        pedido_html = """
        <div class="crossover-node empty">
            <h4>Pedido de Compra</h4>
            <div class="node-value">Nao vinculado</div>
        </div>"""

    # Recebimento
    if recebimento:
        receb_html = f"""
        <div class="crossover-node matched">
            <h4>Recebimento</h4>
            <div class="node-value">{_fmt_date(recebimento.data_recebimento)}</div>
            <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                {_esc(recebimento.responsavel) if recebimento.responsavel else '-'}
            </div>
        </div>"""
    else:
        receb_html = """
        <div class="crossover-node empty">
            <h4>Recebimento</h4>
            <div class="node-value">Nao vinculado</div>
        </div>"""

    # Lançamentos
    if lancamentos:
        lan_html = ""
        for l in lancamentos:
            estorno = " (estornado)" if l.estornado else ""
            lan_html += f"""
            <div class="crossover-node matched">
                <h4>Lancamento Contabil</h4>
                <div class="node-value">{_fmt_money(l.valor)}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                    D: {l.conta_debito_codigo or '-'}<br>
                    C: {l.conta_credito_codigo or '-'}<br>
                    {_fmt_date(l.data_lancamento)}{estorno}
                </div>
            </div>"""
    else:
        lan_html = """
        <div class="crossover-node empty">
            <h4>Lancamento Contabil</h4>
            <div class="node-value">Nao gerado</div>
        </div>"""

    # Divergencias
    div_html = ""
    if rec and rec.divergencias:
        div_html = "<h2>Divergencias Detectadas</h2><div class='detalhe-box'><table><thead><tr><th>Campo</th><th>Esperado</th><th>Encontrado</th><th>Diferenca</th></tr></thead><tbody>"
        for d in rec.divergencias:
            div_html += f"""
            <tr>
                <td>{d.get('campo', '-')}</td>
                <td>{d.get('esperado', '-')}</td>
                <td>{d.get('encontrado', '-')}</td>
                <td style="color: #e74c3c;">{d.get('diferenca', '-')}</td>
            </tr>"""
        div_html += "</tbody></table></div>"

    # Trilha de auditoria
    auditoria_html = f"""
    <h2>Trilha de Auditoria</h2>
    <div class="detalhe-box">
        <table>
            <thead><tr><th>Evento</th><th>Data/Hora</th><th>Detalhe</th></tr></thead>
            <tbody>
                <tr><td>Importacao DF-e</td><td>{_fmt_datetime(nfe.created_at)}</td><td>NSU {nfe.nsu or '-'}</td></tr>
                <tr><td>Manifestacao</td><td>{_fmt_datetime(nfe.created_at)}</td><td>{nfe.manifestacao_destinatario or '-'}</td></tr>
                {f'<tr><td>Reconciliação</td><td>{_fmt_datetime(rec.data_match)}</td><td>{rec.matched_by} - {rec.status}</td></tr>' if rec and rec.data_match else ''}
                {f'<tr><td>Resolucao manual</td><td>{_fmt_datetime(rec.data_resolucao)}</td><td>{rec.resolvido_por} - {rec.justificativa_resolucao or ""}</td></tr>' if rec and rec.data_resolucao else ''}
            </tbody>
        </table>
    </div>"""

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crossover - NF-e {nfe.numero_nota}</title>
    <style>{CSS}</style>
</head>
<body>
    <div class="nav">
        <a href="/">&larr; Dashboard</a>
        <a href="/crossover">&larr; Lista de Crossovers</a>
        <a href="/notas/{chave}">Ver Detalhe da Nota</a>
    </div>

    <h1>Crossover: NF-e {nfe.numero_nota}</h1>
    <p style="color: #7f8c8d; font-family: monospace; font-size: 13px;">Chave: {nfe.chave_acesso}</p>

    <h2>Fluxo de Documentos</h2>
    <div class="crossover-flow">
        <div class="crossover-node">
            <h4>NF-e</h4>
            <div class="node-value">{_fmt_money(nfe.valor_total)}</div>
            <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                {_esc(nfe.emitente.nome) if nfe.emitente else '-'}<br>
                {_fmt_date(nfe.data_emissao)}
            </div>
        </div>
        <div class="crossover-arrow">&rarr;</div>
        {pedido_html}
        <div class="crossover-arrow">&rarr;</div>
        {receb_html}
        <div class="crossover-arrow">&rarr;</div>
        <div class="crossover-node {rec_cls}">
            <h4>Reconciliacao</h4>
            <div class="node-value">{rec_status}</div>
            <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                {rec.tipo_match if rec else '-'}<br>
                {rec.matched_by if rec else '-'}
            </div>
        </div>
        <div class="crossover-arrow">&rarr;</div>
        {lan_html}
    </div>

    {div_html}
    {auditoria_html}
</body>
</html>
    """


# ============================================================================
# API JSON
# ============================================================================

@app.post("/api/reconciliacoes/{rec_id}/resolver")
async def api_resolver_divergencia(
    rec_id: int,
    justificativa: str = Query(..., min_length=10, max_length=2000, description="Justificativa da resolucao (min 10 chars)"),
    resolvido_por: str = Query(..., min_length=2, max_length=255, description="Nome de quem resolveu (min 2 chars)"),
    session: Session = Depends(get_session),
):
    """Resolve uma divergência manualmente, marcando como matched."""
    rec = session.query(Reconciliacao).filter_by(id=rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada")

    rec.status = "matched"
    rec.resolvido_por = resolvido_por
    rec.data_resolucao = datetime.now()
    rec.justificativa_resolucao = justificativa
    session.commit()
    return {"status": "ok", "reconciliacao_id": rec_id, "novo_status": "matched"}


@app.get("/api/export/csv")
async def api_export_csv(
    tipo: str = Query("notas", description="Tipo: notas, reconciliacoes ou lançamentos"),
    session: Session = Depends(get_session),
):
    """Exporta dados em formato CSV."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    if tipo == "notas":
        writer.writerow(["Número", "Chave", "Data", "Emitente", "CNPJ", "Valor", "Status", "Origem", "Protocolo", "Manifestação"])
        for n in session.query(Nfe).order_by(Nfe.numero_nota).all():
            writer.writerow([
                n.numero_nota, n.chave_acesso,
                n.data_emissao.strftime("%d/%m/%Y") if n.data_emissao else "",
                n.emitente.nome if n.emitente else "",
                n.emitente.cnpj_cpf if n.emitente else "",
                _to_float(n.valor_total) if n.valor_total else 0,
                n.status_autorizacao, n.origem or "sefaz",
                n.protocolo or "", n.manifestacao_destinatario or "",
            ])
    elif tipo == "reconciliacoes":
        writer.writerow(["ID", "NF-e", "Pedido", "Status", "Tipo", "Divergencias", "Data"])
        for r in session.query(Reconciliacao).all():
            writer.writerow([
                r.id, r.nfe.numero_nota if r.nfe else "",
                r.pedido.numero if r.pedido else "",
                r.status, r.tipo_match or "",
                len(r.divergencias) if r.divergencias else 0,
                r.data_match.strftime("%d/%m/%Y %H:%M") if r.data_match else "",
            ])
    elif tipo == "lancamentos":
        writer.writerow(["ID", "NF-e", "Data", "Debito", "Credito", "Valor", "Historico", "Estornado"])
        for l in session.query(LancamentoContabil).order_by(LancamentoContabil.id).all():
            writer.writerow([
                l.id, l.nfe.numero_nota if l.nfe else "",
                l.data_lancamento.strftime("%d/%m/%Y") if l.data_lancamento else "",
                l.conta_debito_codigo or "", l.conta_credito_codigo or "",
                _to_float(l.valor) if l.valor else 0,
                l.historico or "", "Sim" if l.estornado else "Nao",
            ])
    else:
        raise HTTPException(status_code=400, detail="Tipo deve ser: notas, reconciliacoes ou lancamentos")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={tipo}_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


@app.get("/api/export/ecd")
async def api_export_ecd(
    data_inicio: str = Query(..., description="Data inicial (YYYY-MM-DD)"),
    data_fim: str = Query(..., description="Data final (YYYY-MM-DD)"),
    session: Session = Depends(get_session),
):
    """Exporta lançamentos em formato ECD (SPED Contabil)."""
    from datetime import date as date_type, timedelta as td
    try:
        ini = date_type.fromisoformat(data_inicio)
        fim = date_type.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")

    if fim < ini:
        raise HTTPException(status_code=400, detail="Data final não pode ser anterior a data inicial")
    if (fim - ini).days > 366:
        raise HTTPException(status_code=400, detail="Periodo maximo de 1 ano (366 dias)")

    cnpj = settings.cnpj_consultado
    nome = settings.destinatario_nome
    exportador = ExportadorECD(session)
    conteudo = exportador.exportar(ini, fim, cnpj, nome)
    return StreamingResponse(
        iter([conteudo]),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=ecd_{data_inicio}_{data_fim}.txt"},
    )


@app.get("/api/notas")
async def api_listar_notas(
    status: str = Query(None, description="Filtrar por status"),
    emitente_cnpj: str = Query(None, description="Filtrar por CNPJ do emitente"),
    data_inicio: str = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: str = Query(None, description="Data final (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Pagina (1-based)"),
    page_size: int = Query(50, ge=1, le=500, description="Itens por pagina (max 500)"),
    session: Session = Depends(get_session),
):
    """Lista notas com filtros opcionais e paginacao."""
    query = session.query(Nfe)
    if status:
        query = query.filter(Nfe.status_autorizacao == status)
    if emitente_cnpj:
        query = query.join(Participante, Nfe.emitente_id == Participante.id).filter(
            Participante.cnpj_cpf == emitente_cnpj
        )
    if data_inicio:
        from datetime import datetime as dt
        try:
            query = query.filter(Nfe.data_emissao >= dt.fromisoformat(data_inicio))
        except ValueError:
            pass
    if data_fim:
        from datetime import datetime as dt, timedelta as td
        try:
            fim = dt.fromisoformat(data_fim) + td(days=1)
            query = query.filter(Nfe.data_emissao < fim)
        except ValueError:
            pass

    total = query.count()
    offset = (page - 1) * page_size
    notas = query.order_by(Nfe.data_emissao.desc()).offset(offset).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "notas": [
        {"id": n.id, "chave": n.chave_acesso, "numero": n.numero_nota,
         "data_emissao": n.data_emissao.isoformat() if n.data_emissao else None,
         "emitente": n.emitente.nome if n.emitente else None,
         "valor_total": _to_float(n.valor_total) if n.valor_total else 0,
         "status": n.status_autorizacao, "origem": n.origem or "sefaz",
         "protocolo": n.protocolo or "",
         "manifestacao": n.manifestacao_destinatario}
        for n in notas
    ]}

@app.post("/api/reconciliacao/executar")
async def api_executar_reconciliacao():
    """Dispara a reconciliação de todas as NF-e."""
    try:
        stats = executar_reconciliacao()
        return {"status": "ok", "estatisticas": stats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.post("/api/teste/gerar-1000")
async def api_gerar_1000(session: Session = Depends(get_session)):
    """Gera 1000 NF-e sintéticas para teste de volume."""
    import time
    inicio = time.time()
    stats = popular_nfe_sinteticas(session, 1000)
    tempo = time.time() - inicio
    return {"status": "ok", "estatisticas": stats, "tempo_segundos": round(tempo, 2)}


@app.post("/api/reconciliacao/popular-pedidos")
async def api_popular_pedidos():
    """Cria pedidos de compra de demonstração para testar a reconciliação."""
    try:
        resultado = popular_pedidos_demo()
        return {"status": "ok", "resultado": resultado}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.get("/api/reconciliacoes")
async def api_listar_reconciliacoes(session: Session = Depends(get_session)):
    """Lista todas as reconciliacoes."""
    recs = session.query(Reconciliacao).all()
    return {"total": len(recs), "reconciliacoes": [
        {
            "id": r.id, "status": r.status, "tipo_match": r.tipo_match,
            "matched_by": r.matched_by,
            "nfe_chave": r.nfe.chave_acesso if r.nfe else None,
            "nfe_numero": r.nfe.numero_nota if r.nfe else None,
            "nfe_valor": _to_float(r.nfe.valor_total) if r.nfe and r.nfe.valor_total else 0,
            "pedido_numero": r.pedido.numero if r.pedido else None,
            "pedido_valor": _to_float(r.pedido.valor_total) if r.pedido and r.pedido.valor_total else 0,
            "divergencias": r.divergencias,
            "data_match": r.data_match.isoformat() if r.data_match else None,
        }
        for r in recs
    ]}


@app.post("/api/lancamentos/executar")
async def api_executar_lancamentos():
    """Gera lançamentos contábeis para NF-e reconciliadas."""
    try:
        stats = executar_lancamentos()
        return {"status": "ok", "estatisticas": stats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.get("/api/lancamentos")
async def api_listar_lancamentos(session: Session = Depends(get_session)):
    """Lista todos os lançamentos contábeis."""
    lans = session.query(LancamentoContabil).order_by(LancamentoContabil.data_lancamento.desc()).all()
    return {"total": len(lans), "lançamentos": [
        {
            "id": l.id,
            "nfe_numero": l.nfe.numero_nota if l.nfe else None,
            "data": l.data_lancamento.isoformat() if l.data_lancamento else None,
            "débito": l.conta_debito_codigo,
            "crédito": l.conta_credito_codigo,
            "valor": _to_float(l.valor) if l.valor else 0,
            "historico": l.historico,
            "estornado": l.estornado,
        }
        for l in lans
    ]}

@app.get("/api/dashboard")
async def api_dashboard(session: Session = Depends(get_session)):
    try:
        from sqlalchemy import func
        total_notas = session.query(func.count(Nfe.id)).scalar() or 0
        notas_pendentes = session.query(func.count(Reconciliacao.id)).filter(
            Reconciliacao.status == "pending"
        ).scalar() or 0
        notas_match = session.query(func.count(Reconciliacao.id)).filter(
            Reconciliacao.status == "matched"
        ).scalar() or 0
        notas_divergent = session.query(func.count(Reconciliacao.id)).filter(
            Reconciliacao.status == "divergent"
        ).scalar() or 0
        valor_total = session.query(func.coalesce(func.sum(Nfe.valor_total), 0)).scalar() or 0
        notas_canceladas = session.query(func.count(Nfe.id)).filter(
            Nfe.status_autorizacao == "cancelada"
        ).scalar() or 0
    except Exception:
        total_notas = notas_pendentes = notas_match = notas_divergent = notas_canceladas = 0
        valor_total = 0
    return {
        "total_notas": total_notas, "notas_pendentes": notas_pendentes,
        "notas_reconciliadas": notas_match, "notas_divergentes": notas_divergent,
        "notas_canceladas": notas_canceladas, "valor_total": _to_float(valor_total),
    }


@app.post("/api/importacao/executar")
async def api_executar_importacao():
    try:
        stats = executar_importacao()
        return {"status": "ok", "estatisticas": stats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.get("/api/notas/{chave}")
async def api_detalhe_nfe(chave: str, session: Session = Depends(get_session)):
    if not _validar_chave(chave):
        raise HTTPException(status_code=400, detail="Chave de acesso inválida")
    nfe = session.query(Nfe).filter_by(chave_acesso=chave).first()
    if not nfe:
        raise HTTPException(status_code=404, detail="NF-e não encontrada")
    return {
        "id": nfe.id, "chave": nfe.chave_acesso, "numero": nfe.numero_nota,
        "serie": nfe.serie, "modelo": nfe.modelo,
        "data_emissao": nfe.data_emissao.isoformat() if nfe.data_emissao else None,
        "natureza_operacao": nfe.natureza_operacao,
        "valor_total": _to_float(nfe.valor_total) if nfe.valor_total else 0,
        "status": nfe.status_autorizacao, "nsu": nfe.nsu,
        "emitente": {"cnpj": nfe.emitente.cnpj_cpf, "nome": nfe.emitente.nome} if nfe.emitente else None,
        "destinatario": {"cnpj": nfe.destinatario.cnpj_cpf, "nome": nfe.destinatario.nome} if nfe.destinatario else None,
        "itens": [
            {"numero": i.numero_item, "codigo": i.codigo_produto, "descricao": i.descricao,
             "ncm": i.ncm, "cfop": i.cfop, "quantidade": _to_float(i.quantidade) if i.quantidade else 0,
             "valor_unitario": _to_float(i.valor_unitario) if i.valor_unitario else 0,
             "valor_total": _to_float(i.valor_total) if i.valor_total else 0,
             "vicms": _to_float(i.vicms) if i.vicms else 0,
             "vibscbs": _to_float(i.vibscbs) if i.vibscbs else 0}
            for i in nfe.itens
        ],
        "eventos": [
            {"tipo": e.tipo_evento, "data": e.data_evento.isoformat() if e.data_evento else None,
             "protocolo": e.protocolo, "status": e.status}
            for e in nfe.eventos
        ],
        "reconciliacoes": [
            {"status": r.status, "tipo_match": r.tipo_match, "matched_by": r.matched_by}
            for r in nfe.reconciliacoes
        ],
        "lançamentos": [
            {"data": l.data_lancamento.isoformat() if l.data_lancamento else None,
             "débito": l.conta_debito_codigo, "crédito": l.conta_credito_codigo,
             "valor": _to_float(l.valor) if l.valor else 0, "estornado": l.estornado}
            for l in nfe.lancamentos
        ],
    }


@app.get("/api/apuracao/{ano}/{mes}")
async def api_apuracao_mensal(
    ano: int = Path(..., ge=2000, le=2100, description="Ano (ex.: 2026)"),
    mes: int = Path(..., ge=1, le=12, description="Mês (1-12)"),
    session: Session = Depends(get_session),
):
    """Apura impostos do mês: créditos (entradas), débitos (saídas) e saldo a recolher."""
    try:
        resultado = apurar_mes_dict(session, ano, mes)
        return {"status": "ok", **resultado}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro na apuração: {e}")
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.post("/api/pedidos/gerar")
async def api_gerar_pedidos():
    """Gera pedidos de compra simulados para as NF-e existentes (three-way matching)."""
    try:
        resultado = gerar_pedidos_para_notas()
        return {"status": "ok", "estatisticas": resultado}
    except Exception as e:
        logger.error(f"Erro ao gerar pedidos: {e}")
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.post("/api/manifestacao/executar")
async def api_manifestacao_lote():
    """Manifesta em lote as NF-e pendentes (ciência da emissão e confirmação)."""
    try:
        resultado = executar_manifestacao_automatica()
        return {"status": "ok", **resultado}
    except Exception as e:
        logger.error(f"Erro na manifestação: {e}")
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.get("/api/manifestacao/pendentes")
async def api_manifestacao_pendentes(session: Session = Depends(get_session)):
    """Lista NF-e pendentes de manifestação, separadas por prioridade."""
    try:
        resultado = identificar_notas_pendentes(session)
        return {
            "status": "ok",
            "urgente_ciencia": resultado["urgente_ciencia"],
            "pendente_ciencia": resultado["pendente_ciencia"],
            "fora_prazo_ciencia": resultado["fora_prazo_ciencia"],
            "pendente_confirmacao": resultado["pendente_confirmacao"],
            "total_urgente": len(resultado["urgente_ciencia"]),
            "total_fora_prazo": len(resultado["fora_prazo_ciencia"]),
            "total_pendente_confirmacao": len(resultado["pendente_confirmacao"]),
        }
    except Exception as e:
        logger.error(f"Erro ao listar pendentes: {e}")
        return JSONResponse(status_code=500, content={"status": "erro", "mensagem": str(e)})


@app.get("/api/crossover/{chave}")
async def api_crossover(chave: str, session: Session = Depends(get_session)):
    if not _validar_chave(chave):
        raise HTTPException(status_code=400, detail="Chave de acesso inválida")
    nfe = session.query(Nfe).filter_by(chave_acesso=chave).first()
    if not nfe:
        raise HTTPException(status_code=404, detail="NF-e não encontrada")
    rec = nfe.reconciliacoes[0] if nfe.reconciliacoes else None
    return {
        "nfe": {"chave": nfe.chave_acesso, "numero": nfe.numero_nota, "valor": _to_float(nfe.valor_total)},
        "pedido": {"numero": rec.pedido.numero, "valor": _to_float(rec.pedido.valor_total)} if rec and rec.pedido else None,
        "recebimento": {"data": rec.recebimento.data_recebimento.isoformat()} if rec and rec.recebimento else None,
        "reconciliacao": {"status": rec.status, "tipo": rec.tipo_match, "divergencias": rec.divergencias} if rec else None,
        "lançamentos": [
            {"débito": l.conta_debito_codigo, "crédito": l.conta_credito_codigo, "valor": _to_float(l.valor)}
            for l in nfe.lancamentos
        ],
    }
