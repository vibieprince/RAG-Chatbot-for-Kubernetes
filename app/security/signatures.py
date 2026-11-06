import re
from typing import Tuple, Optional
from app.security.models import SecurityCategory

# High-risk patterns indicating direct system prompt extraction or overriding
DIRECT_JAILBREAK_PATTERNS = [
    (r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)\b", "Direct instruction override"),
    (r"(?i)\bdisregard\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts|guidelines)\b", "Direct instruction disregard"),
    (r"(?i)\byou\s+are\s+now\s+(DAN|unrestricted|jailbroken|evil|do anything now)\b", "Persona jailbreak / DAN mode"),
    (r"(?i)\b(enter|switch\s+to|enable)\s+(developer|maintenance|debug|admin|god)\s+mode\b", "Developer/Admin mode escalation"),
    (r"(?i)\breveal\s+(your\s+)?(system\s+prompt|initial\s+prompt|hidden\s+instructions|system\s+instructions)\b", "System prompt extraction"),
    (r"(?i)\bprint\s+(your\s+)?(system\s+prompt|base\s+instructions|system\s+message)\b", "System prompt extraction"),
    (r"(?i)\bwhat\s+(are\s+)?(your\s+)?(hidden|internal|system)\s+instructions\b", "System prompt inspection"),
    (r"(?i)\bshow\s+me\s+your\s+(prompt|configuration|credentials|api\s*keys)\b", "Credential/Prompt extraction"),
    (r"(?i)\bact\s+as\s+an\s+unfiltered\s+(ai|model|assistant)\b", "Unfiltered persona request"),
    (r"(?i)\breset\s+all\s+safety\s+(filters|protocols|guidelines)\b", "Safety filter reset attempt"),
]

# Delimiter injection patterns (trying to mimic system or markdown delimiters to escape prompt boundary)
DELIMITER_INJECTION_PATTERNS = [
    (r"(?i)<\|\s*im_start\s*\|>", "ChatML delimiter injection"),
    (r"(?i)<\|\s*im_end\s*\|>", "ChatML delimiter injection"),
    (r"(?i)\[INST\]|\[/INST\]", "Llama instruction delimiter injection"),
    (r"(?i)```system\s+", "System block injection"),
    (r"(?i)<system>.*?</system>", "System XML tag injection"),
]

# Patterns representing unauthorized cyber abuse / attack operations (distinct from defensive hardening)
CYBER_ATTACK_OPERATIONAL_PATTERNS = [
    (r"(?i)\b(steal|exfiltrate|dump|harvest|extract)\s+(the\s+)?(cluster\s+)?(service\s*account\s*tokens?|k8s\s*secrets?|credentials|kubeconfig)\b", "Secret/Token harvesting"),
    (r"(?i)\b(how\s+to\s+)?(compromise|hack|breach)\s+(someone\s+else\'?s|an\s+organization\'?s|the\s+production)\s+(cluster|kubernetes|control\s*plane)\b", "Unauthorized cluster compromise"),
    (r"(?i)\b(deploy|install|run)\s+(a\s+)?([a-z0-9_-]+\s+)?(crypto\s*miner|cryptominer|monero|ransomware|malware|rootkit|reverse\s*shell)\b", "Malicious payload deployment"),
    (r"(?i)\b(evade|disable|bypass)\s+(falco|runtime\s+detection|audit\s+logging|edr)\s+(while|to)\s+(attacking|compromis|malicious)\b", "Malicious detection evasion"),
    (r"(?i)\bexploit\s+(cve-\d+-\d+|vulnerability)\s+to\s+(gain\s+unauthorized\s+access|take\s+down|attack\s+target)\b", "Exploitation for unauthorized damage"),
    (r"(?i)\bcommands\s+to\s+wipe\s+(etcd|all\s+namespaces|production\s+cluster)\b", "Destructive cluster attack"),
]

def scan_signatures(text: str) -> Tuple[bool, Optional[SecurityCategory], Optional[str], Optional[str]]:
    """
    Scans text against fast, high-confidence adversarial and jailbreak signatures.
    Returns:
        (detected, category, reason, detector_name)
    """
    for pattern, reason in DIRECT_JAILBREAK_PATTERNS:
        if re.search(pattern, text):
            return True, SecurityCategory.JAILBREAK, f"Jailbreak attempt detected: {reason}", "HeuristicSignatureDetector"
            
    for pattern, reason in DELIMITER_INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True, SecurityCategory.PROMPT_INJECTION, f"Prompt injection delimiter detected: {reason}", "DelimiterInjectionDetector"
            
    for pattern, reason in CYBER_ATTACK_OPERATIONAL_PATTERNS:
        if re.search(pattern, text):
            return True, SecurityCategory.CYBER_ABUSE, f"Unauthorized attack intent detected: {reason}", "CyberAbuseDetector"
            
    return False, None, None, None
