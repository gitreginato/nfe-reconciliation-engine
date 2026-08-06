"""Registry de vigência legislativa para regulatory drift.

Mantém registro versionado de legislação com datas de vigência.
Permite detectar quando leis mudam e quais controles precisam atualização.

Regulatory drift: quando a legislação muda (nova IN, MOC atualizado,
Reforma Tributária avança), o gate detecta automaticamente que controles
precisam ser revisados, sem precisar reescrever o gate.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class LegislationEntry:
    """Entrada de legislação com vigência."""
    id: str
    name: str
    article: str = ""
    url: str = ""
    vigencia_inicio: date = None
    vigencia_fim: date = None  # None = vigente
    fonte: str = ""
    category: str = ""  # contabil, fiscal, legislativo, tecnico
    supersedes: str = ""  # id da legislação que esta substitui

    def is_vigente(self, ref: date = None) -> bool:
        ref = ref or date.today()
        if self.vigencia_inicio and ref < self.vigencia_inicio:
            return False
        if self.vigencia_fim and ref > self.vigencia_fim:
            return False
        return True

    def days_until_expiry(self, ref: date = None) -> int | None:
        if not self.vigencia_fim:
            return None
        ref = ref or date.today()
        return (self.vigencia_fim - ref).days

    def is_expiring_soon(self, days: int = 90, ref: date = None) -> bool:
        d = self.days_until_expiry(ref)
        return d is not None and 0 < d <= days


# Registry central de legislação
REGISTRY: list[LegislationEntry] = [
    # Contábil
    LegislationEntry(
        id="lei-6404-1976", name="Lei das S/A", article="art. 177",
        url="https://www.planalto.gov.br/ccivil_03/leis/l6404consol.htm",
        vigencia_inicio=date(1977, 1, 1), category="contabil",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="manual-ecd-9", name="Manual ECD Leiaute 9",
        url="https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd",
        vigencia_inicio=date(2026, 1, 1), category="contabil",
        fonte="SPED",
    ),
    LegislationEntry(
        id="in-rfb-2003-2021", name="IN RFB nº 2.003/2021", article="art. 5º",
        url="http://sped.rfb.gov.br/pagina/show/5727",
        vigencia_inicio=date(2022, 1, 1), category="contabil",
        fonte="Receita Federal",
    ),
    # Fiscal
    LegislationEntry(
        id="lc-87-1996", name="Lei Kandir (ICMS)",
        url="https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp87.htm",
        vigencia_inicio=date(1996, 9, 13), category="fiscal",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="decreto-7212-2010", name="Regulamento IPI",
        url="https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/decreto/d7212.htm",
        vigencia_inicio=date(2010, 8, 15), category="fiscal",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="lei-10637-2002", name="PIS não-cumulativo",
        url="https://www.planalto.gov.br/ccivil_03/leis/2002/l10637.htm",
        vigencia_inicio=date(2002, 12, 30), category="fiscal",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="lei-10833-2003", name="COFINS não-cumulativo",
        url="https://www.planalto.gov.br/ccivil_03/leis/2003/l10833.htm",
        vigencia_inicio=date(2004, 2, 1), category="fiscal",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="lc-116-2003", name="Lista de serviços (ISS)",
        url="https://www.planalto.gov.br/ccivil_03/leis/2003/lcp/lcp116.htm",
        vigencia_inicio=date(2003, 9, 1), category="fiscal",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="tipi-2024", name="Tabela de Incidência IPI (TIPI)",
        url="https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/classificacao-fiscal-de-mercadorias/tipi",
        vigencia_inicio=date(2024, 1, 1), category="fiscal",
        fonte="Receita Federal",
    ),
    # Reforma Tributária (vigência progressiva)
    LegislationEntry(
        id="ec-132-2023", name="EC nº 132/2023 (Reforma Tributária)",
        url="https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm",
        vigencia_inicio=date(2024, 1, 1), category="legislativo",
        fonte="Planalto",
    ),
    LegislationEntry(
        id="lc-214-2025", name="LC nº 214/2025 (Reforma Tributária regulamentação)",
        url="https://planalto.gov.br/ccivil_03/leis/lcp/lcp214compilado.htm",
        vigencia_inicio=date(2025, 1, 1), category="legislativo",
        fonte="Planalto",
    ),
    # NF-e
    LegislationEntry(
        id="moc-7-0", name="MOC 7.0 NF-e",
        url="https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf",
        vigencia_inicio=date(2023, 1, 1), category="tecnico",
        fonte="CONFAZ",
    ),
    LegislationEntry(
        id="nt-2023-002", name="NT 2023.002 (leiaute NF-e 4.00)",
        url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/2020/ajuste-sinief-44-20",
        vigencia_inicio=date(2023, 9, 1), category="tecnico",
        fonte="CONFAZ",
    ),
    LegislationEntry(
        id="ajuste-sinief-07-2005", name="Ajuste SINIEF 07/2005 (Manifestação)",
        article="cláusulas 15-A a 15-C",
        url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/2005/ajuste-sinief-07-05",
        vigencia_inicio=date(2005, 8, 1), category="legislativo",
        fonte="CONFAZ",
    ),
    # LGPD
    LegislationEntry(
        id="lgpd-13709-2018", name="Lei nº 13.709/2018 (LGPD)",
        url="https://www.gov.br/anpd/pt-br/centrais-de-conteudo/legislacao/lei-no-13-709-de-14-de-agosto-de-2018",
        vigencia_inicio=date(2020, 9, 18), category="legislativo",
        fonte="ANPD",
    ),
]


def get_vigente(category: str = "", ref: date = None) -> list[LegislationEntry]:
    """Retorna legislação vigente, opcionalmente filtrada por categoria."""
    ref = ref or date.today()
    result = [e for e in REGISTRY if e.is_vigente(ref)]
    if category:
        result = [e for e in result if e.category == category]
    return result


def get_expiring_soon(days: int = 90, ref: date = None) -> list[LegislationEntry]:
    """Retorna legislação que expira em breve (alerta de regulatory drift)."""
    return [e for e in REGISTRY if e.is_expiring_soon(days, ref)]


def get_superseded(ref: date = None) -> list[LegislationEntry]:
    """Retorna legislação não mais vigente (substituída)."""
    ref = ref or date.today()
    return [e for e in REGISTRY if not e.is_vigente(ref)]


def get_by_id(leg_id: str) -> LegislationEntry | None:
    """Busca entrada por ID."""
    for e in REGISTRY:
        if e.id == leg_id:
            return e
    return None


def regulatory_drift_report(ref: date = None) -> dict:
    """Gera relatório de drift regulatório.

    Retorna:
    - vigente: legislação em vigor
    - expiring: legislação expirando em <=90 dias
    - superseded: legislação substituída
    - total: total de entradas
    """
    ref = ref or date.today()
    return {
        "data_referencia": ref.isoformat(),
        "total": len(REGISTRY),
        "vigente": len(get_vigente(ref=ref)),
        "expirando_90d": len(get_expiring_soon(90, ref)),
        "substituida": len(get_superseded(ref)),
        "alertas": [
            {"id": e.id, "name": e.name, "dias_para_expirar": e.days_until_expiry(ref)}
            for e in get_expiring_soon(90, ref)
        ],
    }
