"""Small presentation helpers shared by the API/UI layer. Kept separate from
services/ because these are formatting concerns, not business logic."""

DECISION_LABELS = {
    "STRONG_APPLY": "Strong Apply",
    "APPLY_REVIEW_GAPS": "Apply / Review Gaps",
    "CONSIDER": "Consider",
    "LOW_MATCH": "Low Match",
}

def decision_label(decision_bucket: str) -> str:
    return DECISION_LABELS.get(decision_bucket, decision_bucket)
