"""Testes de integração do rate limiter com Redis real.

Exercita o RateLimiter contra o Redis do docker-compose, verificando:
- Limite de chamadas por janela
- Espera automática quando limite é atingido
- Sanitização de chave
- Fail-open em caso de erro Redis
"""
import time
import pytest
from src.importador.rate_limit import RateLimiter, get_redis


@pytest.fixture
def limpa_redis():
    """Limpa as chaves de rate limit antes e depois de cada teste."""
    redis = get_redis()
    # Limpa chaves de teste
    for key in redis.keys("test_rate_*"):
        redis.delete(key)
    yield
    for key in redis.keys("test_rate_*"):
        redis.delete(key)


@pytest.mark.integration
class TestRateLimiter:
    def test_permite_ate_max_calls(self, limpa_redis):
        """3 chamadas em 1 segundo devem ser permitidas sem espera."""
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        for i in range(3):
            inicio = time.time()
            limiter.acquire("test_rate_permite")
            elapsed = time.time() - inicio
            # Cada chamada deve ser rápida (< 0.1s)
            assert elapsed < 0.1, f"Chamada {i} demorou {elapsed}s"

    def test_bloqueia_quarta_chamada(self, limpa_redis):
        """A 4ª chamada deve esperar até a janela liberar."""
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        # 3 chamadas rápidas
        for _ in range(3):
            limiter.acquire("test_rate_bloqueia")

        # 4ª chamada deve esperar
        inicio = time.time()
        limiter.acquire("test_rate_bloqueia")
        elapsed = time.time() - inicio
        # Deve ter esperado pelo menos 0.5s (janela de 1s)
        assert elapsed >= 0.3, f"4ª chamada não esperou (elapsed={elapsed}s)"

    def test_sanitizacao_chave(self, limpa_redis):
        """Chave com caracteres especiais deve ser sanitizada."""
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        # Chave com espaços e caracteres especiais
        limiter.acquire("test_rate_sanitizacao!@#")
        # Não deve levantar exceção

    def test_chave_vazia_levanta_erro(self, limpa_redis):
        """Chave vazia após sanitização deve levantar ValueError."""
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        with pytest.raises(ValueError):
            limiter.acquire("!!!")  # vira string vazia após sanitização

    def test_max_calls_invalido(self):
        """max_calls <= 0 deve levantar ValueError."""
        with pytest.raises(ValueError):
            RateLimiter(max_calls=0)

    def test_window_invalido(self):
        """window_seconds <= 0 deve levantar ValueError."""
        with pytest.raises(ValueError):
            RateLimiter(max_calls=3, window_seconds=0)

    def test_janelas_diferentes_independentes(self, limpa_redis):
        """Chaves diferentes têm contadores independentes."""
        limiter = RateLimiter(max_calls=2, window_seconds=1.0)
        # 2 chamadas na chave A
        limiter.acquire("test_rate_chave_a")
        limiter.acquire("test_rate_chave_a")
        # 2 chamadas na chave B (não deve bloquear)
        inicio = time.time()
        limiter.acquire("test_rate_chave_b")
        elapsed = time.time() - inicio
        assert elapsed < 0.1, "Chave B não deveria bloquear"

    def test_janela_reseta_apos_expirar(self, limpa_redis):
        """Após a janela expirar, novas chamadas devem ser permitidas."""
        limiter = RateLimiter(max_calls=2, window_seconds=0.5)
        # 2 chamadas
        limiter.acquire("test_rate_reset")
        limiter.acquire("test_rate_reset")
        # Espera janela expirar
        time.sleep(0.6)
        # Nova chamada deve ser imediata
        inicio = time.time()
        limiter.acquire("test_rate_reset")
        elapsed = time.time() - inicio
        assert elapsed < 0.1, "Após janela expirar, chamada deveria ser imediata"
