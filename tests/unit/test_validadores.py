"""Testes unitários dos validadores fiscais e contábeis (TDD).

Cobrem:
- Validação de CFOP contra tabela oficial
- Validação de NCM (formato e compatibilidade CFOP x NCM)
- Validação de CNPJ com dígito verificador
- Validação de CPF com dígito verificador
- Validação de chave de acesso com DV módulo 11
- Validação de protocolo (15-17 dígitos)
- Validação de CST/CSOSN
- Validação de partida dobrada
- Validação de valor total da NF-e
- Validação de alíquotas IBS/CBS (Reforma Tributária)
- Validação de período ECD
- Validação de prazo de entrega ECD
- Validação de obrigatoriedade ECD
- Validação de prazo de manifestação do destinatário
- Máscara de CNPJ e chave (LGPD)

Referências legais:
- NT 2023.002 (leiaute NF-e 4.00)
- MOC 7.0 (Manual de Orientação do Contribuinte)
- TIPI 2024 (Decreto 11.158/2022)
- Lei 6.404/76 art. 177 (partida dobrada)
- EC 132/2023 (Reforma Tributária)
- IN RFB 2.055/2022 (SPED ECD)
- Ajuste SINIEF 07/10 (manifestação do destinatário)
"""
import pytest
from decimal import Decimal
from datetime import date

from src.fiscal.validadores import (
    validar_cfop, validar_cfop_compatibilidade, is_cfop_servico, is_cfop_devolucao,
    is_cfop_ativo, is_cfop_consumo, categoria_contabil_cfop,
    validar_ncm, validar_cfop_ncm,
    validar_cnpj, validar_cpf, validar_chave_acesso_dv, validar_protocolo,
    validar_cst_icms, validar_csosn, validar_cst_pis_cofins,
    validar_partida_dobrada, validar_valor_total_nfe,
    get_aliquota_ibscbs, validar_data_emissao, validar_periodo_ecd,
    calcular_prazo_entrega_ecd, validar_obrigatoriedade_ecd,
    validar_prazo_manifestacao, mascara_cnpj, mascara_chave,
)


class TestValidacaoCFOP:
    """Testes de validação de CFOP (Ajuste SINIEF 07/05)."""

    def test_cfop_valido_1102(self):
        assert validar_cfop("1102") is True

    def test_cfop_valido_1933_servico_issqn(self):
        assert validar_cfop("1933") is True

    def test_cfop_valido_1551(self):
        assert validar_cfop("1551") is True

    def test_cfop_invalido_inexistente(self):
        assert validar_cfop("9999") is False

    def test_cfop_invalido_curto(self):
        assert validar_cfop("110") is False

    def test_cfop_invalido_letras(self):
        assert validar_cfop("ABCD") is False

    def test_cfop_vazio(self):
        assert validar_cfop("") is False

    def test_cfop_none(self):
        assert validar_cfop(None) is False

    def test_cfop_compatibilidade_entrada(self):
        assert validar_cfop_compatibilidade("1102", "0") is True

    def test_cfop_compatibilidade_saida(self):
        assert validar_cfop_compatibilidade("5102", "1") is True

    def test_cfop_incompativel_entrada_com_saida(self):
        # CFOP de saída (5xxx) em nota de entrada (tipo=0) é inválido
        assert validar_cfop_compatibilidade("5102", "0") is False

    def test_cfop_incompativel_saida_com_entrada(self):
        # CFOP de entrada (1xxx) em nota de saída (tipo=1) é inválido
        assert validar_cfop_compatibilidade("1102", "1") is False

    def test_is_cfop_servico_issqn(self):
        assert is_cfop_servico("1933") is True

    def test_is_cfop_servico_false(self):
        assert is_cfop_servico("1102") is False

    def test_is_cfop_devolucao(self):
        assert is_cfop_devolucao("1202") is True

    def test_is_cfop_devolucao_false(self):
        assert is_cfop_devolucao("1102") is False

    def test_is_cfop_ativo(self):
        assert is_cfop_ativo("1551") is True

    def test_is_cfop_consumo(self):
        assert is_cfop_consumo("1103") is True

    def test_categoria_contabil_estoque(self):
        assert categoria_contabil_cfop("1102") == "estoque"
        assert categoria_contabil_cfop("5102") == "estoque"

    def test_categoria_contabil_ativo(self):
        assert categoria_contabil_cfop("1551") == "ativo"

    def test_categoria_contabil_consumo(self):
        assert categoria_contabil_cfop("1103") == "consumo"

    def test_categoria_contabil_servico(self):
        assert categoria_contabil_cfop("1933") == "servico"

    def test_categoria_contabil_devolucao(self):
        assert categoria_contabil_cfop("1202") == "devolucao"
        assert categoria_contabil_cfop("5202") == "devolucao"

    def test_categoria_contabil_generico(self):
        assert categoria_contabil_cfop("9999") == "generico"
        assert categoria_contabil_cfop("") == "generico"


class TestValidacaoNCM:
    """Testes de validação de NCM (TIPI 2024)."""

    def test_ncm_valido_8_digitos(self):
        assert validar_ncm("11010010") is True

    def test_ncm_servico_00(self):
        assert validar_ncm("00") is True

    def test_ncm_invalido_7_digitos(self):
        assert validar_ncm("1101001") is False

    def test_ncm_invalido_letras(self):
        assert validar_ncm("1101001A") is False

    def test_ncm_vazio(self):
        assert validar_ncm("") is False

    def test_ncm_none(self):
        assert validar_ncm(None) is False

    def test_cfop_ncm_servico_compativel(self):
        assert validar_cfop_ncm("1933", "00") is True

    def test_cfop_ncm_servico_incompativel(self):
        # CFOP de serviço com NCM de mercadoria é inválido
        assert validar_cfop_ncm("1933", "11010010") is False

    def test_cfop_ncm_mercadoria_compativel(self):
        assert validar_cfop_ncm("1102", "11010010") is True

    def test_cfop_ncm_mercadoria_incompativel(self):
        # CFOP de mercadoria com NCM "00" é inválido
        assert validar_cfop_ncm("1102", "00") is False


class TestValidacaoCNPJ:
    """Testes de validação de CNPJ com dígito verificador (módulo 11)."""

    def test_cnpj_valido(self):
        # CNPJ válido real: 11.444.777/0001-61
        assert validar_cnpj("11444777000161") is True

    def test_cnpj_valido_formatado(self):
        assert validar_cnpj("11.444.777/0001-61") is True

    def test_cnpj_invalido_dv_errado(self):
        assert validar_cnpj("11222333000145") is False

    def test_cnpj_invalido_curto(self):
        assert validar_cnpj("1122233300014") is False

    def test_cnpj_invalido_todos_iguais(self):
        assert validar_cnpj("11111111111111") is False

    def test_cnpj_vazio(self):
        assert validar_cnpj("") is False

    def test_cnpj_letras(self):
        assert validar_cnpj("11.222.333/0001-AB") is False


class TestValidacaoCPF:
    """Testes de validação de CPF com dígito verificador."""

    def test_cpf_valido(self):
        # CPF válido de teste: 111.444.777-35
        assert validar_cpf("11144477735") is True

    def test_cpf_invalido_dv_errado(self):
        assert validar_cpf("11144477736") is False

    def test_cpf_invalido_todos_iguais(self):
        assert validar_cpf("11111111111") is False

    def test_cpf_curto(self):
        assert validar_cpf("111444777") is False


class TestValidacaoChaveAcesso:
    """Testes de validação de chave de acesso NF-e (44 dígitos, DV módulo 11)."""

    def test_chave_valida_44_digitos(self):
        # UF=35 (SP), ano=2020, mes=08, modelo=55, série=1, número=1
        base = (
            "35" + "2008" + "12345678000190" + "55" + "001"
            + "000000001" + "1" + "00000001"
        )  # 43 dígitos sem DV
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = 0
        for i in range(43):
            soma += int(base[42 - i]) * pesos[i % 8]
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        chave_valida = base + str(dv)
        assert validar_chave_acesso_dv(chave_valida) is True

    def test_chave_invalida_dv_errado(self):
        # Chave com DV propositalmente errado
        chave = "35200812345678000190550010000000011000000099"
        assert validar_chave_acesso_dv(chave) is False

    def test_chave_invalida_curta(self):
        assert validar_chave_acesso_dv("35200812345678000190") is False

    def test_chave_invalida_uf(self):
        # UF 99 não existe
        chave = "99200812345678000190550010000000011000000001"
        assert validar_chave_acesso_dv(chave) is False

    def test_chave_invalida_mes(self):
        # Mês 13 não existe (dígitos 4-5)
        chave = "35201312345678000190550010000000011000000001"
        assert validar_chave_acesso_dv(chave) is False

    def test_chave_vazia(self):
        assert validar_chave_acesso_dv("") is False

    def test_chave_letras(self):
        assert validar_chave_acesso_dv("3520081234567800019055001000000001100000000A") is False

    def test_chave_com_caractere_extra_e_rejeitada(self):
        chave = "A35200812345678000190550010000000011000000000"
        assert validar_chave_acesso_dv(chave) is False


class TestValidacaoProtocolo:
    """Testes de validação de protocolo de autorização (15-17 dígitos)."""

    def test_protocolo_valido_15_digitos(self):
        assert validar_protocolo("350260000000123") is True

    def test_protocolo_valido_17_digitos(self):
        assert validar_protocolo("13526000000123456") is True

    def test_protocolo_invalido_curto(self):
        assert validar_protocolo("1234567890") is False

    def test_protocolo_invalido_16_digitos(self):
        assert validar_protocolo("1352600000001234") is False

    def test_protocolo_invalido_letras(self):
        assert validar_protocolo("35026000000012A") is False

    def test_protocolo_vazio(self):
        assert validar_protocolo("") is False


class TestValidacaoCST:
    """Testes de validação de CST/CSOSN (Ajuste SINIEF 04/04)."""

    def test_cst_icms_valido_00(self):
        assert validar_cst_icms("00") is True

    def test_cst_icms_valido_40(self):
        assert validar_cst_icms("40") is True

    def test_cst_icms_invalido(self):
        assert validar_cst_icms("99") is False

    def test_csosn_valido_101(self):
        assert validar_csosn("101") is True

    def test_csosn_invalido(self):
        assert validar_csosn("999") is False

    def test_cst_pis_cofins_valido_01(self):
        assert validar_cst_pis_cofins("01") is True

    def test_cst_pis_cofins_valido_99(self):
        assert validar_cst_pis_cofins("99") is True

    def test_cst_pis_cofins_invalido(self):
        assert validar_cst_pis_cofins("88") is False


class TestPartidaDobrada:
    """Testes de validação de partida dobrada (Lei 6.404/76 art. 177)."""

    def test_partida_dobrada_valida(self):
        class MockLanc:
            def __init__(self, debito, credito, valor, historico="teste", estornado=False):
                self.conta_debito_codigo = debito
                self.conta_credito_codigo = credito
                self.valor = Decimal(str(valor))
                self.historico = historico
                self.estornado = estornado

        lancamentos = [
            MockLanc("1.1.3.01", "2.1.01", 1000.00, "Compra"),
            MockLanc("2.2.01", "2.1.01", 180.00, "ICMS"),
        ]
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"] is True
        assert resultado["soma_debitos"] == Decimal("1180.00")
        assert resultado["soma_creditos"] == Decimal("1180.00")

    def test_partida_dobrada_sem_debito(self):
        class MockLanc:
            def __init__(self, debito, credito, valor, historico="teste", estornado=False):
                self.conta_debito_codigo = debito
                self.conta_credito_codigo = credito
                self.valor = Decimal(str(valor))
                self.historico = historico
                self.estornado = estornado

        lancamentos = [MockLanc(None, "2.1.01", 1000.00, "Sem débito")]
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"] is False
        assert "sem conta de débito" in resultado["erros"][0]

    def test_partida_dobrada_sem_credito(self):
        class MockLanc:
            def __init__(self, debito, credito, valor, historico="teste", estornado=False):
                self.conta_debito_codigo = debito
                self.conta_credito_codigo = credito
                self.valor = Decimal(str(valor))
                self.historico = historico
                self.estornado = estornado

        lancamentos = [MockLanc("1.1.3.01", None, 1000.00, "Sem crédito")]
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"] is False
        assert "sem conta de crédito" in resultado["erros"][0]

    def test_partida_dobrada_valor_zero(self):
        class MockLanc:
            def __init__(self, debito, credito, valor, historico="teste", estornado=False):
                self.conta_debito_codigo = debito
                self.conta_credito_codigo = credito
                self.valor = Decimal(str(valor))
                self.historico = historico
                self.estornado = estornado

        lancamentos = [MockLanc("1.1.3.01", "2.1.01", 0, "Valor zero")]
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"] is False
        assert "valor <= 0" in resultado["erros"][0]

    def test_partida_dobrada_ignora_estornados(self):
        class MockLanc:
            def __init__(self, debito, credito, valor, historico="teste", estornado=False):
                self.conta_debito_codigo = debito
                self.conta_credito_codigo = credito
                self.valor = Decimal(str(valor))
                self.historico = historico
                self.estornado = estornado

        lancamentos = [
            MockLanc("1.1.3.01", "2.1.01", 1000.00, "Original"),
            MockLanc("2.1.01", "1.1.3.01", 1000.00, "Estorno", estornado=False),  # estorno conta
            MockLanc("1.1.3.01", "2.1.01", 500.00, "Estornado", estornado=True),  # ignorado
        ]
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"] is True
        assert resultado["soma_debitos"] == Decimal("2000.00")


class TestValorTotalNFe:
    """Testes de validação de valor total da NF-e."""

    def test_valor_total_simples(self):
        assert validar_valor_total_nfe(Decimal("1000"), Decimal("1000")) is True

    def test_valor_total_com_frete(self):
        assert validar_valor_total_nfe(
            Decimal("1150"), Decimal("1000"),
            valor_frete=Decimal("150")
        ) is True

    def test_valor_total_com_desconto(self):
        assert validar_valor_total_nfe(
            Decimal("900"), Decimal("1000"),
            valor_desconto=Decimal("100")
        ) is True

    def test_valor_total_inconsistente(self):
        assert validar_valor_total_nfe(Decimal("1000"), Decimal("950")) is False

    def test_valor_total_tolerancia_01(self):
        # Diferença de 0.01 é aceita (arredondamento)
        assert validar_valor_total_nfe(Decimal("1000.00"), Decimal("1000.01")) is True

    def test_valor_total_negativo_e_rejeitado(self):
        assert validar_valor_total_nfe(Decimal("1000"), Decimal("1000"), valor_frete=Decimal("-1")) is False


class TestIBSCBS:
    """Testes de alíquotas IBS/CBS (EC 132/2023, LC 214/2025)."""

    def test_aliquota_2026_fase_educativa(self):
        aliquota = get_aliquota_ibscbs(2026)
        assert aliquota["fase"] == "educativa"
        assert aliquota["recolher"] is False

    def test_aliquota_2027_exige_parametrizacao_vigente(self):
        aliquota = get_aliquota_ibscbs(2027)
        assert aliquota["fase"] == "parametrizacao_pendente"
        assert aliquota["recolher"] is None
        assert aliquota["cbs"] is None

    def test_aliquota_2033_nao_e_inventada(self):
        aliquota = get_aliquota_ibscbs(2033)
        assert aliquota["fase"] == "parametrizacao_pendente"
        assert aliquota["ibs"] is None

    def test_aliquota_cbs_2026(self):
        aliquota = get_aliquota_ibscbs(2026)
        assert aliquota["cbs"] == Decimal("0.90")

    def test_aliquota_ibs_2026(self):
        aliquota = get_aliquota_ibscbs(2026)
        assert aliquota["ibs"] == Decimal("0.10")


class TestPeriodoECD:
    """Testes de validação de período ECD (IN RFB 2.055/2022)."""

    def test_periodo_valido(self):
        valido, msg = validar_periodo_ecd(date(2026, 1, 1), date(2026, 12, 31))
        assert valido is True

    def test_periodo_invalido_inicio_maior_fim(self):
        valido, msg = validar_periodo_ecd(date(2026, 12, 31), date(2026, 1, 1))
        assert valido is False
        assert "posterior" in msg

    def test_periodo_invalido_maior_366(self):
        valido, msg = validar_periodo_ecd(date(2025, 1, 1), date(2026, 12, 31))
        assert valido is False
        assert "366" in msg

    def test_periodo_1_dia_valido(self):
        valido, msg = validar_periodo_ecd(date(2026, 7, 15), date(2026, 7, 15))
        assert valido is True

    def test_prazo_entrega_ecd_2025(self):
        # ECD de 2025: prazo último dia útil de junho de 2026
        prazo = calcular_prazo_entrega_ecd(2025)
        assert prazo.year == 2026
        assert prazo.month == 6
        assert prazo.weekday() < 5  # dia útil

    def test_prazo_entrega_ecd_2026(self):
        prazo = calcular_prazo_entrega_ecd(2026)
        assert prazo.year == 2027
        assert prazo.month == 6


class TestObrigatoriedadeECD:
    """Testes de obrigatoriedade de ECD (IN RFB 2.003/2021)."""

    def test_lucro_real_obrigatorio(self):
        assert validar_obrigatoriedade_ecd("lucro_real", 1_000_000) is True

    def test_lucro_presumido_alto_faturamento(self):
        assert validar_obrigatoriedade_ecd("lucro_presumido", 5_000_000) is True

    def test_lucro_presumido_baixo_faturamento(self):
        assert validar_obrigatoriedade_ecd("lucro_presumido", 1_000_000) is False

    def test_simples_nacional_nao_obrigatorio(self):
        assert validar_obrigatoriedade_ecd("simples_nacional", 5_000_000) is False


class TestManifestacaoDestinatario:
    """Testes de prazo de manifestação do destinatário (Ajuste SINIEF 07/10)."""

    def test_manifestacao_dentro_prazo(self):
        assert validar_prazo_manifestacao(
            date(2026, 1, 1), date(2026, 6, 1)  # 151 dias
        ) is True

    def test_manifestacao_fora_prazo(self):
        assert validar_prazo_manifestacao(
            date(2026, 1, 1), date(2026, 7, 1)  # 181 dias
        ) is False

    def test_manifestacao_mesmo_dia(self):
        assert validar_prazo_manifestacao(
            date(2026, 1, 1), date(2026, 1, 1)
        ) is True

    def test_ciencia_emissao_deve_ocorrer_em_ate_10_dias(self):
        assert validar_prazo_manifestacao(
            date(2026, 1, 1), date(2026, 1, 12), "ciencia_emissao"
        ) is False

    def test_evento_desconhecido_e_rejeitado(self):
        assert validar_prazo_manifestacao(
            date(2026, 1, 1), date(2026, 1, 2), "evento_inexistente"
        ) is False


class TestMascaraLGPD:
    """Testes de máscara de dados sensíveis (LGPD art. 5)."""

    def test_mascara_cnpj(self):
        assert mascara_cnpj("11222333000144") == "11.222.333/****-**"

    def test_mascara_cnpj_formatado(self):
        assert mascara_cnpj("11.222.333/0001-44") == "11.222.333/****-**"

    def test_mascara_cnpj_curto(self):
        # CNPJ com menos de 14 dígitos retorna parcial
        resultado = mascara_cnpj("12345678")
        assert "****" in resultado

    def test_mascara_chave(self):
        resultado = mascara_chave("35200812345678000190550010000000011000000001")
        assert resultado.endswith("...")
        assert len(resultado) == 23  # 20 chars + "..."

    def test_mascara_chave_curta(self):
        resultado = mascara_chave("352008")
        assert resultado == "352008..."


class TestDataEmissao:
    """Testes de validação de data de emissão."""

    def test_data_emissao_valida(self):
        assert validar_data_emissao(date(2026, 7, 15), date(2026, 7, 30)) is True

    def test_data_emissao_futura(self):
        assert validar_data_emissao(date(2030, 1, 1), date(2026, 7, 30)) is False

    def test_data_emissao_anterior_1950(self):
        assert validar_data_emissao(date(1949, 1, 1)) is False

    def test_data_emissao_none(self):
        assert validar_data_emissao(None) is False
