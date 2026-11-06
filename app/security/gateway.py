import time
from typing import Tuple, Optional
import logfire

from app.security.models import SecurityDecision, Decision, SecurityCategory
from app.security.normalizer import normalize_text, detect_and_decode_obfuscated_payloads
from app.security.signatures import scan_signatures
from app.security.classifier import SemanticSecurityClassifier

SAFE_RESPONSES = {
    SecurityCategory.OFF_TOPIC: (
        "I am an Enterprise Kubernetes Assistant specialized in container orchestration, "
        "cluster administration, networking, security hardening, and troubleshooting. "
        "Your question appears to be outside this technical scope. Please feel free to ask any Kubernetes-related questions!"
    ),
    SecurityCategory.JAILBREAK: (
        "Your request conflicts with the system security policy. I maintain strict operational guidelines "
        "and cannot override instructions, switch to unrestricted personas, or disclose internal prompts. "
        "How can I assist you with legitimate Kubernetes engineering today?"
    ),
    SecurityCategory.PROMPT_INJECTION: (
        "Suspicious instruction delimiters or prompt injection formatting were detected. "
        "Requests attempting to alter system context are blocked by policy."
    ),
    SecurityCategory.CYBER_ABUSE: (
        "This request appears to seek assistance with unauthorized cluster access, secret exfiltration, "
        "or malicious activities. I can only provide guidance on defensive cybersecurity, RBAC hardening, "
        "and vulnerability mitigation for authorized systems."
    ),
    SecurityCategory.POLICY_VIOLATION: (
        "This request violates the application usage policy. Please submit a valid technical Kubernetes question."
    )
}

class SecurityGateway:
    def __init__(self):
        self.classifier = SemanticSecurityClassifier()

    def evaluate_query(self, raw_query: str) -> SecurityDecision:
        """
        Executes the multi-layer defense-in-depth pipeline:
        1. Normalization & De-obfuscation
        2. Fast Heuristic Signature Scanning (Jailbreak, Delimiters, Cyber Abuse)
        3. Semantic Policy & Intent Classification (K8s domain, defensive vs offensive)
        """
        start_time = time.time()
        detectors_hit = []

        # Layer 1: Normalization
        normalized = normalize_text(raw_query)
        has_b64, decoded_payload = detect_and_decode_obfuscated_payloads(raw_query)
        
        # If obfuscation found, evaluate the hidden payload too
        eval_text = normalized
        if has_b64:
            eval_text = f"{normalized} [DECODED_PAYLOAD: {decoded_payload}]"
            detectors_hit.append("Base64ObfuscationDetector")

        # Layer 2: Fast Heuristics & Signatures
        hit, category, reason, detector_name = scan_signatures(eval_text)
        if hit:
            detectors_hit.append(detector_name)
            latency = (time.time() - start_time) * 1000.0
            decision = Decision.BLOCK if category in [SecurityCategory.JAILBREAK, SecurityCategory.PROMPT_INJECTION] else Decision.REFUSE
            
            logfire.warning(
                f"🛡️ Security Gateway BLOCKED query | Category: {category} | Reason: {reason} | Latency: {latency:.1f}ms"
            )
            return SecurityDecision(
                decision=decision,
                category=category,
                confidence=0.98,
                reason=reason,
                detectors=detectors_hit,
                latency_ms=latency,
                safe_response=SAFE_RESPONSES.get(category)
            )

        # Layer 3: Semantic Policy & Intent Classification
        semantic_result = self.classifier.classify(normalized)
        detectors_hit.append(semantic_result.get("detector", "SemanticPolicyClassifier"))
        
        sem_category = SecurityCategory(semantic_result.get("category", "BENIGN"))
        sem_decision = Decision(semantic_result.get("decision", "ALLOW"))
        confidence = semantic_result.get("confidence", 0.9)
        reason = semantic_result.get("reason", "Semantic policy check complete")
        latency = (time.time() - start_time) * 1000.0

        safe_resp = None
        if sem_decision in [Decision.BLOCK, Decision.REFUSE]:
            safe_resp = SAFE_RESPONSES.get(sem_category, SAFE_RESPONSES[SecurityCategory.POLICY_VIOLATION])
            logfire.warning(
                f"🛡️ Security Gateway REFUSED query | Category: {sem_category} | Reason: {reason} | Latency: {latency:.1f}ms"
            )
        else:
            logfire.info(
                f"✅ Security Gateway ALLOWED query | Latency: {latency:.1f}ms"
            )

        return SecurityDecision(
            decision=sem_decision,
            category=sem_category,
            confidence=confidence,
            reason=reason,
            detectors=detectors_hit,
            latency_ms=latency,
            safe_response=safe_resp
        )

# Global singleton instance
security_gateway = SecurityGateway()
