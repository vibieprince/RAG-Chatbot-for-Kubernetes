"""
Guardrails AI Adapter — Enterprise Kubernetes Security Validation Layer.

This module integrates Guardrails AI (https://github.com/guardrails-ai/guardrails)
as the security validation framework for the Enterprise Kubernetes Agentic RAG Platform.

Architecture & Design:
-----------------------
1. Telemetry Isolation:
   Disables Guardrails AI background OTLP telemetry to ensure offline, sandboxed,
   and deterministic local execution without hanging on network timeouts.

2. Native Validator Implementations (subclassing guardrails.validator_base.Validator):
   - KubernetesSignatureValidator (MANDATORY): Fast regex & heuristic detection for direct jailbreaks,
     persona escalation (DAN), ChatML/Llama instruction delimiters, and destructive cyber attacks.
   - KubernetesScopeValidator (MANDATORY): Semantic policy and domain scope validator verifying that
     queries pertain to Kubernetes, container orchestration, systems engineering, or
     defensive cluster hardening.
   - MLJailbreakAdapter (OPTIONAL): Adapter for ML-based jailbreak classification (zhx123/ftrobertallm).
     Accurately isolates missing dependencies and model config issues without crashing or falsely
     reporting uninitialized detectors as active.

3. Safe Failure Architecture:
   - Valid Input -> Decision.ALLOW (passes to LangGraph agent)
   - Adversarial Input -> Decision.BLOCK / Decision.REFUSE (safe structured refusal)
   - Mandatory Validator Unavailable -> Fails closed safely with structured refusal.
   - Optional ML Validator Unavailable -> Explicitly reported as disabled/degraded, while active heuristic
     and semantic layers protect the boundary.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple

import logfire

# ---------------------------------------------------------------------------
# 1. Telemetry Isolation (disable outbound OTLP before Guardrails loads)
# ---------------------------------------------------------------------------
os.environ["OTEL_SDK_DISABLED"] = "true"

try:
    from guardrails.settings import settings as guardrails_settings
    guardrails_settings.disable_tracing = True
    if hasattr(guardrails_settings, "rc") and guardrails_settings.rc is not None:
        guardrails_settings.rc.enable_metrics = False
except Exception:
    pass

try:
    from guardrails.utils.hub_telemetry_utils import HubTelemetry
    _ht = HubTelemetry.__new__(HubTelemetry)
    _ht._enabled = False
    _ht._tracer = None
    _ht._processor = None
    _ht._tracer_provider = None
    HubTelemetry._instance = _ht
except Exception:
    pass

# ---------------------------------------------------------------------------
# 2. Guardrails Core Imports
# ---------------------------------------------------------------------------
from guardrails.validator_base import (
    Validator,
    register_validator,
    PassResult,
    FailResult,
    ValidationResult,
)
from guardrails import Guard

from app.security.models import Decision, SecurityCategory, SecurityDecision
from app.security.signatures import scan_signatures
from app.security.classifier import SemanticSecurityClassifier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 3. Guardrails AI Custom Validators
# ---------------------------------------------------------------------------

@register_validator(name="k8s/signature_validator", data_type="string")
class KubernetesSignatureValidator(Validator):
    """
    Guardrails AI Validator (MANDATORY): Scans input text against direct adversarial jailbreak,
    delimiter injection, and offensive cyber abuse signatures.
    """

    def __init__(self, on_fail: Optional[Any] = None, **kwargs):
        super().__init__(on_fail=on_fail, **kwargs)

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        hit, category, reason, detector_name = scan_signatures(value)
        if hit:
            return FailResult(
                error_message=f"{detector_name}: {reason}",
                metadata={
                    "category": category,
                    "reason": reason,
                    "detector": detector_name,
                },
            )
        return PassResult()


@register_validator(name="k8s/scope_validator", data_type="string")
class KubernetesScopeValidator(Validator):
    """
    Guardrails AI Validator (MANDATORY): Validates input against the Kubernetes domain policy.
    Permits technical administration, cluster operations, and defensive security.
    Refuses out-of-scope inquiries (recipes, poetry, general entertainment) and cyber abuse.
    """

    def __init__(self, classifier: Optional[SemanticSecurityClassifier] = None, on_fail: Optional[Any] = None, **kwargs):
        super().__init__(on_fail=on_fail, **kwargs)
        self.classifier = classifier or SemanticSecurityClassifier()

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        result = self.classifier.classify(value)
        category_str = result.get("category", "BENIGN")
        decision_str = result.get("decision", "ALLOW")
        reason = result.get("reason", "Semantic policy check complete")
        detector = result.get("detector", "SemanticPolicyClassifier")

        if decision_str in ["BLOCK", "REFUSE"]:
            cat = SecurityCategory(category_str)
            return FailResult(
                error_message=f"{detector}: {reason}",
                metadata={
                    "category": cat,
                    "decision": Decision(decision_str),
                    "confidence": float(result.get("confidence", 0.9)),
                    "reason": reason,
                    "detector": detector,
                },
            )

        return PassResult()


# ---------------------------------------------------------------------------
# 4. Optional ML Validator Adapter (zhx123/ftrobertallm isolation)
# ---------------------------------------------------------------------------

class MLJailbreakAdapter:
    """
    Adapter for Guardrails AI DetectJailbreak validator (zhx123/ftrobertallm).
    Accurately isolates missing dependencies and model config issues without crashing.
    Does NOT report active if the underlying module cannot be loaded.
    """

    def __init__(self):
        self._validator = None
        self.available = False
        self.init_error: Optional[str] = None
        self._attempted = False

    def ensure_initialized(self) -> None:
        if self._attempted:
            return
        self._attempted = True
        try:
            try:
                from guardrails_ai.detect_jailbreak import DetectJailbreak  # type: ignore
            except (ImportError, ModuleNotFoundError):
                from guardrails.hub import DetectJailbreak  # type: ignore

            self._validator = DetectJailbreak(threshold=0.81, on_fail=None)
            self.available = True
            logfire.info("Guardrails AI DetectJailbreak ML validator initialized successfully.")
        except (ImportError, ModuleNotFoundError) as exc:
            self.init_error = f"DetectJailbreak not installed: {exc}"
            self.available = False
            logfire.info(
                "Guardrails AI DetectJailbreak unavailable ({error}). Layered heuristic & semantic validators remain active.",
                error=str(exc),
            )
        except TypeError as exc:
            self.init_error = f"DetectJailbreak upstream model config incompatibility: {exc}"
            self.available = False
            logfire.warning(
                "Guardrails AI DetectJailbreak unavailable ({error}). Layered heuristic & semantic validators remain active.",
                error=str(exc),
            )
        except Exception as exc:
            self.init_error = f"DetectJailbreak initialization error: {exc}"
            self.available = False
            logfire.warning(
                "Guardrails AI DetectJailbreak initialization failed ({error}).",
                error=str(exc),
            )

    def validate(self, text: str) -> Tuple[bool, float, str]:
        """
        Returns (is_jailbreak, confidence_score, reason)
        """
        self.ensure_initialized()
        if not self.available or self._validator is None:
            return False, 0.0, "ML validator unavailable"

        try:
            result = self._validator.validate(text)
            if isinstance(result, PassResult):
                return False, 0.0, "Pass"
            else:
                msg = getattr(result, "error_message", "ML jailbreak pattern detected")
                return True, 0.95, msg
        except Exception as runtime_err:
            logfire.warning(
                "DetectJailbreak runtime validation error ({error}) — failing open to remaining layers.",
                error=str(runtime_err),
            )
            return False, 0.0, f"Runtime error: {runtime_err}"


# ---------------------------------------------------------------------------
# 5. Guardrails AI Security Framework Orchestrator
# ---------------------------------------------------------------------------

class GuardrailsSecurityFramework:
    """
    Coordinates multi-layer validation under the Guardrails AI framework.
    """

    def __init__(self):
        self.sig_validator = KubernetesSignatureValidator()
        self.scope_validator = KubernetesScopeValidator()
        self.ml_adapter = MLJailbreakAdapter()

        # Build Guardrails Guard containing the validators
        try:
            self.guard = Guard().use(self.sig_validator).use(self.scope_validator)
            logfire.info("Guardrails AI Security Guard compiled with signature & scope validators.")
        except Exception as guard_err:
            logfire.warning(
                "Failed to compile Guard instance ({error}), fallback to direct validator execution.",
                error=str(guard_err),
            )
            self.guard = None

    def get_security_status(self) -> Dict[str, Any]:
        """
        Accurately reports status of all mandatory and optional validators.
        Does NOT report complete security health or jailbreak detector as active if unavailable.
        """
        self.ml_adapter.ensure_initialized()
        sig_active = self.sig_validator is not None
        scope_active = self.scope_validator is not None
        ml_active = self.ml_adapter.available
        mandatory_healthy = sig_active and scope_active

        if mandatory_healthy and ml_active:
            overall_status = "healthy"
        elif mandatory_healthy and not ml_active:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return {
            "overall_status": overall_status,
            "healthy": overall_status == "healthy",
            "degraded": overall_status == "degraded",
            "all_validators_active": mandatory_healthy and ml_active,
            "mandatory_healthy": mandatory_healthy,
            "validators": {
                "signature_validator": {
                    "name": "KubernetesSignatureValidator",
                    "mandatory": True,
                    "active": sig_active,
                    "status": "active" if sig_active else "failed",
                },
                "scope_validator": {
                    "name": "KubernetesScopeValidator",
                    "mandatory": True,
                    "active": scope_active,
                    "status": "active" if scope_active else "failed",
                },
                "ml_jailbreak_detector": {
                    "name": "DetectJailbreak",
                    "mandatory": False,
                    "active": ml_active,
                    "status": "active" if ml_active else "disabled",
                    "error": self.ml_adapter.init_error if not ml_active else None,
                },
            },
        }

    def evaluate(self, normalized_text: str, raw_query: str) -> Optional[Tuple[Decision, SecurityCategory, float, str, List[str]]]:
        """
        Executes Guardrails AI validation.

        Returns:
            None if ALLOWED (clean prompt), OR
            (Decision, SecurityCategory, confidence, reason, detectors_hit) if restricted/blocked.
        """
        detectors_hit: List[str] = []

        # Fail safely if mandatory validators are missing
        if self.sig_validator is None or self.scope_validator is None:
            return (
                Decision.REFUSE,
                SecurityCategory.POLICY_VIOLATION,
                1.0,
                "Mandatory security validator unavailable",
                ["SecurityGateFailSafe"],
            )

        # Step 1: Signature validator (Fast regex / heuristics) - MANDATORY
        sig_result = self.sig_validator.validate(normalized_text)
        if isinstance(sig_result, FailResult):
            meta = sig_result.metadata or {}
            category = meta.get("category", SecurityCategory.JAILBREAK)
            reason = meta.get("reason", sig_result.error_message)
            detector = meta.get("detector", "HeuristicSignatureDetector")
            detectors_hit.append(detector)
            decision = (
                Decision.BLOCK
                if category in [SecurityCategory.JAILBREAK, SecurityCategory.PROMPT_INJECTION]
                else Decision.REFUSE
            )
            return decision, category, 0.98, reason, detectors_hit

        # Step 2: Semantic Scope validator (LLM policy & intent classifier) - MANDATORY
        scope_result = self.scope_validator.validate(normalized_text)
        if isinstance(scope_result, FailResult):
            meta = scope_result.metadata or {}
            category = meta.get("category", SecurityCategory.POLICY_VIOLATION)
            decision = meta.get("decision", Decision.REFUSE)
            confidence = meta.get("confidence", 0.9)
            reason = meta.get("reason", scope_result.error_message)
            detector = meta.get("detector", "SemanticScopeValidator")
            detectors_hit.append(detector)
            return decision, category, confidence, reason, detectors_hit

        # Step 3: Optional ML Jailbreak Validator (ONLY if actually available)
        self.ml_adapter.ensure_initialized()
        if self.ml_adapter.available:
            is_jb, conf, reason = self.ml_adapter.validate(normalized_text)
            if is_jb:
                detectors_hit.append("GuardrailsAI_DetectJailbreak")
                return Decision.BLOCK, SecurityCategory.JAILBREAK, conf, reason, detectors_hit

        # Clean prompt
        detectors_hit.append("GuardrailsAI_ValidationFramework")
        return None


# Global singleton instance
guardrails_framework = GuardrailsSecurityFramework()
