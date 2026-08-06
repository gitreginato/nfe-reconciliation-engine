"""Testes do cálculo tributário determinístico."""
from decimal import Decimal
from src.fiscal.calculo import (
    calcular_icms,
    calcular_icms_st,
    calcular_ipi,
    calcular_pis_cofins,
    calcular_ibscbs,
    calcular_tributos_item,
    calcular_tributos_nfe,
)


class TestCalcularICMS:
    def test_icms_interestadual_12_por_cento(self):
        base, valor, aliq = calcular_icms(Decimal("1000.00"), "SP", "RJ")
        assert aliq == Decimal("12.00")
        assert base == Decimal("1000.00")
        assert valor == Decimal("120.00")

    def test_icms_interestadual_7_por_cento(self):
        base, valor, aliq = calcular_icms(Decimal("1000.00"), "SP", "BA")
        assert aliq == Decimal("7.00")
        assert valor == Decimal("70.00")

    def test_icms_interna_sp_18_por_cento(self):
        base, valor, aliq = calcular_icms(Decimal("1000.00"), "SP", "SP")
        assert aliq == Decimal("18.00")
        assert valor == Decimal("180.00")

    def test_icms_cst_sem_credito(self):
        base, valor, aliq = calcular_icms(Decimal("1000.00"), "SP", "RJ", cst="40")
        assert base == Decimal("0")
        assert valor == Decimal("0")
        assert aliq is None

    def test_icms_com_reducao_base(self):
        base, valor, aliq = calcular_icms(
            Decimal("1000.00"), "SP", "RJ", base_redutora=Decimal("50")
        )
        assert base == Decimal("500.00")
        assert valor == Decimal("60.00")

    def test_icms_default_interestadual(self):
        base, valor, aliq = calcular_icms(Decimal("1000.00"), "AC", "RR")
        assert aliq == Decimal("12.00")


class TestCalcularICMSST:
    def test_st_farinha_sp(self):
        base_st, valor_st = calcular_icms_st(
            Decimal("500.00"), "SP", "11010010", Decimal("18.00"), Decimal("60.00")
        )
        # base = 500 * 1.36 = 680
        assert base_st == Decimal("680.00")
        # valor = 680 * 0.18 - 60 = 122.40 - 60 = 62.40
        assert valor_st == Decimal("62.40")

    def test_st_uf_sem_tabela_retorna_zero(self):
        base_st, valor_st = calcular_icms_st(
            Decimal("500.00"), "RJ", "11010010", Decimal("18.00"), Decimal("60.00")
        )
        assert base_st == Decimal("0")
        assert valor_st == Decimal("0")

    def test_st_ncm_sem_mva_retorna_zero(self):
        base_st, valor_st = calcular_icms_st(
            Decimal("500.00"), "SP", "99999999", Decimal("18.00"), Decimal("60.00")
        )
        assert base_st == Decimal("0")
        assert valor_st == Decimal("0")


class TestCalcularIPI:
    def test_ipi_farinha_zero(self):
        valor, aliq = calcular_ipi(Decimal("1000.00"), "11010010")
        assert valor == Decimal("0")
        assert aliq == Decimal("0.00")

    def test_ipi_computador_5_por_cento(self):
        valor, aliq = calcular_ipi(Decimal("1000.00"), "84713012")
        assert aliq == Decimal("5.00")
        assert valor == Decimal("50.00")

    def test_ipi_moveis_10_por_cento(self):
        valor, aliq = calcular_ipi(Decimal("1000.00"), "94013000")
        assert aliq == Decimal("10.00")
        assert valor == Decimal("100.00")

    def test_ipi_ncm_sem_tabela(self):
        valor, aliq = calcular_ipi(Decimal("1000.00"), "99999999")
        assert valor == Decimal("0")
        assert aliq is None


class TestCalcularPISCOFINS:
    def test_cumulativo(self):
        base_p, v_pis, base_c, v_cof, a_pis, a_cof = calcular_pis_cofins(
            Decimal("1000.00"), "cumulativo"
        )
        assert a_pis == Decimal("0.65")
        assert a_cof == Decimal("3.00")
        assert v_pis == Decimal("6.50")
        assert v_cof == Decimal("30.00")

    def test_nao_cumulativo(self):
        _, v_pis, _, v_cof, a_pis, a_cof = calcular_pis_cofins(
            Decimal("1000.00"), "nao_cumulativo"
        )
        assert a_pis == Decimal("1.65")
        assert a_cof == Decimal("7.60")
        assert v_pis == Decimal("16.50")
        assert v_cof == Decimal("76.00")

    def test_cst_sem_credito(self):
        _, v_pis, _, v_cof, _, _ = calcular_pis_cofins(
            Decimal("1000.00"), "cumulativo", cst_pis="04"
        )
        assert v_pis == Decimal("0")
        assert v_cof == Decimal("0")


class TestCalcularTributosItem:
    def test_compra_normal_sp_rj(self):
        r = calcular_tributos_item(
            valor_total=Decimal("1000.00"),
            ncm="11010010",
            cfop="1102",
            uf_origem="SP",
            uf_destino="RJ",
            cst_icms="00",
            cst_pis="01",
            regime="cumulativo",
        )
        assert r.valor_icms == Decimal("120.00")
        assert r.valor_ipi == Decimal("0")
        assert r.valor_pis == Decimal("6.50")
        assert r.valor_cofins == Decimal("30.00")

    def test_compra_com_st(self):
        r = calcular_tributos_item(
            valor_total=Decimal("500.00"),
            ncm="11010010",
            cfop="1102",
            uf_origem="SP",
            uf_destino="SP",
            cst_icms="10",
            cst_pis="01",
            regime="cumulativo",
            calcular_st=True,
        )
        # ICMS interno 18%
        assert r.valor_icms == Decimal("90.00")
        # ST: base = 500 * 1.36 = 680, valor = 680*0.18 - 90 = 122.40 - 90 = 32.40
        assert r.base_icms_st == Decimal("680.00")
        assert r.valor_icms_st == Decimal("32.40")

    def test_determinismo_mesmo_resultado(self):
        args = dict(
            valor_total=Decimal("1500.00"),
            ncm="84713012",
            cfop="1102",
            uf_origem="SP",
            uf_destino="RJ",
        )
        r1 = calcular_tributos_item(**args)
        r2 = calcular_tributos_item(**args)
        assert r1.valor_icms == r2.valor_icms
        assert r1.valor_ipi == r2.valor_ipi
        assert r1.valor_pis == r2.valor_pis
        assert r1.valor_cofins == r2.valor_cofins


class TestCalcularTributosNFe:
    def test_nfe_com_3_itens(self):
        itens = [
            {"valor_total": 500, "ncm": "11010010", "cfop": "1102",
             "cst_icms": "00", "cst_pis": "01"},
            {"valor_total": 400, "ncm": "17019900", "cfop": "1102",
             "cst_icms": "00", "cst_pis": "01"},
            {"valor_total": 600, "ncm": "15121911", "cfop": "1102",
             "cst_icms": "00", "cst_pis": "01"},
        ]
        r = calcular_tributos_nfe(itens, "SP", "RJ", "cumulativo")
        assert r["totais"]["valor_produtos"] == Decimal("1500.00")
        # ICMS 12% sobre 1500 = 180
        assert r["totais"]["valor_icms"] == Decimal("180.00")
        # PIS 0.65% sobre 1500 = 9.75
        assert r["totais"]["valor_pis"] == Decimal("9.75")
        # COFINS 3% sobre 1500 = 45
        assert r["totais"]["valor_cofins"] == Decimal("45.00")
        assert len(r["detalhes"]) == 3


class TestCalcularIBSCBS:
    def test_2026_fase_educativa(self):
        """Em 2026, IBS=0.10% + CBS=0.90% = 1.00% (fase educativa, sem recolhimento)."""
        base, v_ibs, v_cbs, a_ibs, a_cbs, periodo = calcular_ibscbs(
            Decimal("1000.00"), "2026"
        )
        assert base == Decimal("1000.00")
        assert a_ibs == Decimal("0.10")
        assert a_cbs == Decimal("0.90")
        assert v_ibs == Decimal("1.00")
        assert v_cbs == Decimal("9.00")
        assert periodo == "2026"

    def test_reducao_setor_saude(self):
        """Setor saúde tem 30% de redução na alíquota."""
        _, v_ibs, v_cbs, a_ibs, a_cbs, _ = calcular_ibscbs(
            Decimal("1000.00"), "2026", setor="saude"
        )
        # 0.10% * 0.70 = 0.07
        assert a_ibs == Decimal("0.07")
        # 0.90% * 0.70 = 0.63
        assert a_cbs == Decimal("0.63")
        assert v_ibs == Decimal("0.70")
        assert v_cbs == Decimal("6.30")

    def test_cesta_basica_isenta(self):
        """Cesta básica tem 100% de redução (isenta)."""
        _, v_ibs, v_cbs, a_ibs, a_cbs, _ = calcular_ibscbs(
            Decimal("1000.00"), "2026", setor="cesta_basica"
        )
        assert v_ibs == Decimal("0.00")
        assert v_cbs == Decimal("0.00")

    def test_periodo_default_2026(self):
        """Sem especificar período, usa 2026 (atual)."""
        _, _, _, _, _, periodo = calcular_ibscbs(Decimal("1000.00"))
        assert periodo == "2026"

    def test_periodo_invalido_fallback(self):
        """Período inexistente cai no default (2026, alíquota educativa)."""
        _, _, _, _, _, periodo = calcular_ibscbs(
            Decimal("1000.00"), "9999"
        )
        assert periodo == "9999"
        # Fallback para alíquota do período atual (2026: IBS=0.10%)
        _, v_ibs, _, _, _, _ = calcular_ibscbs(Decimal("1000.00"), "9999")
        assert v_ibs == Decimal("1.00")

    def test_consistencia_com_validadores(self):
        """Alíquotas de calculo.py devem ser iguais às de validadores.py."""
        from src.fiscal.validadores import ALIQUOTAS_IBS_CBS as ALIQ_VALIDADORES
        from src.fiscal.calculo import ALIQUOTAS_IBS_CBS as ALIQ_CALCULO
        # 2026 deve ter mesma alíquota nas duas tabelas
        v = ALIQ_VALIDADORES[2026]
        c = ALIQ_CALCULO["2026"]
        assert v["ibs"] == c["ibs"]
        assert v["cbs"] == c["cbs"]


class TestTributosItemComIBSCBS:
    def test_item_com_ibscbs_2026(self):
        """Item calculado em 2026 tem IBS/CBS da fase educativa (0.10 + 0.90)."""
        r = calcular_tributos_item(
            valor_total=Decimal("1000.00"),
            ncm="11010010",
            cfop="1102",
            uf_origem="SP",
            uf_destino="RJ",
            periodo_regulatorio="2026",
        )
        # 0.10% IBS + 0.90% CBS = 1.00% = 10.00
        assert r.valor_ibscbs == Decimal("10.00")
        assert r.base_ibscbs == Decimal("1000.00")
        assert r.aliquota_ibs == Decimal("0.10")
        assert r.aliquota_cbs == Decimal("0.90")
        assert r.periodo_regulatorio == "2026"

    def test_nfe_com_ibscbs_nos_totais(self):
        """Totais da NF-e incluem IBS/CBS."""
        itens = [
            {"valor_total": 1000, "ncm": "11010010", "cfop": "1102",
             "cst_icms": "00", "cst_pis": "01", "periodo_regulatorio": "2026"},
        ]
        r = calcular_tributos_nfe(itens, "SP", "RJ", "cumulativo")
        assert r["totais"]["valor_ibscbs"] == Decimal("10.00")
        assert r["totais"]["base_ibscbs"] == Decimal("1000.00")
