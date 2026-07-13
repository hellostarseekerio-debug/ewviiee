"""Poster Archive status lifecycle: the allowed-transition graph, the
minimum role required for each transition, and the mapping back onto the
legacy `approval_status` field kept in sync during its deprecation cycle
(see PosterStatus's docstring in app/core/models.py).

Lifecycle: draft -> pending_review -> approved -> published -> archived,
with rejected/resubmit branches. Diagrammed here rather than left implicit
in a dict, since this *is* the product-facing behavior, not an
implementation detail:

    draft ------------------> pending_review
                                |    ^  |
                      approve --+    |  +-- reject
                                v    |  v
                            approved-+  rejected
                                |          |
                     publish -- +          +-- (resubmit)
                                v
                            published
                                |
                       archive -+
                                v
                            archived (terminal)
"""
from __future__ import annotations

from app.core.models import ApprovalStatus, PosterStatus, UserRole
from app.core.status_workflow import validate_transition

POSTER_STATUS_TRANSITIONS: dict[PosterStatus, set[PosterStatus]] = {
    PosterStatus.DRAFT: {PosterStatus.PENDING_REVIEW},
    PosterStatus.PENDING_REVIEW: {PosterStatus.APPROVED, PosterStatus.REJECTED, PosterStatus.DRAFT},
    PosterStatus.APPROVED: {PosterStatus.PUBLISHED, PosterStatus.PENDING_REVIEW},
    PosterStatus.PUBLISHED: {PosterStatus.ARCHIVED},
    PosterStatus.REJECTED: {PosterStatus.DRAFT, PosterStatus.PENDING_REVIEW},
    PosterStatus.ARCHIVED: set(),
}

# Only the review verdicts themselves (approve/reject) are gated at the
# Reviewer role - every other transition is an editing/operational action
# and uses the same Editor+ bar as creating/updating a poster record.
# Note _ROLE_RANK (app/core/security.py) ranks Reviewer *below* Editor, so
# "Reviewer+" here means "Reviewer, Editor, or Admin", matching the
# existing convention on Document approve/reject (app/api/routes/documents.py).
_REVIEW_VERDICT_STATUSES = {PosterStatus.APPROVED, PosterStatus.REJECTED}


def required_role_for_transition(new: PosterStatus) -> UserRole:
    """Minimum role needed to move a poster *to* `new`."""
    if new in _REVIEW_VERDICT_STATUSES:
        return UserRole.REVIEWER
    return UserRole.EDITOR


def validate_poster_transition(current: PosterStatus, new: PosterStatus, *, force: bool = False) -> None:
    validate_transition(current, new, POSTER_STATUS_TRANSITIONS, force=force)


def approval_status_for(status: PosterStatus) -> ApprovalStatus:
    """Keeps the legacy `approval_status` field meaningful while both
    columns coexist - anything still reading `approval_status` alone (an
    older report, a script) sees a value consistent with the new,
    richer `status`."""
    if status == PosterStatus.REJECTED:
        return ApprovalStatus.REJECTED
    if status in (PosterStatus.APPROVED, PosterStatus.PUBLISHED, PosterStatus.ARCHIVED):
        return ApprovalStatus.APPROVED
    return ApprovalStatus.PENDING
