"""Local syntax flagging for the Corporate Integrity Scorecard (no model required)."""
import math
import re

# category -> (weight, regex)
RED_FLAG_PATTERNS = {
    "Going concern doubt": (10, r"substantial doubt|going concern"),
    "Material weakness / controls": (9, r"material weakness|ineffective internal control|significant deficienc"),
    "Restatement / accounting errors": (9, r"restate(?:d|ment)|non-reliance|accounting error"),
    "Litigation / investigations": (7, r"class action|subpoena|SEC investigation|enforcement action|litigation|lawsuit"),
    "Related-party dealings": (6, r"related[- ]party|related person transaction"),
    "Debt covenant stress": (7, r"covenant (?:breach|violation|waiver)|default|forbearance"),
    "Auditor concerns": (8, r"auditor resign|dismiss(?:ed)? (?:our )?auditor|adverse opinion|qualified opinion|disclaimer of opinion"),
    "Hedging language": (3, r"may not be able|no assurance|cannot guarantee|could adversely|uncertain(?:ty|ties)"),
    "Non-GAAP reliance": (4, r"non-gaap|adjusted ebitda|as adjusted|pro forma"),
    "Impairment / write-downs": (6, r"impairment|write-?down|write-?off|goodwill charge"),
}


def scan_red_flags(text: str) -> dict:
    """Return {score, flags:[{flag, weight, mentions}]}; score is 0-100, higher = cleaner."""
    n_words = max(len(text.split()), 1)
    flags = [
        {"flag": name, "weight": w, "mentions": len(re.findall(p, text, flags=re.IGNORECASE))}
        for name, (w, p) in RED_FLAG_PATTERNS.items()
    ]
    # Density is log-damped so long filings aren't over-penalized.
    penalty = sum(f["weight"] * math.log1p(f["mentions"] / n_words * 10_000) for f in flags)
    return {"score": round(max(0.0, 100 - penalty * 4), 1), "flags": flags}
