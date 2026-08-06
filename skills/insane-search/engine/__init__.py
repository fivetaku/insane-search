"""insane-search engine — generic WAF-profile-based fetch chain.

No site-specific logic lives here. Site specifics belong to runtime hints or
observations, never to code. See `../SKILL.md` for the No-Site-Name Rule.
"""

from .validators import Verdict, ValidationResult, validate, CHALLENGE_MARKERS
from .waf_detector import detect
from .url_transforms import TRANSFORMS, apply_transform
from .fetch_chain import fetch, FetchResult, Attempt
from .content_safety import (
    BEGIN_UNTRUSTED_WEB_CONTENT,
    CONTENT_TRUST_UNTRUSTED_PUBLIC_WEB,
    END_UNTRUSTED_WEB_CONTENT,
    ContentSafetyReport,
    analyze_untrusted_content,
    wrap_untrusted_content,
)

__all__ = [
    "Verdict",
    "ValidationResult",
    "validate",
    "CHALLENGE_MARKERS",
    "detect",
    "TRANSFORMS",
    "apply_transform",
    "fetch",
    "FetchResult",
    "Attempt",
    "BEGIN_UNTRUSTED_WEB_CONTENT",
    "CONTENT_TRUST_UNTRUSTED_PUBLIC_WEB",
    "END_UNTRUSTED_WEB_CONTENT",
    "ContentSafetyReport",
    "analyze_untrusted_content",
    "wrap_untrusted_content",
]
