from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REFUSE = "REFUSE"

class SecurityCategory(str, Enum):
    BENIGN = "BENIGN"
    OFF_TOPIC = "OFF_TOPIC"
    JAILBREAK = "JAILBREAK"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    CYBER_ABUSE = "CYBER_ABUSE"
    POLICY_VIOLATION = "POLICY_VIOLATION"

class SecurityDecision(BaseModel):
    decision: Decision
    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    detectors: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    safe_response: Optional[str] = None
