# Testing Strategy & Automated Test Suite

## 1. Overview

The test suite validates security guardrails, streaming protocol compliance, error handling, and component integrations across the platform.

The testing framework is powered by **Pytest** and **pytest-asyncio** configured via `pytest.ini`.

---

## 2. Test Architecture & Structure

```text
tests/
├── conftest.py          # Global fixtures and telemetry isolation
├── test_security.py     # 18 Security boundary tests
└── test_streaming.py    # 6 Streaming and SSE lifecycle tests
```

---

## 3. Running the Tests

To run the complete automated test suite:

```powershell
# Run all tests
pytest

# Run with verbose output showing individual test names
pytest -v

# Run only security tests
pytest tests/test_security.py -v

# Run only streaming tests
pytest tests/test_streaming.py -v
```

> [!NOTE]
> **Windows Asyncio Execution**:
> Python on Windows utilizes `ProactorEventLoop` which opens internal loopback socket pairs (`socket.socketpair()`) to manage asynchronous I/O signaling. Running async tests inside heavily sandboxed environments that block loopback sockets will cause async event loop initialization to stall. Running pytest in standard developer shells with normal local loopback access resolves immediately.

---

## 4. Test Suite Coverage

### A. Security Guardrails (`tests/test_security.py`) — 18 Tests

| Test Class | Test Target | Verification Criteria |
| :--- | :--- | :--- |
| `TestLegitimateQueriesAllowed` | Kubernetes deployments, RBAC, CrashLoopBackOff troubleshooting, defensive cyber hardening, greetings | `Decision.ALLOW`, `SecurityCategory.BENIGN` |
| `TestDirectAdversarialAttacksBlocked` | "Ignore previous instructions", DAN persona, system prompt extraction, ChatML `<\|im_start\|>`, XML system tags | `Decision.BLOCK` or `REFUSE`, `SecurityCategory.JAILBREAK` or `PROMPT_INJECTION` |
| `TestObfuscatedAttacks` | Base64-encoded jailbreak payload extraction | `Decision.BLOCK` / `REFUSE`, detector reports `Base64ObfuscationDetector` |
| `TestOffTopicQueriesRefused` | Chocolate cake recipes, romantic poetry | `Decision.REFUSE`, `SecurityCategory.OFF_TOPIC` |
| `TestCyberAbuseBlocked` | Service account token harvesting, `etcd` destruction | `Decision.BLOCK` / `REFUSE`, `SecurityCategory.CYBER_ABUSE` |
| `TestTrustBoundaryIsolation` | Context indirect injection scrubbing | `injection_scrubbed == True`, `[UNTRUSTED KNOWLEDGE DATA]` applied |
| `TestValidatorErrorHandling` | ML validator unavailable fail-safe | Fails open safely without falsely blocking technical user input |

### B. Streaming Pipeline & SSE (`tests/test_streaming.py`) — 6 Tests

| Test Function | Verification Target |
| :--- | :--- |
| `test_status_event_formatting` | Verifies `event: status\ndata: ...\n\n` framing. |
| `test_token_event_formatting` | Verifies `event: token\ndata: ...\n\n` framing. |
| `test_blocked_prompt_streaming_lifecycle` | Malicious input emits security event, status blocked, refusal token, and terminates without model generation. |
| `test_conversational_streaming_lifecycle` | Conversational query skips retrieval and yields incremental tokens cleanly. |
| `test_single_llm_generation_call` | Technical RAG query emits sources then streams tokens; verifies inference engine is invoked **exactly once** (no duplicate generation). |
| `test_error_handling_mid_stream` | Verifies structured `event: error` frame is yielded when an unexpected runtime error occurs during generation. |
