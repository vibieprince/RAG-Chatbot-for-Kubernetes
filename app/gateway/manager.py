"""
LiteLLM Gateway Readiness & Parallel Wake-Up Manager.

Architecture:
  1. Parallel Cold-Start Wakeup:
     Immediately on request arrival, triggers a non-blocking asynchronous health
     probe to LiteLLM so cold-start waking overlaps with input validation,
     security checks, and initial SSE framing.
  2. Concurrency-Safe Deduplication (Single-Flight Pattern):
     If multiple concurrent requests arrive while LiteLLM is waking up, only a single
     probe loop is initiated. All concurrent callers attach to and await the same
     in-flight task without hammering the waking service.
  3. Bounded Exponential Backoff:
     Polls the LiteLLM health/readiness endpoint with configurable exponential backoff
     and a hard upper timeout boundary.
  4. Instantaneous Fallback:
     If the gateway is unreachable or probe times out, downstream components
     immediately route requests to direct Groq inference without dropping or delaying traffic.
  5. Readiness Caching:
     Maintains a TTL-bounded readiness state to skip network roundtrips when the gateway
     is actively warm.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Dict, Any

import httpx
import logfire

from app.config import settings


def derive_health_url(base_url: str, override_url: Optional[str] = None) -> str:
    """
    Derives the LiteLLM health readiness URL.
    E.g. 'http://127.0.0.1:4000/v1' -> 'http://127.0.0.1:4000/health/readiness'.
    """
    if override_url:
        return override_url.strip()

    clean_base = base_url.rstrip("/")
    if clean_base.endswith("/v1"):
        clean_base = clean_base[:-3]
    return f"{clean_base}/health/readiness"


class GatewayReadinessManager:
    """
    Manages LiteLLM gateway readiness probing, wake-up lifecycle,
    and single-flight concurrency synchronization.
    """

    def __init__(self) -> None:
        self._health_url = derive_health_url(settings.LITELLM_BASE_URL, settings.LITELLM_HEALTH_URL)
        self._is_ready: bool = False
        self._last_ready_monotonic: float = 0.0
        self._lock: Optional[asyncio.Lock] = None
        self._current_probe_task: Optional[asyncio.Task[bool]] = None
        self._client: Optional[httpx.AsyncClient] = None

    def _get_lock(self) -> asyncio.Lock:
        """Lazily creates the asyncio lock inside an active running loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily instantiates the shared httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=3.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                headers={"User-Agent": "KubernetesRAG-GatewayManager/2.0"},
            )
        return self._client

    def is_cached_ready(self) -> bool:
        """
        Returns True if the gateway was confirmed ready within the cache TTL window.
        """
        if not self._is_ready:
            return False
        elapsed = time.monotonic() - self._last_ready_monotonic
        return elapsed < settings.LITELLM_READINESS_CACHE_TTL

    def start_wakeup(self) -> asyncio.Future[bool]:
        """
        Initiates a non-blocking background wake-up probe.
        Guarantees single-flight deduplication: concurrent calls share the same task.
        """
        loop = asyncio.get_running_loop()

        # Fast path: already warm and cached
        if self.is_cached_ready():
            fut: asyncio.Future[bool] = loop.create_future()
            fut.set_result(True)
            return fut

        # Check existing in-flight task
        if self._current_probe_task is not None and not self._current_probe_task.done():
            return self._current_probe_task

        # Launch single probe task
        self._current_probe_task = loop.create_task(
            self._execute_probe_lifecycle(),
            name="litellm-gateway-wakeup-probe"
        )
        return self._current_probe_task

    async def wait_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Awaits the gateway readiness probe up to the specified timeout.
        Returns True if LiteLLM is awake and ready, False if timed out or failed.
        """
        task = self.start_wakeup()
        max_wait = timeout if timeout is not None else settings.LITELLM_WAKEUP_TIMEOUT
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=max_wait)
        except (asyncio.TimeoutError, Exception) as exc:
            logfire.warning(
                "Gateway readiness wait boundary reached: {exc}. Proceeding with fallback.",
                exc=str(exc)
            )
            return False

    async def _execute_probe_lifecycle(self) -> bool:
        """
        Internal probe loop with bounded exponential backoff.
        Protected by an async lock to prevent duplicate concurrent runs.
        """
        async with self._get_lock():
            # Re-check cache under lock
            if self.is_cached_ready():
                return True

            start_time = time.monotonic()
            max_timeout = settings.LITELLM_WAKEUP_TIMEOUT
            backoff = settings.LITELLM_INITIAL_BACKOFF
            client = self._get_client()

            headers: Dict[str, str] = {}
            if settings.LITELLM_MASTER_KEY:
                headers["Authorization"] = f"Bearer {settings.LITELLM_MASTER_KEY}"

            retries = 0
            logfire.info(
                "Initiating LiteLLM gateway parallel wake-up probe | Target: {url} | Max timeout: {max_timeout}s",
                url=self._health_url,
                max_timeout=max_timeout,
            )

            while (time.monotonic() - start_time) < max_timeout and retries < settings.LITELLM_MAX_RETRIES:
                retries += 1
                elapsed = time.monotonic() - start_time
                remaining = max(0.5, max_timeout - elapsed)
                probe_timeout = min(4.0, remaining)

                with logfire.span("LiteLLM Probe Attempt #{retries}", retries=retries):
                    try:
                        resp = await client.get(
                            self._health_url,
                            headers=headers,
                            timeout=probe_timeout
                        )
                        if resp.status_code == 200:
                            total_wake = time.monotonic() - start_time
                            self._is_ready = True
                            self._last_ready_monotonic = time.monotonic()
                            logfire.info(
                                "LiteLLM gateway confirmed READY | Attempts: {retries} | Total wake-up time: {total_wake:.2f}s",
                                retries=retries,
                                total_wake=total_wake,
                            )
                            return True

                        # Handle LiteLLM versions serving health at /health instead of /health/readiness
                        if resp.status_code == 404 and "/health/readiness" in self._health_url:
                            alt_url = self._health_url.replace("/health/readiness", "/health")
                            alt_resp = await client.get(alt_url, headers=headers, timeout=probe_timeout)
                            if alt_resp.status_code == 200:
                                self._health_url = alt_url
                                total_wake = time.monotonic() - start_time
                                self._is_ready = True
                                self._last_ready_monotonic = time.monotonic()
                                logfire.info(
                                    "LiteLLM gateway confirmed READY via /health | Attempts: {retries} | Total wake-up time: {total_wake:.2f}s",
                                    retries=retries,
                                    total_wake=total_wake,
                                )
                                return True

                        logfire.info(
                            "LiteLLM responded with status {status} (attempt {retries})",
                            status=resp.status_code,
                            retries=retries,
                        )

                    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as net_err:
                        logfire.info(
                            "LiteLLM gateway cold-starting (attempt {retries}): {err}",
                            retries=retries,
                            err=type(net_err).__name__,
                        )
                    except Exception as unexpected:
                        logfire.warning(
                            "Unexpected error during gateway probe (attempt {retries}): {err}",
                            retries=retries,
                            err=str(unexpected),
                        )

                # Sleep bounded exponential backoff
                time_left = max_timeout - (time.monotonic() - start_time)
                if time_left <= 0:
                    break

                sleep_time = min(backoff, time_left)
                await asyncio.sleep(sleep_time)
                backoff = min(backoff * settings.LITELLM_BACKOFF_FACTOR, 4.0)

            total_elapsed = time.monotonic() - start_time
            self._is_ready = False
            logfire.warning(
                "LiteLLM gateway wake-up failed or timed out after {total_elapsed:.2f}s ({retries} attempts). Downstream queries will use direct Groq fallback.",
                total_elapsed=total_elapsed,
                retries=retries,
            )
            return False

    async def check_health(self) -> bool:
        """Explicitly checks and updates health status."""
        return await self._execute_probe_lifecycle()

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic status of the gateway."""
        is_cached = self.is_cached_ready()
        elapsed = time.monotonic() - self._last_ready_monotonic if self._last_ready_monotonic > 0 else None
        return {
            "ready": is_cached,
            "cached": is_cached,
            "seconds_since_last_ready": round(elapsed, 1) if elapsed is not None else None,
            "in_flight_probe": bool(self._current_probe_task and not self._current_probe_task.done()),
            "health_url": self._health_url,
        }

    async def close(self) -> None:
        """Closes the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# Global Singleton Instance
gateway_manager = GatewayReadinessManager()
