"""Importador DF-e - busca notas na SEFAZ (ou mock) e persiste no banco.

Fluxo:
1. Consulta NFeDistribuicaoDFe por NSU
2. Para cada documento: manifesta (ciencia da emissao)
3. Baixa XML completo
4. Faz parse e persiste no PostgreSQL
5. Atualiza ultimo NSU em dfe_importacao
"""
import logging
from datetime import datetime
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.persistencia.models import (
    Nfe, Participante, NfeItem, NfeEvento, DfeImportacao, get_session, Session as SessionClass
)
from src.importador.rate_limit import RateLimiter, retry_sefaz
from src.importador.validador_xml import validar_xml_nfe
from src.fiscal.validadores import (
    get_aliquota_ibscbs,
    validar_chave_acesso_dv,
    validar_cfop,
    validar_ncm,
    validar_cfop_ncm,
    validar_valor_total_nfe,
)

logger = logging.getLogger(__name__)


class ImportadorDFe:
    """Importa documentos fiscais da SEFAZ (ou mock SEFAZ)."""

    def __init__(self, session: Session | None = None):
        self.session = session or SessionClass()
        self._own_session = session is None
        if settings.mock_sefaz:
            self.base_url = settings.sefaz_mock_url
        else:
            self.base_url = None  # producao usa erpbrasil.edoc (fase futura)
        self.client = httpx.Client(timeout=settings.sefaz_timeout)
        self.rate_limiter = RateLimiter(max_calls=settings.sefaz_rate_limit, window_seconds=1.0)

    def close(self):
        self.client.close()
        if self._own_session:
            self.session.close()

    @staticmethod
    def _validar_protocolo(protocolo: str) -> str:
        """Valida protocolo de autorização com 15 ou 17 dígitos numéricos."""
        if not protocolo:
            return ""
        protocolo = str(protocolo).strip()
        if protocolo.isdigit() and len(protocolo) in (15, 17):
            return protocolo
        logger.warning(f"Protocolo com formato inválido: {protocolo[:10]}...")
        return ""

    @staticmethod
    def _parse_data_autorizacao(data_str: str, fallback: datetime) -> datetime:
        """Converte data_autorizacao string para datetime, com fallback seguro."""
        if not data_str:
            return fallback
        try:
            return datetime.fromisoformat(data_str)
        except (ValueError, TypeError):
            logger.warning(f"Data autorização inválida: {data_str}, usando fallback")
            return fallback

    def _get_ultimo_nsu(self) -> int:
        """Recupera o último NSU consultado do banco."""
        registro = self.session.query(DfeImportacao).order_by(
            DfeImportacao.id.desc()
        ).first()
        return registro.ultimo_nsu if registro else 0

    def _salvar_nsu(self, nsu: int, total: int, status: str, erro: str = None):
        """Salva o NSU consultado no banco."""
        self.session.add(DfeImportacao(
            cnpj_consultado=settings.cnpj_consultado,
            ultimo_nsu=nsu,
            total_documentos=total,
            data_ultima_consulta=datetime.now(),
            status=status,
            erro_mensagem=erro,
        ))
        self.session.commit()

    def consultar_dfe(self, ultimo_nsu: int = None) -> dict:
        """Consulta NFeDistribuicaoDFe no mock SEFAZ."""
        if ultimo_nsu is None:
            ultimo_nsu = self._get_ultimo_nsu()

        if settings.mock_sefaz:
            self.rate_limiter.acquire("sefaz_dfe")
            return self._consultar_dfe_retry(ultimo_nsu)
        else:
            raise NotImplementedError("Importação via SEFAZ real será implementada com erpbrasil.edoc")

    @retry_sefaz
    def _consultar_dfe_retry(self, ultimo_nsu: int) -> dict:
        resp = self.client.post(
            f"{self.base_url}/nfe-distribuicao",
            json={"ultimo_nsu": ultimo_nsu, "cnpj": settings.cnpj_consultado},
        )
        resp.raise_for_status()
        return resp.json()

    def manifestar(self, chave: str) -> dict:
        """Envia ciência da emissão para a SEFAZ."""
        if settings.mock_sefaz:
            self.rate_limiter.acquire("sefaz_manifestacao")
            return self._manifestar_retry(chave)
        else:
            raise NotImplementedError("Manifestação via SEFAZ real será implementada com erpbrasil.edoc")

    @retry_sefaz
    def _manifestar_retry(self, chave: str) -> dict:
        resp = self.client.post(
            f"{self.base_url}/nfe-manifestação",
            json={"chave": chave, "tipo_evento": "ciencia_emissao"},
        )
        resp.raise_for_status()
        return resp.json()

    def baixar_xml(self, chave: str) -> str:
        """Baixa o XML completo da nota."""
        if settings.mock_sefaz:
            self.rate_limiter.acquire("sefaz_xml")
            return self._baixar_xml_retry(chave)
        else:
            raise NotImplementedError("Download via SEFAZ real será implementada com erpbrasil.edoc")

    @retry_sefaz
    def _baixar_xml_retry(self, chave: str) -> str:
        resp = self.client.get(f"{self.base_url}/nfe/{chave}/xml")
        resp.raise_for_status()
        return resp.text

    def buscar_resumo(self, chave: str) -> dict:
        """Busca o resumo de uma nota específica."""
        if settings.mock_sefaz:
            self.rate_limiter.acquire("sefaz_resumo")
            return self._buscar_resumo_retry(chave)
        else:
            raise NotImplementedError("Busca via SEFAZ real será implementada com erpbrasil.edoc")

    @retry_sefaz
    def _buscar_resumo_retry(self, chave: str) -> dict:
        resp = self.client.get(f"{self.base_url}/nfe/{chave}")
        resp.raise_for_status()
        return resp.json()

    def _get_or_create_participante(self, cnpj: str, nome: str) -> Participante:
        """Busca ou cria um participante no banco."""
        part = self.session.query(Participante).filter_by(cnpj_cpf=cnpj).first()
        if not part:
            part = Participante(cnpj_cpf=cnpj, nome=nome)
            self.session.add(part)
            self.session.flush()
        return part

    def persistir_nfe(self, resumo: dict, xml: str) -> Nfe | None:
        """Persiste uma NF-e no banco a partir do resumo e XML."""
        chave = resumo["chave"]

        if not validar_chave_acesso_dv(chave):
            raise ValueError("Chave de acesso NF-e inválida")

        itens_resumo = resumo.get("itens", [])
        for item_data in itens_resumo:
            cfop = item_data.get("cfop", "")
            ncm = item_data.get("ncm", "")
            if not validar_cfop(cfop):
                raise ValueError(f"CFOP inválido: {cfop}")
            if not validar_ncm(ncm) or not validar_cfop_ncm(cfop, ncm):
                raise ValueError(f"NCM incompatível com CFOP: {ncm}/{cfop}")

        soma_itens = sum(
            (Decimal(str(item.get("valor_total", 0))) for item in itens_resumo),
            Decimal("0"),
        )
        if not validar_valor_total_nfe(
            Decimal(str(resumo["valor_total"])),
            soma_itens,
            valor_frete=resumo.get("valor_frete"),
            valor_seguro=resumo.get("valor_seguro"),
            valor_outros=resumo.get("valor_outros"),
            valor_desconto=resumo.get("valor_desconto"),
        ):
            raise ValueError("Valor total da NF-e não confere com seus itens")

        # Idempotência: não reimportar nota que já existe
        existente = self.session.query(Nfe).filter_by(chave_acesso=chave).first()
        if existente:
            logger.info(f"NF-e {chave[:20]}... já importada, pulando")
            return None

        emitente = self._get_or_create_participante(
            resumo["emitente_cnpj"], resumo["emitente_nome"]
        )
        destinatario = self._get_or_create_participante(
            settings.cnpj_consultado, settings.destinatario_nome
        )

        data_emissao = datetime.fromisoformat(resumo["data_emissao"])

        nfe = Nfe(
            chave_acesso=chave,
            numero_nota=resumo.get("numero", int(chave[-8:])),
            serie=resumo.get("serie", 1),
            modelo="55",
            data_emissao=data_emissao,
            natureza_operacao=resumo.get("natureza", ""),
            tipo_operacao="0" if resumo.get("tipo") == "entrada" else "1",
            valor_total=Decimal(str(resumo["valor_total"])),
            valor_produtos=Decimal(str(resumo.get("valor_produtos") or resumo["valor_total"])),
            valor_desconto=Decimal(str(resumo.get("valor_desconto", 0))) if resumo.get("valor_desconto") else None,
            valor_frete=Decimal(str(resumo.get("valor_frete", 0))) if resumo.get("valor_frete") else None,
            valor_seguro=Decimal(str(resumo.get("valor_seguro", 0))) if resumo.get("valor_seguro") else None,
            valor_outros=Decimal(str(resumo.get("valor_outros", 0))) if resumo.get("valor_outros") else None,
            status_autorizacao="cancelada" if resumo.get("cancelada") else "autorizada",
            origem="sefaz",
            xml_original=xml,
            protocolo=self._validar_protocolo(resumo.get("protocolo_autorizacao", "")),
            data_autorizacao=self._parse_data_autorizacao(resumo.get("data_autorizacao"), data_emissao),
            manifestacao_destinatario="ciencia_emissao",
            nsu=resumo.get("nsu"),
            emitente_id=emitente.id,
            destinatario_id=destinatario.id,
        )
        self.session.add(nfe)
        self.session.flush()

        # Persistir itens
        for i, item_data in enumerate(resumo.get("itens", []), 1):
            item = NfeItem(
                nfe_id=nfe.id,
                numero_item=i,
                codigo_produto=item_data.get("codigo", ""),
                descricao=item_data.get("descricao", ""),
                ncm=item_data.get("ncm", ""),
                cfop=item_data.get("cfop", ""),
                unidade="UN",
                quantidade=Decimal(str(item_data.get("quantidade", 0))),
                valor_unitario=Decimal(str(item_data.get("valor_unitario", 0))),
                valor_total=Decimal(str(item_data.get("valor_total", 0))),
                valor_desconto=Decimal(str(item_data.get("valor_desconto", 0))) if item_data.get("valor_desconto") else None,
                valor_frete=Decimal(str(item_data.get("valor_frete", 0))) if item_data.get("valor_frete") else None,
                vicms=Decimal(str(item_data.get("vicms", 0))) if item_data.get("vicms") else None,
                vicms_st=Decimal(str(item_data.get("vicms_st", 0))) if item_data.get("vicms_st") else None,
                vbc_icms_st=Decimal(str(item_data.get("vbc_icms_st", 0))) if item_data.get("vbc_icms_st") else None,
                vipi=Decimal(str(item_data.get("vipi", 0))) if item_data.get("vipi") else None,
                vpis=Decimal(str(item_data.get("vpis", 0))) if item_data.get("vpis") else None,
                vcofins=Decimal(str(item_data.get("vcofins", 0))) if item_data.get("vcofins") else None,
            )
            self.session.add(item)

        # Se tem IBS/CBS, aplicar somente parametrização com fonte vigente.
        if resumo.get("tem_ibscbs"):
            aliquota = get_aliquota_ibscbs(data_emissao.year)
            if aliquota["ibs"] is not None and aliquota["cbs"] is not None:
                percentual_total = aliquota["ibs"] + aliquota["cbs"]
                for item in self.session.query(NfeItem).filter_by(nfe_id=nfe.id).all():
                    item.vbc_ibscbs = item.valor_total
                    item.aliquota_ibscbs = percentual_total
                    item.vibscbs = (
                        item.valor_total * percentual_total / Decimal("100")
                    ).quantize(Decimal("0.01"))
            else:
                logger.warning(
                    "IBS/CBS sem parametrização vigente para o ano %s; nota %s importada sem cálculo",
                    data_emissao.year,
                    chave[:20] + "...",
                )

        # Registrar evento de manifestação
        evento = NfeEvento(
            nfe_id=nfe.id,
            tipo_evento="ciencia_emissao",
            data_evento=datetime.now(),
            sequencia=1,
            status="registrado",
        )
        self.session.add(evento)

        self.session.commit()
        logger.info(f"NF-e {chave[:20]}... importada com sucesso (NSU={resumo.get('nsu')})")
        return nfe

    def importar_tudo(self) -> dict:
        """Executa importação completa: consulta, manifesta, baixa XML, persiste."""
        stats = {"consultadas": 0, "importadas": 0, "duplicadas": 0, "erros": 0, "canceladas": 0}

        try:
            resultado = self.consultar_dfe()
            documentos = resultado.get("documentos", [])
            stats["consultadas"] = len(documentos)

            if not documentos:
                logger.info("Nenhum documento novo para importar")
                self._salvar_nsu(self._get_ultimo_nsu(), 0, "sem_documentos")
                return stats

            for doc in documentos:
                try:
                    chave = doc["chave"]

                    # Manifestar para liberar o XML
                    self.manifestar(chave)

                    # Baixar XML completo
                    xml = self.baixar_xml(chave)

                    # Validar XML antes de persistir
                    validacao = validar_xml_nfe(xml)
                    if not validacao.valido:
                        logger.warning(f"XML inválido para {chave[:20]}...: {validacao.erros}")
                        stats["erros"] += 1
                        continue

                    # Buscar resumo completo (com itens)
                    resumo = self.buscar_resumo(chave)

                    # Persistir
                    nfe = self.persistir_nfe(resumo, xml)
                    if nfe:
                        stats["importadas"] += 1
                        if resumo.get("cancelada"):
                            stats["canceladas"] += 1
                    else:
                        stats["duplicadas"] += 1

                except Exception as e:
                    self.session.rollback()
                    logger.error(f"Erro ao importar nota {doc.get('chave', '?')[:20]}...: {e}")
                    stats["erros"] += 1

            # Salvar NSU final
            self._salvar_nsu(resultado.get("ultimo_nsu", 0), stats["importadas"], "concluido")

        except Exception as e:
            logger.error(f"Erro na importação: {e}")
            self._salvar_nsu(self._get_ultimo_nsu(), 0, "erro", str(e))
            stats["erros"] += 1

        return stats


def executar_importacao() -> dict:
    """Função de conveniência para executar importação (chamada pela API)."""
    importador = ImportadorDFe()
    try:
        return importador.importar_tudo()
    except Exception:
        importador.session.rollback()
        raise
    finally:
        importador.close()
