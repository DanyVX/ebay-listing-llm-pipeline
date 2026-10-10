from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from elp.budget import (
    BudgetExceededError,
    BudgetLedger,
    ReservationError,
    estimate_max_usd,
)


@pytest.fixture
def ledger(tmp_path):
    return BudgetLedger(tmp_path / "ledger.sqlite3", Decimal("1"), Decimal("1.5"))


def test_paid_calls_denied_by_default(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.db", Decimal("0"), Decimal("0"))
    with pytest.raises(BudgetExceededError):
        ledger.reserve("id", "run", Decimal("0.000001"))


def test_free_fixture_is_allowed_by_zero_cap(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.db", Decimal("0"), Decimal("0"))
    ledger.reserve("fixture", "r", Decimal("0"))
    ledger.settle("fixture", Decimal("0"))
    assert ledger.usage_micro("r")[0] == 0


def test_reservations_enforce_run_cap(ledger):
    ledger.reserve("a", "r", Decimal("0.75"))
    with pytest.raises(BudgetExceededError, match="per-run"):
        ledger.reserve("b", "r", Decimal("0.26"))
    assert ledger.usage_micro("r")[0] == 750000


def test_settlement_releases_unused_reserved_amount(ledger):
    ledger.reserve("a", "r", Decimal("0.9"))
    ledger.settle("a", Decimal("0.1"))
    ledger.reserve("b", "r", Decimal("0.9"))
    assert ledger.usage_micro("r")[0] == 1000000


def test_settlement_cannot_exceed_reservation(ledger):
    ledger.reserve("a", "r", Decimal("0.1"))
    with pytest.raises(BudgetExceededError, match="reserved"):
        ledger.settle("a", Decimal("0.2"))
    assert ledger.usage_micro("r")[0] == 100000


def test_day_cap_across_multiple_runs(ledger):
    ledger.reserve("a", "r1", Decimal("0.9"))
    ledger.reserve("b", "r2", Decimal("0.6"))
    with pytest.raises(BudgetExceededError, match="daily"):
        ledger.reserve("c", "r3", Decimal("0.01"))


def test_day_rollover_keeps_run_cap(ledger):
    d1 = datetime(2026, 10, 10, tzinfo=timezone.utc)
    ledger.reserve("a", "r1", Decimal("0.9"), d1)
    ledger.reserve("b", "r2", Decimal("0.9"), d1 + timedelta(days=1))
    assert ledger.usage_micro("r2", d1 + timedelta(days=1)) == (900000, 900000)


def test_cancel_releases_capacity(ledger):
    ledger.reserve("a", "r", Decimal("1"))
    ledger.cancel("a")
    ledger.reserve("b", "r", Decimal("1"))
    assert ledger.usage_micro("r")[0] == 1000000


def test_request_ids_never_reused(ledger):
    ledger.reserve("a", "r", Decimal("0"))
    with pytest.raises(ReservationError, match="duplicate"):
        ledger.reserve("a", "r", Decimal("0"))


def test_double_settlement_disallowed(ledger):
    ledger.reserve("a", "r", Decimal("0"))
    ledger.settle("a", Decimal("0"))
    with pytest.raises(ReservationError):
        ledger.settle("a", Decimal("0"))


def test_fractional_micro_rounds_up_and_caps_round_down(ledger):
    ledger.reserve("a", "r", Decimal("0.0000001"))
    assert ledger.usage_micro("r")[0] == 1


def test_validation_rejects_invalid_values(tmp_path):
    with pytest.raises(ValueError):
        BudgetLedger(tmp_path / "db", Decimal("-1"), Decimal("1"))
    ledger = BudgetLedger(tmp_path / "db2", Decimal("1"), Decimal("1"))
    with pytest.raises(ValueError):
        ledger.reserve("bad", "r", Decimal("NaN"))
    with pytest.raises(ValueError):
        ledger.reserve("bad", "r", Decimal("-1"))
    with pytest.raises(ValueError):
        ledger.reserve("bad", "r", Decimal("0"), datetime(2026, 1, 1))


def test_pricing_estimator_uses_bound():
    assert estimate_max_usd(1000, 2000, Decimal("1"), Decimal("3")) == Decimal("0.007")
    with pytest.raises(ValueError):
        estimate_max_usd(-1, 1, Decimal("1"), Decimal("1"))
