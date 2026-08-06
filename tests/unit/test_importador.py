"""Testes unitários do importador DF-e e rate limiter.

Cobre:
- ImportadorDFe: inicialização e configuração de mock SEFAZ
- RateLimiter: limita chamadas por janela, bloqueia ao exceder, reseta após janela
- executar_importacao: função de conveniência existe e é chamável

Não realiza chamadas reais à SEFAZ (usa mock=True e mocks para o servidor).
"""
import time
from unittest.mock import patch, MagicMock

import pytest

from src.importador.dfe import ImportadorDFe, executar_importacao
from src.importador.rate_limit import RateLimiter


class FakeRedis:
    """Redis em memória que simula sorted sets (sliding window do rate limiter).

    Cada key mapeia para uma lista de [score, member] ordenada por score.
    """

    def __init__(self):
        self._data: dict[str, list[list]] = {}
        self._expires: dict[str, float] = {}

    def _key_alive(self, key: str) -> bool:
        exp = self._expires.get(key)
        if exp is not None and time.time() > exp:
            self._data.pop(key, None)
            self._expires.pop(key, None)
            return False
        return key in self._data

    def zremrangebyscore(self, key, min_score, max_score):
        if not self._key_alive(key):
            return 0
        before = len(self._data[key])
        self._data[key] = [
            entry for entry in self._data[key]
            if not (min_score <= entry[1] <= max_score)
        ]
        return before - len(self._data[key])

    def zcard(self, key):
        if not self._key_alive(key):
            return 0
        return len(self._data[key])

    def zadd(self, key, mapping):
        if key not in self._data:
            self._data[key] = []
        for member, score in mapping.items():
            self._data[key].append([member, float(score)])
        self._data[key].sort(key=lambda e: e[1])
        return len(self._data[key])

    def expire(self, key, seconds):
        self._expires[key] = time.time() + seconds
        return True

    def zrange(self, key, start, end, withscores=False):
        if not self._key_alive(key):
            return []
        entries = self._data[key]
        if start < 0:
            start = max(len(entries) + start, 0)
        if end < 0:
            end = len(entries) + end
        result = []
        for i in range(start, min(end + 1, len(entries))):
            if withscores:
                result.append([entries[i][0], entries[i][1]])
            else:
                result.append(entries[i][0])
        return result


@pytest.fixture
def fake_redis():
    """Fornece um FakeRedis e patcha get_redis para usá-lo."""
    redis = FakeRedis()
    with patch("src.importador.rate_limit.get_redis", return_value=redis):
        yield redis


@pytest.fixture
def importador(fake_redis):
    """ImportadorDFe com Redis mockado e cliente HTTP mockado."""
    with patch("src.importador.dfe.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        imp = ImportadorDFe(session=MagicMock())
        imp.client = mock_client
        yield imp
        imp.close()


class TestImportadorDFe:
    """Testes de inicialização e configuração do ImportadorDFe."""

    def test_inicializacao_cria_rate_limiter_e_client(self, importador):
        assert importador.client is not None
        assert isinstance(importador.rate_limiter, RateLimiter)
        assert importador.rate_limiter.max_calls > 0

    def test_config_mock_sefaz_define_base_url(self, importador):
        """Com mock_sefaz=True, base_url aponta para a URL do mock."""
        from src.config import settings
        assert settings.mock_sefaz is True
        assert importador.base_url == settings.sefaz_mock_url

    def test_close_fecha_client_e_session(self, importador):
        importador._own_session = False  # session externa não deve ser fechada
        importador.close()
        importador.client.close.assert_called_once()

    def test_validar_protocolo_15_digitos(self):
        assert ImportadorDFe._validar_protocolo("123456789012345") == "123456789012345"

    def test_validar_protocolo_invalido_retorna_vazio(self):
        assert ImportadorDFe._validar_protocolo("abc") == ""
        assert ImportadorDFe._validar_protocolo("") == ""

    def test_parse_data_autorizacao_valida(self):
        from datetime import datetime
        fallback = datetime(2026, 1, 1)
        result = ImportadorDFe._parse_data_autorizacao("2026-07-15T10:00:00", fallback)
        assert result == datetime(2026, 7, 15, 10, 0, 0)

    def test_parse_data_autorizacao_invalida_usa_fallback(self):
        from datetime import datetime
        fallback = datetime(2026, 1, 1)
        result = ImportadorDFe._parse_data_autorizacao("invalida", fallback)
        assert result == fallback


class TestRateLimiter:
    """Testes do RateLimiter (sliding window via Redis mockado)."""

    def test_limita_chamadas_por_janela(self, fake_redis):
        """Permite até max_calls chamadas dentro da janela sem bloquear."""
        rl = RateLimiter(max_calls=3, window_seconds=1.0, timeout=5.0)
        inicio = time.time()
        for _ in range(3):
            rl.acquire("teste_janela")
        # 3 chamadas devem ser quase instantâneas (sem bloqueio)
        assert time.time() - inicio < 0.5
        assert fake_redis.zcard("teste_janela") == 3

    def test_bloqueia_quando_excede_max_calls(self, fake_redis):
        """Ao exceder max_calls, a próxima acquire bloqueia até a janela expirar."""
        rl = RateLimiter(max_calls=2, window_seconds=0.3, timeout=5.0)
        rl.acquire("bloqueio")
        rl.acquire("bloqueio")
        # A 3ª chamada deve bloquear (janela cheia) e só liberar após expirar
        inicio = time.time()
        rl.acquire("bloqueio")
        decorrido = time.time() - inicio
        assert decorrido >= 0.2, f"Esperava bloqueio >= 0.2s, got {decorrido:.3f}s"

    def test_reseta_apos_window_seconds(self, fake_redis):
        """Após window_seconds, entradas expiram e novas chamadas são permitidas."""
        rl = RateLimiter(max_calls=2, window_seconds=0.2, timeout=5.0)
        rl.acquire("reset")
        rl.acquire("reset")
        assert fake_redis.zcard("reset") == 2
        # Espera a janela expirar
        time.sleep(0.35)
        # zremrangebyscore remove entradas expiradas na próxima acquire
        rl.acquire("reset")
        # Após reset, apenas 1 entrada na nova janela
        assert fake_redis.zcard("reset") == 1

    def test_max_calls_invalido_levanta_erro(self, fake_redis):
        with pytest.raises(ValueError):
            RateLimiter(max_calls=0)
        with pytest.raises(ValueError):
            RateLimiter(max_calls=-1)

    def test_window_seconds_invalido_levanta_erro(self, fake_redis):
        with pytest.raises(ValueError):
            RateLimiter(max_calls=3, window_seconds=0)
        with pytest.raises(ValueError):
            RateLimiter(max_calls=3, window_seconds=-1)

    def test_key_invalida_levanta_erro(self, fake_redis):
        rl = RateLimiter(max_calls=3, window_seconds=1.0)
        with pytest.raises(ValueError):
            rl.acquire("!!!")  # caracteres não alfanuméricos viram string vazia

    def test_fail_open_em_erro_redis(self, fake_redis):
        """Em caso de erro Redis, o rate limiter permite passagem (fail-open)."""
        import redis as redis_mod
        rl = RateLimiter(max_calls=3, window_seconds=1.0)
        rl.redis = MagicMock()
        rl.redis.zremrangebyscore.side_effect = redis_mod.RedisError("Redis down")
        # Não deve levantar; deve permitir passagem
        rl.acquire("fail_open")


class TestExecutarImportacao:
    """Testes da função de conveniência executar_importacao."""

    def test_funcao_existe_e_e_chamavel(self):
        assert callable(executar_importacao)

    @patch("src.importador.dfe.ImportadorDFe")
    def test_executar_importacao_cria_instancia_e_chama_importar_tudo(self, mock_cls):
        """executar_importacao instancia ImportadorDFe e chama importar_tudo."""
        instancia = MagicMock()
        instancia.importar_tudo.return_value = {"importadas": 5, "erros": 0}
        mock_cls.return_value = instancia

        resultado = executar_importacao()

        mock_cls.assert_called_once()
        instancia.importar_tudo.assert_called_once()
        assert resultado == {"importadas": 5, "erros": 0}
        instancia.close.assert_called_once()

    @patch("src.importador.dfe.ImportadorDFe")
    def test_executar_importacao_faz_rollback_em_erro(self, mock_cls):
        """Em caso de exceção, faz rollback e propaga o erro."""
        instancia = MagicMock()
        instancia.importar_tudo.side_effect = RuntimeError("falha")
        mock_cls.return_value = instancia

        with pytest.raises(RuntimeError, match="falha"):
            executar_importacao()

        instancia.session.rollback.assert_called_once()
        instancia.close.assert_called_once()


class TestPersistirNfe:
    """Testa ImportadorDFe.persistir_nfe com banco em memória."""

    @pytest.fixture
    def importador(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Patch get_session para usar banco em memória
        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        # Substitui a session manualmente
        imp.session = session
        yield imp, session
        session.close()

    def _chave_valida(self):
        """Gera chave de 44 dígitos com DV válido (módulo 11)."""
        # UF=52 (SP), ano=24, mes=06, CNPJ=11222333000144, modelo=55, serie=1, numero=1, tipo=1
        base = "52" + "2406" + "11" + "222333000144" + "55" + "001" + "000000001" + "1"
        base = base[:43].ljust(43, "0")
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = 0
        for i in range(43):
            soma += int(base[42 - i]) * pesos[i % 8]
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        return base + str(dv)

    def _resumo_valido(self, chave=None):
        if chave is None:
            chave = self._chave_valida()
        return {
            "chave": chave,
            "valor_total": "1500.00",
            "data_emissao": "2026-07-15T00:00:00",
            "emitente_cnpj": "11222333000144",
            "emitente_nome": "Distribuidora Alimentos SP Ltda",
            "tipo": "entrada",
            "natureza": "Compra de mercadorias",
            "numero": 1,
            "serie": 1,
            "nsu": "12345",
            "itens": [
                {"codigo": "001", "descricao": "Farinha 1kg", "ncm": "11010010",
                 "cfop": "1102", "valor_total": "1500.00",
                 "valor_unitario": "15.00", "quantidade": "100"},
            ],
        }

    def test_persistir_nfe_sucesso(self, importador):
        """Persiste NF-e válida no banco."""
        imp, session = importador
        resumo = self._resumo_valido()
        nfe = imp.persistir_nfe(resumo, "<xml>fake</xml>")

        assert nfe is not None
        assert nfe.chave_acesso == resumo["chave"]
        assert nfe.valor_total == 1500
        assert len(nfe.itens) == 1
        assert nfe.itens[0].cfop == "1102"

    def test_persistir_nfe_duplicada_retorna_none(self, importador):
        """NF-e já importada retorna None (idempotência)."""
        imp, session = importador
        resumo = self._resumo_valido()
        imp.persistir_nfe(resumo, "<xml>fake</xml>")
        # Segunda vez: mesma chave
        nfe2 = imp.persistir_nfe(resumo, "<xml>fake</xml>")
        assert nfe2 is None

    def test_persistir_nfe_chave_invalida_erro(self, importador):
        """Chave inválida levanta ValueError."""
        imp, session = importador
        resumo = self._resumo_valido(chave="1" * 44)  # DV provavelmente errado
        with pytest.raises(ValueError, match="Chave de acesso"):
            imp.persistir_nfe(resumo, "<xml>fake</xml>")

    def test_persistir_nfe_cfop_invalido_erro(self, importador):
        """CFOP inexistente levanta ValueError."""
        imp, session = importador
        resumo = self._resumo_valido()
        resumo["itens"][0]["cfop"] = "9999"
        with pytest.raises(ValueError, match="CFOP inválido"):
            imp.persistir_nfe(resumo, "<xml>fake</xml>")

    def test_persistir_nfe_valor_total_divergente_erro(self, importador):
        """Valor total não bate com soma dos itens."""
        imp, session = importador
        resumo = self._resumo_valido()
        resumo["valor_total"] = "999.00"  # divergente
        with pytest.raises(ValueError, match="Valor total"):
            imp.persistir_nfe(resumo, "<xml>fake</xml>")

    def test_persistir_nfe_com_ibscbs(self, importador):
        """NF-e com tem_ibscbs=True calcula IBS/CBS nos itens."""
        imp, session = importador
        resumo = self._resumo_valido()
        resumo["tem_ibscbs"] = True
        nfe = imp.persistir_nfe(resumo, "<xml>fake</xml>")

        item = nfe.itens[0]
        assert item.vbc_ibscbs is not None
        assert item.aliquota_ibscbs is not None
        assert item.vibscbs is not None
        # 2026: IBS=0.10% + CBS=0.90% = 1.00% sobre 1500 = 15.00
        assert item.vibscbs == 1500 * item.aliquota_ibscbs / 100

    def test_persistir_nfe_cancelada(self, importador):
        """NF-e marcada como cancelada fica com status_autorizacao='cancelada'."""
        imp, session = importador
        resumo = self._resumo_valido()
        resumo["cancelada"] = True
        nfe = imp.persistir_nfe(resumo, "<xml>fake</xml>")
        assert nfe.status_autorizacao == "cancelada"

    def test_persistir_nfe_cria_evento_manifestacao(self, importador):
        """Persistir NF-e cria evento de ciência da emissão."""
        imp, session = importador
        resumo = self._resumo_valido()
        nfe = imp.persistir_nfe(resumo, "<xml>fake</xml>")
        assert len(nfe.eventos) == 1
        assert nfe.eventos[0].tipo_evento == "ciencia_emissao"


class TestImportarTudo:
    """Testa ImportadorDFe.importar_tudo com mocks."""

    def test_sem_documentos(self):
        """importar_tudo com 0 documentos retorna stats vazias."""
        with patch("src.importador.dfe.Session"):
            imp = ImportadorDFe()
        imp.consultar_dfe = lambda: {"documentos": [], "ultimo_nsu": "0"}
        imp._get_ultimo_nsu = lambda: "0"
        imp._salvar_nsu = lambda *a, **kw: None
        stats = imp.importar_tudo()
        assert stats["consultadas"] == 0
        assert stats["importadas"] == 0

    def test_com_documento_valido(self):
        """importar_tudo com 1 documento válido importa 1 NF-e."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session

        # Mock da chave válida (DV módulo 11)
        base = "52" + "2406" + "11" + "222333000144" + "55" + "001" + "000000001" + "1"
        base = base[:43].ljust(43, "0")
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = 0
        for i in range(43):
            soma += int(base[42 - i]) * pesos[i % 8]
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        chave = base + str(dv)

        imp.consultar_dfe = lambda: {
            "documentos": [{"chave": chave}],
            "ultimo_nsu": "1",
        }
        imp.manifestar = lambda ch: None
        imp.baixar_xml = lambda ch: "<xml>fake</xml>"
        imp.buscar_resumo = lambda ch: {
            "chave": ch, "valor_total": "100.00",
            "data_emissao": "2026-07-15T00:00:00",
            "emitente_cnpj": "11222333000144",
            "emitente_nome": "Fornecedor",
            "tipo": "entrada",
            "itens": [{"codigo": "001", "descricao": "Item",
                       "ncm": "11010010", "cfop": "1102",
                       "valor_total": "100.00",
                       "valor_unitario": "10.00", "quantidade": "10"}],
        }
        imp._salvar_nsu = lambda *a, **kw: None

        # Mock validação XML
        with patch("src.importador.dfe.validar_xml_nfe") as mock_val:
            mock_val.return_value = MagicMock(valido=True, erros=[])
            stats = imp.importar_tudo()

        assert stats["consultadas"] == 1
        assert stats["importadas"] == 1
        session.close()


class TestImportadorMetodosMock:
    """Testa métodos de consulta/manifestar/baixar/buscar com mock SEFAZ."""

    @pytest.fixture
    def importador_mock(self):
        """Importador com client HTTP mockado."""
        with patch("src.importador.dfe.Session"):
            imp = ImportadorDFe()
        imp.client = MagicMock()
        imp._get_ultimo_nsu = lambda: 0
        imp._salvar_nsu = lambda *a, **kw: None
        yield imp
        imp.close()

    def test_consultar_dfe_mock(self, importador_mock):
        """consultar_dfe chama o mock SEFAZ e retorna JSON."""
        imp = importador_mock
        imp.client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"documentos": [], "ultimo_nsu": "1"},
            raise_for_status=lambda: None,
        )
        result = imp.consultar_dfe(0)
        assert "documentos" in result

    def test_consultar_dfe_sem_mock_erro(self):
        """consultar_dfe sem mock SEFAZ levanta NotImplementedError."""
        with patch("src.importador.dfe.Session"), \
             patch("src.importador.dfe.settings") as mock_settings:
            mock_settings.mock_sefaz = False
            mock_settings.sefaz_timeout = 30
            mock_settings.sefaz_rate_limit = 3
            imp = ImportadorDFe()
            with pytest.raises(NotImplementedError):
                imp.consultar_dfe(0)
            imp.close()

    def test_manifestar_mock(self, importador_mock):
        """manifestar chama o endpoint de manifestação."""
        imp = importador_mock
        imp.client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "ok"},
            raise_for_status=lambda: None,
        )
        result = imp.manifestar("1" * 44)
        assert result["status"] == "ok"

    def test_manifestar_sem_mock_erro(self):
        """manifestar sem mock SEFAZ levanta NotImplementedError."""
        with patch("src.importador.dfe.Session"), \
             patch("src.importador.dfe.settings") as mock_settings:
            mock_settings.mock_sefaz = False
            mock_settings.sefaz_timeout = 30
            mock_settings.sefaz_rate_limit = 3
            imp = ImportadorDFe()
            with pytest.raises(NotImplementedError):
                imp.manifestar("1" * 44)
            imp.close()

    def test_baixar_xml_mock(self, importador_mock):
        """baixar_xml retorna o XML da nota."""
        imp = importador_mock
        imp.client.get.return_value = MagicMock(
            status_code=200,
            text="<xml>fake</xml>",
            raise_for_status=lambda: None,
        )
        xml = imp.baixar_xml("1" * 44)
        assert "<xml>" in xml

    def test_baixar_xml_sem_mock_erro(self):
        """baixar_xml sem mock SEFAZ levanta NotImplementedError."""
        with patch("src.importador.dfe.Session"), \
             patch("src.importador.dfe.settings") as mock_settings:
            mock_settings.mock_sefaz = False
            mock_settings.sefaz_timeout = 30
            mock_settings.sefaz_rate_limit = 3
            imp = ImportadorDFe()
            with pytest.raises(NotImplementedError):
                imp.baixar_xml("1" * 44)
            imp.close()

    def test_buscar_resumo_mock(self, importador_mock):
        """buscar_resumo retorna o resumo da nota."""
        imp = importador_mock
        imp.client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"chave": "1" * 44, "valor_total": "100.00"},
            raise_for_status=lambda: None,
        )
        resumo = imp.buscar_resumo("1" * 44)
        assert resumo["chave"] == "1" * 44

    def test_buscar_resumo_sem_mock_erro(self):
        """buscar_resumo sem mock SEFAZ levanta NotImplementedError."""
        with patch("src.importador.dfe.Session"), \
             patch("src.importador.dfe.settings") as mock_settings:
            mock_settings.mock_sefaz = False
            mock_settings.sefaz_timeout = 30
            mock_settings.sefaz_rate_limit = 3
            imp = ImportadorDFe()
            with pytest.raises(NotImplementedError):
                imp.buscar_resumo("1" * 44)
            imp.close()

    def test_get_ultimo_nsu_sem_registro(self):
        """_get_ultimo_nsu retorna 0 quando não há registros."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session
        assert imp._get_ultimo_nsu() == 0
        session.close()

    def test_salvar_nsu(self):
        """_salvar_nsu persiste o registro de importação."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base, DfeImportacao

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session
        imp._salvar_nsu(5, 3, "concluido")
        registros = session.query(DfeImportacao).all()
        assert len(registros) == 1
        assert registros[0].ultimo_nsu == 5
        assert registros[0].total_documentos == 3
        session.close()

    def test_get_ultimo_nsu_com_registro(self):
        """_get_ultimo_nsu retorna o NSU do último registro."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base, DfeImportacao

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session
        imp._salvar_nsu(10, 5, "concluido")
        imp._salvar_nsu(20, 8, "concluido")
        assert imp._get_ultimo_nsu() == 20
        session.close()

    def test_validar_protocolo_vazio(self):
        """Protocolo vazio retorna string vazia."""
        assert ImportadorDFe._validar_protocolo("") == ""

    def test_validar_protocolo_curto(self):
        """Protocolo com menos de 15 dígitos retorna vazio."""
        assert ImportadorDFe._validar_protocolo("123") == ""

    def test_validar_protocolo_com_letras(self):
        """Protocolo com letras retorna vazio."""
        assert ImportadorDFe._validar_protocolo("12345678901234X") == ""

    def test_validar_protocolo_valido_15(self):
        """Protocolo com 15 dígitos é válido."""
        assert ImportadorDFe._validar_protocolo("123456789012345") == "123456789012345"

    def test_validar_protocolo_valido_17(self):
        """Protocolo com 17 dígitos é válido."""
        assert ImportadorDFe._validar_protocolo("12345678901234567") == "12345678901234567"

    def test_parse_data_autorizacao_vazia(self):
        """Data vazia retorna fallback."""
        from datetime import datetime
        fallback = datetime(2026, 7, 15)
        assert ImportadorDFe._parse_data_autorizacao("", fallback) == fallback

    def test_parse_data_autorizacao_none(self):
        """Data None retorna fallback."""
        from datetime import datetime
        fallback = datetime(2026, 7, 15)
        assert ImportadorDFe._parse_data_autorizacao(None, fallback) == fallback

    def test_parse_data_autorizacao_invalida(self):
        """Data inválida retorna fallback."""
        from datetime import datetime
        fallback = datetime(2026, 7, 15)
        assert ImportadorDFe._parse_data_autorizacao("invalida", fallback) == fallback

    def test_parse_data_autorizacao_valida(self):
        """Data ISO válida é parseada corretamente."""
        from datetime import datetime
        fallback = datetime(2026, 7, 15)
        result = ImportadorDFe._parse_data_autorizacao("2026-07-15T10:30:00", fallback)
        assert result == datetime(2026, 7, 15, 10, 30, 0)

    def test_close_fecha_client_e_session(self):
        """close() fecha client e session quando própria."""
        with patch("src.importador.dfe.Session"):
            imp = ImportadorDFe()
        imp.client = MagicMock()
        imp.session = MagicMock()
        imp._own_session = True
        imp.close()
        imp.client.close.assert_called_once()
        imp.session.close.assert_called_once()

    def test_get_or_create_participante_existente(self):
        """_get_or_create_participante retorna existente sem duplicar."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from src.persistencia.models import Base, Participante

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Criar participante
        session.add(Participante(cnpj_cpf="11222333000144", nome="Fornecedor"))
        session.flush()

        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session
        part = imp._get_or_create_participante("11222333000144", "Outro Nome")
        assert part.nome == "Fornecedor"  # não sobrescreve
        assert session.query(Participante).count() == 1
        session.close()
