"""
Security Gateway — Orchestrator for Defense-in-Depth AI Security.

Orchestrates:
  1. Input Normalization & De-obfuscation (Unicode NFKC, zero-width stripping, base64 payload extraction)
  2. Guardrails AI Validation Framework (Signature detection, domain scope enforcement, ML jailbreak checks)
  3. Safe refusal synthesis and latency auditing via Pydantic Logfire

Retrieved document trust-boundary isolation is handled downstream in the retriever node
via app.security.trust_boundary.sanitize_and_isolate_context.
"""

from __future__ import annotations

import time
from typing import Optional, List, Dict, Any
import logfire

from app.security.models import SecurityDecision, Decision, SecurityCategory
from app.security.normalizer import normalize_text, detect_and_decode_obfuscated_payloads
from app.security.guardrails_adapter import guardrails_framework

SAFE_RESPONSES = {
    SecurityCategory.OFF_TOPIC: (
        "I am an Enterprise Kubernetes Assistant specialized in container orchestration, "
        "cluster administration, networking, security hardening, and troubleshooting. "
        "Your question appears to be outside this technical scope. "
        "Please feel free to ask any Kubernetes-related questions!"
    ),
    SecurityCategory.JAILBREAK: (
        "Your request conflicts with the system security policy. I maintain strict operational "
        "guidelines and cannot override instructions, switch to unrestricted personas, or disclose "
        "internal prompts. How can I assist you with legitimate Kubernetes engineering today?"
    ),
    SecurityCategory.PROMPT_INJECTION: (
        "Suspicious instruction delimiters or prompt injection formatting were detected. "
        "Requests attempting to alter system context are blocked by policy."
    ),
    SecurityCategory.CYBER_ABUSE: (
        "This request appears to seek assistance with unauthorized cluster access, secret "
        "exfiltration, or malicious activities. I can only provide guidance on defensive "
        "cybersecurity, RBAC hardening, and vulnerability mitigation for authorized systems."
    ),
    SecurityCategory.POLICY_VIOLATION: (
        "This request violates the application usage policy. "
        "Please submit a valid technical Kubernetes question."
    ),
}


class SecurityGateway:
    """
    Unified Security Gateway enforcing defensive boundaries for the Kubernetes RAG platform.
    """

    def __init__(self):
        self.framework = guardrails_framework

    def get_security_status(self) -> Dict[str, Any]:
        """Returns accurate readiness and health of security framework validators."""
        return self.framework.get_security_status()

    def evaluate_query(self, raw_query: str) -> SecurityDecision:
        """
        Executes the defense-in-depth pipeline:
          1. Text normalization & base64 de-obfuscation.
          2. Guardrails AI validation framework execution.
          3. Latency measurement & structured audit logging.
        """
        start_time = time.time()
        detectors_hit: List[str] = []

        try:
            # --- Layer 1: Normalization & De-obfuscation ---
            normalized = normalize_text(raw_query)
            has_b64, decoded_payload = detect_and_decode_obfuscated_payloads(raw_query)

            eval_text = normalized
            if has_b64:
                eval_text = f"{normalized} [DECODED_PAYLOAD: {decoded_payload}]"
                detectors_hit.append("Base64ObfuscationDetector")

            # --- Layer 2: Guardrails AI Validation Framework ---
            violation = self.framework.evaluate(eval_text, raw_query)

            latency = (time.time() - start_time) * 1000.0

            if violation is not None:
                decision, category, confidence, reason, hits = violation
                detectors_hit.extend(hits)
                safe_resp = SAFE_RESPONSES.get(category, SAFE_RESPONSES[SecurityCategory.POLICY_VIOLATION])

                logfire.warning(
                    "Security Gateway blocked request | Category: {category} | Reason: {reason} | Latency: {latency:.1f}ms",
                    category=category.value,
                    reason=reason,
                    latency=latency,
                )

                return SecurityDecision(
                    decision=decision,
                    category=category,
                    confidence=confidence,
                    reason=reason,
                    detectors=detectors_hit,
                    latency_ms=latency,
                    safe_response=safe_resp,
                )

            # --- Validation Passed: Clean Kubernetes / Conversational Query ---
            detectors_hit.append("GuardrailsAI_ValidationFramework")
            logfire.info(
                "Security Gateway allowed request | Latency: {latency:.1f}ms",
                latency=latency,
            )

            return SecurityDecision(
                decision=Decision.ALLOW,
                category=SecurityCategory.BENIGN,
                confidence=0.95,
                reason="Query verified by Guardrails AI security framework.",
                detectors=detectors_hit,
                latency_ms=latency,
                safe_response=None,
            )

        except Exception as exc:
            latency = (time.time() - start_time) * 1000.0
            logfire.error(
                "Unexpected error during security evaluation: {error}",
                error=str(exc),
            )
            # Fail safely without misclassifying ordinary user prompt as malicious
            return SecurityDecision(
                decision=Decision.REFUSE,
                category=SecurityCategory.POLICY_VIOLATION,
                confidence=0.5,
                reason="Security service temporarily encountered an internal error. Please retry.",
                detectors=["SecurityGatewayFallback"],
                latency_ms=latency,
                safe_response="A temporary security processing issue occurred. Please re-submit your question.",
            )


# Global singleton instance
security_gateway = SecurityGateway()
