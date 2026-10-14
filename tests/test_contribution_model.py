from app.models import Contribution
from app.models.enums import ContributionStatus


def test_mark_completed_is_idempotent_when_already_completed():
    c = Contribution(status=ContributionStatus.COMPLETED)
    c.mark_completed()  # ne doit toucher ni le projet ni la base
    assert c.status == ContributionStatus.COMPLETED


def test_mark_refunded_is_idempotent_when_already_refunded():
    c = Contribution(status=ContributionStatus.REFUNDED)
    c.mark_refunded()
    assert c.status == ContributionStatus.REFUNDED
    assert c.refunded_at is None
