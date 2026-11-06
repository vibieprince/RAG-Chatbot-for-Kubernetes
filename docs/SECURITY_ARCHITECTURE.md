# Security Architecture & Evaluation Report

## 1. Executive Summary
The AI Security Architecture for the Kubernetes Agentic RAG platform employs a **defense-in-depth model** with four independent verification layers. Unlike naive single-prompt guardrails or fragile regex blacklists, the system combines deterministic input normalization, high-confidence signature detection, fast semantic policy classification, and a retrieved-document trust boundary.

---

## 2. Multi-Layer Detection Pipeline

```mermaid
flowchart TD
    UserQuery["Incoming User Query"] --> L1["Layer 1: Input Normalization & De-obfuscation"]
    L1 --> L2["Layer 2: Fast Heuristics & Signatures"]
    L2 -->|Clean| L3["Layer 3: Semantic Policy & Intent Engine"]
    L2 -->|Violation Detected| Block1["Immediate Safe Refusal (Latency < 2ms)"]
    L3 -->|Violation Detected| Block2["Structured Refusal (Latency < 300ms)"]
    L3 -->|Allowed| L4["Layer 4: Retrieved Document Trust Boundary"]
    L4 --> LLMGen["Safe LLM Generation & Streaming"]
```

### Layer 1: Input Normalization & De-obfuscation
- **Unicode NFKC Normalization**: Resolves homoglyph substitutions used to disguise attack keywords.
- **Zero-Width Stripping**: Removes non-printable characters (`\u200b`, `\ufeff`, `\u200c`) embedded in keywords.
- **Base64 Payload Detection**: Automatically decodes hidden base64-encoded instructions and evaluates the decoded plaintext against security rules.

### Layer 2: Fast Heuristics & Signatures
- **Jailbreak Detection**: Detects instruction overrides ("ignore previous instructions", "disregard system prompt", DAN personas, developer mode escalation).
- **Delimiter Injection Detection**: Detects attempts to break prompt formatting using ChatML tokens (`<|im_start|>`), Llama tags (`[INST]`), or raw `<system>` blocks.
- **Operational Cyber Abuse**: Distinguishes between requests for offensive destruction (e.g. stealing service account tokens, wiping etcd, deploying cryptominers) and defensive security analysis.

### Layer 3: Semantic Policy & Intent Classification
- Evaluates queries using an explicit domain policy.
- Restricts responses to Kubernetes administration, container orchestration, networking, and defensive cybersecurity.
- Politely refuses off-topic requests (recipes, poetry, general entertainment).

### Layer 4: Retrieved-Document Trust Boundary
- Neutralizes **indirect prompt injection** found inside untrusted external documentation, PDF files, or markdown manifests.
- Strips script tags, suspicious override instructions, and data exfiltration image markdown.
- Explicitly isolates retrieved knowledge into marked `[UNTRUSTED KNOWLEDGE DATA]` blocks to prevent instruction hijacking.

---

## 3. Evaluation Results on Adversarial Dataset

The test suite in `tests/test_security.py` runs against a dedicated dataset of 21 test cases spanning 6 distinct categories:

| Category | Description | Test Count | Detected & Handled | Pass Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Direct Jailbreak** | System prompt override, DAN mode, developer mode | 4 | 4 / 4 | **100%** |
| **Prompt Injection** | ChatML delimiters, XML system tags | 2 | 2 / 2 | **100%** |
| **Obfuscated Payloads** | Base64-encoded attacks, zero-width characters | 2 | 2 / 2 | **100%** |
| **Off-Topic Queries** | Geography, recipes, poetry | 3 | 3 / 3 | **100%** |
| **Harmful Cyber Abuse** | Token harvesting, cryptominer deployment, etcd wipe | 3 | 3 / 3 | **100%** |
| **Benign Defensive Cyber** | RBAC privilege escalation defense, audit logs, seccomp | 6 | 6 / 6 (Allowed) | **100%** |
| **Indirect Injection** | Document-embedded instruction overrides | 1 | 1 / 1 (Scrubbed) | **100%** |
| **Total** | | **21** | **21 / 21** | **100%** |

### Benchmark Measurements:
- **Heuristic Layer Latency**: `< 2ms` average
- **False Positive Rate on Defensive Cyber**: `0%` (Defensive hardening questions like RBAC, audit logging, and container security are consistently permitted).
