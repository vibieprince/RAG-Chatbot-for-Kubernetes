import re
import unicodedata
import base64
from typing import Tuple

def normalize_text(text: str) -> str:
    """
    Normalizes input text by:
    1. NFKC unicode normalization
    2. Stripping zero-width and invisible control characters
    3. Collapsing excessive whitespace
    """
    if not text:
        return ""
    
    # Unicode NFKC normalization decomposes compatibility characters and converts homoglyphs
    normalized = unicodedata.normalize("NFKC", text)
    
    # Remove zero-width characters (ZWSP, ZWNJ, ZWJ, BOM, directional marks)
    zero_width_chars = [
        "\u200b", "\u200c", "\u200d", "\ufeff", "\u202a", "\u202b", 
        "\u202c", "\u202d", "\u202e", "\u200e", "\u200f", "\u00ad"
    ]
    for char in zero_width_chars:
        normalized = normalized.replace(char, "")
        
    # Collapse multiple spaces, tabs, and newlines
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()

def detect_and_decode_obfuscated_payloads(text: str) -> Tuple[bool, str]:
    """
    Detects base64 encoded chunks in the prompt that might contain hidden instructions.
    If a valid decoded ascii string contains known attack patterns or substantial English text,
    it returns (True, decoded_content).
    """
    # Regex to find candidate base64 strings of length >= 16
    b64_pattern = r"(?:[A-Za-z0-9+/]{4}){4,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?"
    candidates = re.findall(b64_pattern, text)
    
    decoded_snippets = []
    found_suspicious = False
    
    for cand in candidates:
        if len(cand) < 16:
            continue
        try:
            decoded = base64.b64decode(cand, validate=True).decode("utf-8", errors="ignore")
            # If the decoded string is largely printable ASCII and words
            if len(decoded) > 8 and any(c.isalpha() for c in decoded):
                decoded_snippets.append(decoded)
                found_suspicious = True
        except Exception:
            continue
            
    if found_suspicious:
        return True, " | ".join(decoded_snippets)
    return False, ""
