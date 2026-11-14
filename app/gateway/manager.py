"""
LiteLLM Gateway Readiness & Parallel Wake-Up Manager.

Architecture:
  1. Two-Stage Probing with Clear Ownership:
     - Wake-up trigger: GET /health/liveliness (spins up Render instance)
     - Readiness verification: GET /health/readiness (checks model route health)
       with automatic fallback to /health if /health/readiness returns 404.
  2. Redundant Wake-Up Elimination:
     - When Streamlit initiates parallel wake-up, it sets X-LiteLLM-Wakeup-Triggered: true.
     - FastAPI detects this header and skips sending a duplicate /health/liveliness trigger,
       proceeding directly to polling /health/readiness.
     - Direct calls to FastAPI without Streamlit continue to trigger /health/liveliness
       authoritatively before checking readiness.
  3. GET method enforcement: Uses GET, not HEAD, ensuring full end-to-end response validation.
  4. Configurable Deadline (default ~120s):
     Accommodates Render free-tier cold starts (~88s observed) without premature aborts.
  5. Bounded Exponential Backoff with Jitter:
     Individual request timeouts and backoff delays dynamically clamp to the remaining deadline.
  6. Single-Flight Concurrency Deduplication:
     Concurrent requests share the same in-flight probe task to avoid thundering herd.
  7. Observable Logging:
     Logs elapsed time, attempt number, endpoint, status code, and final outcome with Logfire.
  8. Controlled Degradation:
     Returns False when gateway is not ready within deadline, allowing downstream callers
     to route to verified direct Groq fallback or emit controlled 503/504 errors.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional, Dict, Any

import httpx
import logfire

from app.config import settings


def derive_health_url(base_url: str, override_url: Optional[str] = None) -> str:
    """
    Derives the LiteLLM health readiness URL.
    E.g. 'http://127.0.0.1:4000/v1' -> 'http://127.0.0.1:4000/health/readiness'.
    Normalizes legacy base '/health' to canonical '/health/readiness'.
    """
    if override_url:
        override = override_url.strip()
        if override.rstrip("/").endswith("/health"):
            return f"{override.rstrip('/')}/readiness"
        return override

    clean_base = base_url.rstrip("/")
    if clean_base.endswith("/v1"):
        clean_base = clean_base[:-3]
    return f"{clean_base}/health/readiness"


def derive_liveliness_url(base_url: str, override_url: Optional[str] = None) -> str:
    """
    Derives the LiteLLM health liveliness URL.
    E.g. 'http://127.0.0.1:4000/v1' -> 'http://127.0.0.1:4000/health/liveliness'.
    """
    if override_url and "/health/liveliness" in override_url:
        return override_url.strip()

    clean_base = base_url.rstrip("/")
    if clean_base.endswith("/v1"):
        clean_base = clean_base[:-3]
    return f"{clean_base}/health/liveliness"


class GatewayReadinessManager:
    """
    Manages LiteLLM gateway readiness probing, cold-start wake-up lifecycle,
    and single-flight concurrency synchronization.
    """

    def __init__(self) -> None:
        self._health_url = derive_health_url(settings.LITELLM_BASE_URL, settings.LITELLM_HEALTH_URL)
        self._liveliness_url = derive_liveliness_url(settings.LITELLM_BASE_URL)
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

    def start_wakeup(
        self,
        request_id: Optional[str] = None,
        skip_liveliness_trigger: bool = False,
    ) -> asyncio.Future[bool]:
        """
        Initiates a non-blocking background wake-up probe.
        Guarantees single-flight deduplication: concurrent calls share the same task.
        If skip_liveliness_trigger is True, skips redundant /health/liveliness ping
        (already triggered by frontend).
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
            self._execute_probe_lifecycle(
                request_id=request_id,
                skip_liveliness_trigger=skip_liveliness_trigger,
            ),
            name="litellm-gateway-wakeup-probe"
        )
        return self._current_probe_task

    async def wait_ready(
        self,
        timeout: Optional[float] = None,
        request_id: Optional[str] = None,
        skip_liveliness_trigger: bool = False,
    ) -> bool:
        """
        Awaits the gateway readiness probe up to the specified timeout deadline.
        Returns True if LiteLLM is awake and ready, False if timed out or failed.
        """
        task = self.start_wakeup(request_id=request_id, skip_liveliness_trigger=skip_liveliness_trigger)
        max_wait = timeout if timeout is not None else settings.LITELLM_WAKEUP_TIMEOUT
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=max_wait)
        except (asyncio.TimeoutError, Exception) as exc:
            logfire.warning(
                "Gateway readiness wait boundary reached: {exc}. Proceeding with controlled fallback.",
                exc=str(exc),
                request_id=request_id or "unknown",
            )
            return False

    async def _execute_probe_lifecycle(
        self,
        request_id: Optional[str] = None,
        skip_liveliness_trigger: bool = False,
    ) -> bool:
        """
        Internal probe loop:
          Step 1: Trigger wake-up via GET /health/liveliness (if not already triggered by caller).
          Step 2: Verify readiness via GET /health/readiness (or /health fallback).
          Applies bounded exponential backoff with jitter up to the configured overall deadline.
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
            if request_id:
                headers["X-Request-ID"] = request_id

            retries = 0
            logfire.info(
                "Initiating LiteLLM gateway wake-up & readiness orchestration | Wake: {wake_url} | Ready: {ready_url} | Deadline: {max_timeout}s | SkipWakePing: {skip}",
                wake_url=self._liveliness_url,
                ready_url=self._health_url,
                max_timeout=max_timeout,
                skip=skip_liveliness_trigger,
                request_id=request_id or "unknown",
            )

            # --- Step 1: Initial Wake-up Trigger via /health/liveliness (unless already pinged) ---
            if not skip_liveliness_trigger:
                try:
                    retries += 1
                    probe_timeout = min(5.0, max(0.5, max_timeout - (time.monotonic() - start_time)))
                    wake_resp = await client.get(
                        self._liveliness_url,
                        headers=headers,
                        timeout=probe_timeout,
                    )
                    logfire.info(
                        "LiteLLM wake-up trigger ({url}) returned status {status} (attempt {retries})",
                        url=self._liveliness_url,
                        status=wake_resp.status_code,
                        retries=retries,
                        elapsed=round(time.monotonic() - start_time, 2),
                    )
                except Exception as wake_err:
                    logfire.info(
                        "LiteLLM wake-up trigger ({url}) pinged: {err} (attempt {retries})",
                        url=self._liveliness_url,
                        err=type(wake_err).__name__,
                        retries=retries,
                        elapsed=round(time.monotonic() - start_time, 2),
                    )
            else:
                logfire.info(
                    "LiteLLM wake-up ping already triggered by client; proceeding directly to readiness verification.",
                    request_id=request_id or "unknown",
                )

            # --- Step 2: Poll Readiness via /health/readiness with Jittered Backoff ---
            while (time.monotonic() - start_time) < max_timeout and retries < settings.LITELLM_MAX_RETRIES:
                retries += 1
                elapsed = time.monotonic() - start_time
                remaining = max(0.1, max_timeout - elapsed)
                if remaining <= 0.1:
                    break

                probe_timeout = min(5.0, remaining)
                target_url = self._health_url

                with logfire.span("LiteLLM Readiness Probe Attempt #{retries}", retries=retries):
                    try:
                        resp = await client.get(
                            target_url,
                            headers=headers,
                            timeout=probe_timeout,
                        )

                        if resp.status_code == 200:
                            total_wake = time.monotonic() - start_time
                            self._is_ready = True
                            self._last_ready_monotonic = time.monotonic()
                            logfire.info(
                                "LiteLLM gateway confirmed READY | Endpoint: {url} | Attempts: {retries} | Total elapsed: {total_wake:.2f}s | Outcome: SUCCESS",
                                url=target_url,
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
                                    "LiteLLM gateway confirmed READY via /health | Attempts: {retries} | Total elapsed: {total_wake:.2f}s | Outcome: SUCCESS",
                                    retries=retries,
                                    total_wake=total_wake,
                                )
                                return True

                        logfire.info(
                            "LiteLLM readiness probe returned status {status} (attempt {retries})",
                            status=resp.status_code,
                            retries=retries,
                            elapsed=round(time.monotonic() - start_time, 2),
                        )

                    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as net_err:
                        logfire.info(
                            "LiteLLM gateway cold-starting (attempt {retries}): {err}",
                            retries=retries,
                            err=type(net_err).__name__,
                            elapsed=round(time.monotonic() - start_time, 2),
                        )
                    except Exception as unexpected:
                        logfire.warning(
                            "Unexpected error during gateway probe (attempt {retries}): {err}",
                            retries=retries,
                            err=str(unexpected),
                            elapsed=round(time.monotonic() - start_time, 2),
                        )

                # Check remaining time before sleeping
                time_left = max_timeout - (time.monotonic() - start_time)
                if time_left <= 0:
                    break

                # Exponential backoff with sensible jitter
                jitter = random.uniform(0.0, 0.4)
                sleep_time = min(backoff + jitter, time_left)
                await asyncio.sleep(sleep_time)
                backoff = min(backoff * settings.LITELLM_BACKOFF_FACTOR, settings.LITELLM_MAX_BACKOFF)

            total_elapsed = time.monotonic() - start_time
            self._is_ready = False
            logfire.warning(
                "LiteLLM gateway readiness deadline reached after {total_elapsed:.2f}s ({retries} attempts) | Outcome: TIMEOUT / UNREADY",
                total_elapsed=total_elapsed,
                retries=retries,
                endpoint=self._health_url,
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
            "liveliness_url": self._liveliness_url,
            "timeout_deadline_seconds": settings.LITELLM_WAKEUP_TIMEOUT,
        }

    async def close(self) -> None:
        """Closes the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# Global Singleton Instance
gateway_manager = GatewayReadinessManager()
