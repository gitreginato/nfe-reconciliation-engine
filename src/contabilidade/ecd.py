"""Exportacao para formato ECD (Escrituração Contábil Digital).

Gera arquivo ECD no layout do SPED Contábil (Leiaute 9, IN RFB 2.003/2021):
- Registro 0000: Abertura do arquivo
- Registro I001: Abertura do bloco I
- Registro I012: Livros contábeis
- Registro I030: Identificacao do empresario
- Registro I050: Plano de contas
- Registro I051: Plano de contas referencial
- Registro I150: Saldos periodicos
- Registro I200: Lancamentos contabeis
- Registro I250: Detalhes dos lancamentos
- Registro I990: Encerramento do bloco I
- Registro J001: Abertura do bloco J (demonstracoes)
- Registro J050: Demonstracao do resultado
- Registro J100: Balanco patrimonial
- Registro J990: Encerramento do bloco J
- Registro K001: Abertura do bloco K (livro caixa/razao)
- Registro K030: Livro caixa
- Registro K100: Livro razao
- Registro K990: Encerramento do bloco K
- Registro 9001: Encerramento do arquivo
- Registro 9900: Total de registros por tipo
- Registro 9990: Encerramento do bloco 9
- Registro 9999: Total de registros do arquivo
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session

from src.persistencia.models import Nfe, LancamentoContabil, PlanoContas

logger = logging.getLogger(__name__)


class ExportadorECD:
    """Gera arquivo ECD no formato do SPED Contábil."""

    def __init__(self, session: Session):
        self.session = session

    def _fmt_cnpj(self, cnpj: str) -> str:
        """Remove formatação do CNPJ, deixando 14 dígitos (zeros a esquerda)."""
        limpo = (cnpj or "").replace(".", "").replace("/", "").replace("-", "")
        return limpo.zfill(14)[:14]

    def _fmt_data(self, d) -> str:
        """Formata data como DDMMAAAA."""
        if hasattr(d, "strftime"):
            return d.strftime("%d%m%Y")
        return ""

    def _fmt_valor(self, v) -> str:
        """Formata valor com 2 casas decimais usando Decimal (sem perda de precisão)."""
        if not isinstance(v, Decimal):
            v = Decimal(str(v))
        return f"{v:.2f}".replace(".", ",")

    def exportar(self, data_inicio: date, data_fim: date, cnpj: str, nome_empresa: str) -> str:
        """Gera o arquivo ECD completo.

        Args:
            data_inicio: Data inicial do periodo
            data_fim: Data final do periodo
            cnpj: CNPJ da empresa
            nome_empresa: Nome da empresa

        Returns:
            String com o conteudo do arquivo ECD
        """
        # Validacao de input
        if not data_inicio or not data_fim:
            raise ValueError("Data inicial e final são obrigatórias")
        if data_inicio > data_fim:
            raise ValueError("Data inicial não pode ser posterior a data final")
        if (data_fim - data_inicio).days > 366:
            raise ValueError("Período não pode exceder 366 dias (1 ano calendário)")
        if not cnpj:
            raise ValueError("CNPJ obrigatório")
        if not nome_empresa:
            raise ValueError("Nome da empresa obrigatório")

        logger.info(f"Exportação ECD: período {data_inicio} a {data_fim}, CNPJ {self._fmt_cnpj(cnpj)[:8]}***")

        cnpj_fmt = self._fmt_cnpj(cnpj)
        data_ini_fmt = self._fmt_data(data_inicio)
        data_fim_fmt = self._fmt_data(data_fim)
        lancamentos = self.session.query(LancamentoContabil).filter(
            LancamentoContabil.data_lancamento >= data_inicio,
            LancamentoContabil.data_lancamento <= data_fim,
        ).order_by(LancamentoContabil.data_lancamento, LancamentoContabil.id).all()
        linhas = []

        # Registro 0000: Abertura
        linhas.append("|0000|ECD|{}|{}|{}|{}|A|1|".format(
            data_ini_fmt, data_fim_fmt, cnpj_fmt, nome_empresa[:80]
        ))

        # Registro I001: Abertura do bloco I, 1 indica movimento
        linhas.append(f"|I001|{1 if lancamentos else 0}|")

        # Registro I012: Livros contábeis (Lei 6.404/76 art. 1.184)
        # Livro Razão (cod 0) e Livro Diário (cod 1)
        linhas.append(f"|I012|{1 if lancamentos else 0}|")
        linhas.append("|I012|0|Livro Razao|")
        linhas.append("|I012|1|Livro Diario|")

        # Registro I030: Identificação do empresário
        linhas.append("|I030|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            cnpj_fmt,  # CNPJ
            nome_empresa[:80],  # Nome empresarial
            "",  # CNAE
            "",  # Endereco
            "",  # Número
            "",  # Complemento
            "",  # Bairro
            "",  # Municipio
            "",  # UF
            "",  # CEP
            "",  # Telefone
            "",  # Email
            "1",  # Indicador de situacao: normal
        ))

        # Registro I050: Plano de contas
        contas = self.session.query(PlanoContas).order_by(PlanoContas.codigo_referencial).all()
        for conta in contas:
            linhas.append("|I050|{}|{}|{}|{}|".format(
                self._fmt_data(data_inicio),
                conta.codigo_referencial or "",
                conta.nome or "",
                "A",  # As contas cadastradas pelo gerador aceitam lançamentos
            ))
            # Registro I051: Mapeamento para plano de contas referencial RFB
            # (codigo_referencial já segue o padrão da Receita)
            linhas.append("|I051|{}|{}|{}|".format(
                self._fmt_data(data_inicio),
                conta.codigo_referencial or "",
                conta.codigo_referencial or "",
            ))

        # Registro I150: saldos periódicos do período
        if lancamentos:
            linhas.append(f"|I150|{data_ini_fmt}|{data_fim_fmt}|")

        # Registro I200: Lançamentos contábeis
        for lanc in lancamentos:
            # Registro I200: Cabeçalho do lançamento
            linhas.append("|I200|{}|{}|{}|".format(
                self._fmt_data(lanc.data_lancamento),
                f"{lanc.numero_documento or ''}",
                lanc.historico or "",
            ))

            # Registro I250: Detalhe do lançamento (partida dobrada)
            # Debito
            if lanc.conta_debito_codigo:
                linhas.append("|I250|{}|{}|D|{}|".format(
                    lanc.conta_debito_codigo,
                    self._fmt_valor(lanc.valor),
                    "",
                ))
            # Credito
            if lanc.conta_credito_codigo:
                linhas.append("|I250|{}|{}|C|{}|".format(
                    lanc.conta_credito_codigo,
                    self._fmt_valor(lanc.valor),
                    "",
                ))

        # Registro I990: Encerramento do bloco I (conta antes de adicionar I990)
        total_registros_i = sum(1 for l in linhas if l.startswith("|I"))
        linhas.append("|I990|{}|".format(total_registros_i))

        # ===== Bloco J: Demonstrações contábeis =====
        # Registro J001: Abertura do bloco J
        linhas.append(f"|J001|{1 if lancamentos else 0}|")

        # Registro J005: Demonstrações contábeis (DRE e Balanço)
        # Cod 1 = Balanço patrimonial, Cod 2 = DRE
        if lancamentos:
            # DRE
            linhas.append("|J005|{}|2|Demonstracao do Resultado do Exercicio|".format(
                self._fmt_data(data_fim)
            ))
            # Calcular totais para DRE
            total_receitas = Decimal("0")
            total_despesas = Decimal("0")
            for lanc in lancamentos:
                if not lanc.estornado:
                    if lanc.conta_debito_codigo and lanc.conta_debito_codigo.startswith("3."):
                        total_despesas += Decimal(str(lanc.valor))
                    if lanc.conta_credito_codigo and lanc.conta_credito_codigo.startswith("3."):
                        total_receitas += Decimal(str(lanc.valor))

            # J100: Linhas da demonstração (DRE simplificado)
            if total_receitas > 0:
                linhas.append("|J100|01|Receita Operacional Bruta|{}|".format(
                    self._fmt_valor(total_receitas)
                ))
            if total_despesas > 0:
                linhas.append("|J100|02|Despesas Operacionais|{}|".format(
                    self._fmt_valor(total_despesas)
                ))
            resultado = total_receitas - total_despesas
            linhas.append("|J100|03|Resultado do Exercicio|{}|".format(
                self._fmt_valor(resultado)
            ))

            # Balanço patrimonial
            total_ativo = Decimal("0")
            total_passivo = Decimal("0")
            for lanc in lancamentos:
                if not lanc.estornado:
                    if lanc.conta_debito_codigo and lanc.conta_debito_codigo.startswith("1."):
                        total_ativo += Decimal(str(lanc.valor))
                    if lanc.conta_credito_codigo and (lanc.conta_credito_codigo.startswith("2.") or lanc.conta_credito_codigo.startswith("1.")):
                        if lanc.conta_credito_codigo.startswith("2."):
                            total_passivo += Decimal(str(lanc.valor))

            linhas.append("|J005|{}|1|Balanco Patrimonial|".format(
                self._fmt_data(data_fim)
            ))
            if total_ativo > 0:
                linhas.append("|J100|01|Ativo Total|{}|".format(
                    self._fmt_valor(total_ativo)
                ))
            if total_passivo > 0:
                linhas.append("|J100|02|Passivo Total|{}|".format(
                    self._fmt_valor(total_passivo)
                ))

        # Registro J990: Encerramento do bloco J
        total_registros_j = sum(1 for l in linhas if l.startswith("|J"))
        linhas.append("|J990|{}|".format(total_registros_j))

        # ===== Bloco K: Livro Caixa / Livro Razão auxiliar =====
        # Registro K001: Abertura do bloco K
        linhas.append(f"|K001|{1 if lancamentos else 0}|")

        # Registro K030: Livro caixa (simplificado, sem detalhamento de conta)
        if lancamentos:
            linhas.append("|K030|{}|{}|".format(data_ini_fmt, data_fim_fmt))
            # K100: Livro razão auxiliar (um por conta)
            contas_usadas = set()
            for lanc in lancamentos:
                if lanc.conta_debito_codigo:
                    contas_usadas.add(lanc.conta_debito_codigo)
                if lanc.conta_credito_codigo:
                    contas_usadas.add(lanc.conta_credito_codigo)
            for codigo in sorted(contas_usadas):
                linhas.append("|K100|{}|".format(codigo))

        # Registro K990: Encerramento do bloco K
        total_registros_k = sum(1 for l in linhas if l.startswith("|K"))
        linhas.append("|K990|{}|".format(total_registros_k))

        # Registro 9001: Encerramento do arquivo
        linhas.append("|9001|0|")

        # Registro 9900: Total de registros por tipo
        num_i012 = sum(1 for l in linhas if l.startswith("|I012"))
        num_i050 = sum(1 for l in linhas if l.startswith("|I050"))
        num_i051 = sum(1 for l in linhas if l.startswith("|I051"))
        num_i200 = sum(1 for l in linhas if l.startswith("|I200"))
        num_i250 = sum(1 for l in linhas if l.startswith("|I250"))
        num_j005 = sum(1 for l in linhas if l.startswith("|J005"))
        num_j100 = sum(1 for l in linhas if l.startswith("|J100"))
        num_k100 = sum(1 for l in linhas if l.startswith("|K100"))
        linhas.append("|9900|0000|1|")
        linhas.append("|9900|I001|1|")
        linhas.append("|9900|I012|{}|".format(num_i012))
        linhas.append("|9900|I030|1|")
        linhas.append("|9900|I050|{}|".format(num_i050))
        linhas.append("|9900|I051|{}|".format(num_i051))
        linhas.append("|9900|I990|1|")
        linhas.append("|9900|J001|1|")
        linhas.append("|9900|J005|{}|".format(num_j005))
        linhas.append("|9900|J100|{}|".format(num_j100))
        linhas.append("|9900|J990|1|")
        linhas.append("|9900|K001|1|")
        linhas.append("|9900|K100|{}|".format(num_k100))
        linhas.append("|9900|K990|1|")
        linhas.append("|9900|I200|{}|".format(num_i200))
        linhas.append("|9900|I250|{}|".format(num_i250))
        linhas.append("|9900|9001|1|")
        # Conta quantos 9900 já existem + este + o final
        num_9900 = sum(1 for l in linhas if l.startswith("|9900")) + 2
        linhas.append("|9900|9900|{}|".format(num_9900))
        linhas.append("|9900|9990|1|")

        # Registro 9990: Encerramento do bloco 9 (conta antes de adicionar 9990)
        total_9 = sum(1 for l in linhas if l.startswith("|9"))
        linhas.append("|9990|{}|".format(total_9))

        # Registro 9999: Total de registros do arquivo (inclui o próprio 9999)
        total_final = len(linhas) + 1
        linhas.append("|9999|{}|".format(total_final))

        return "\n".join(linhas) + "\n"


def executar_exportacao_ecd(data_inicio: date, data_fim: date, cnpj: str, nome: str) -> str:
    """Função de conveniência para exportar ECD."""
    from src.persistencia.models import Session
    s = Session()
    try:
        exportador = ExportadorECD(s)
        return exportador.exportar(data_inicio, data_fim, cnpj, nome)
    finally:
        s.close()
