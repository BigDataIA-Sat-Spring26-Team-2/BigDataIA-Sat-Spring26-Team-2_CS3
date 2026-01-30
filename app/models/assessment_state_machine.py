from typing import Dict, Set
from app.models.enums import AssessmentStatus

def build_allowed_transitions() -> Dict[AssessmentStatus, Set[AssessmentStatus]]:
    """
    Builds a transition map using ONLY the enum values that exist.
    This avoids crashes if some statuses are not defined in the enum.
    """
    def s(name: str):
        return getattr(AssessmentStatus, name, None)

    DRAFT = s("DRAFT")
    SUBMITTED = s("SUBMITTED")
    IN_REVIEW = s("IN_REVIEW")
    COMPLETED = s("COMPLETED")
    REJECTED = s("REJECTED")

    transitions: Dict[AssessmentStatus, Set[AssessmentStatus]] = {}

    # Minimal always-safe rule: DRAFT can go to SUBMITTED (if both exist)
    if DRAFT and SUBMITTED:
        transitions[DRAFT] = {SUBMITTED}

    # If these exist, wire them up
    if SUBMITTED:
        nxt = set()
        if IN_REVIEW:
            nxt.add(IN_REVIEW)
        if COMPLETED:
            nxt.add(COMPLETED)
        if REJECTED:
            nxt.add(REJECTED)
        if nxt:
            transitions[SUBMITTED] = nxt

    if IN_REVIEW:
        nxt = set()
        if COMPLETED:
            nxt.add(COMPLETED)
        if REJECTED:
            nxt.add(REJECTED)
        if nxt:
            transitions[IN_REVIEW] = nxt

    # Terminal states if present
    if COMPLETED:
        transitions.setdefault(COMPLETED, set())
    if REJECTED:
        transitions.setdefault(REJECTED, set())

    # If enum only has DRAFT (or tiny set), transitions might be empty.
    # That's still a valid "state machine": no transitions allowed.
    return transitions
