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
