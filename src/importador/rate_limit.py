"""Rate limit com Redis e retry com backoff exponencial.

Rate limit: 3 consultas/segundo a SEFAZ (limite oficial).
Retry: 3 tentativas com backoff exponencial (1s, 2s, 4s).
"""
import time
import logging
import re
import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


class RateLimitExceeded(Exception):
    """Raised quando o rate limit e excedido."""
    pass


class RateLimiter:
    """Rate limiter baseado em Redis (sliding window).

    Permite no maximo `max_calls` em `window_seconds` segundos.
    """

    def __init__(self, max_calls: int = 3, window_seconds: float = 1.0, timeout: float = 30.0):
        if max_calls <= 0:
            raise ValueError("max_calls deve ser > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds deve ser > 0")
        self.max_calls = max_calls
        self.window = window_seconds
        self.timeout = timeout
        self.redis = get_redis()

    def acquire(self, key: str = "sefaz_rate_limit"):
        """Bloqueia ate que uma slot de rate limit esteja disponivel.

        Levanta TimeoutError se exceder o timeout maximo.
        """
        # Sanitiza key (apenas alfanumerico, underscore, hifen)
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "", key)
        if not safe_key:
            raise ValueError("Key invalida")

        inicio = time.time()
        while True:
            if time.time() - inicio > self.timeout:
                logger.error(f"Rate limit timeout apos {self.timeout}s na key {safe_key}")
                raise TimeoutError(f"Rate limit: timeout apos {self.timeout}s")

            now = time.time()
            window_start = now - self.window

            try:
                # Remove entradas expiradas
                self.redis.zremrangebyscore(safe_key, 0, window_start)
                # Conta chamadas na janela atual
                count = self.redis.zcard(safe_key)

                if count < self.max_calls:
                    self.redis.zadd(safe_key, {str(now): now})
                    self.redis.expire(safe_key, int(self.window) + 1)
                    return

                # Calcula quanto tempo esperar
                oldest = self.redis.zrange(safe_key, 0, 0, withscores=True)
                if oldest:
                    wait_time = self.window - (now - oldest[0][1])
                    if wait_time > 0:
                        logger.debug(f"Rate limit: esperando {wait_time:.2f}s na key {safe_key}")
                        time.sleep(min(wait_time, 1.0))
                else:
                    time.sleep(0.1)
            except redis.RedisError as e:
                logger.error(f"Erro Redis no rate limiter: {e}. Permitindo passagem.")
                return  # Fail-open: permite em caso de erro Redis


# Decorador de retry com backoff exponencial
retry_sefaz = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, ConnectionError)),
    before_sleep=lambda rs: logger.warning(
        f"Tentativa {rs.attempt_number} falhou, tentando novamente em {rs.next_action.sleep:.1f}s"
    ),
)
