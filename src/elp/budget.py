"""Fail-closed, cross-process SQLite cost reservations in integer USD micro-units."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path

_MICROS = Decimal("1000000")


class BudgetExceededError(ValueError):
    """Requested charge exceeds a configured run/day budget."""


class ReservationError(ValueError):
    """Reservation does not exist or is no longer pending."""


def _money(value: Decimal | str | int) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("USD amount must be a finite number") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("USD amount must be finite and non-negative")
    return amount


def _charge_micros(value: Decimal | str | int) -> int:
    return int((_money(value) * _MICROS).to_integral_value(rounding=ROUND_CEILING))


def _cap_micros(value: Decimal | str | int) -> int:
    return int((_money(value) * _MICROS).to_integral_value(rounding=ROUND_FLOOR))


def estimate_max_usd(
    input_tokens: int,
    max_output_tokens: int,
    input_per_million: Decimal,
    output_per_million: Decimal,
) -> Decimal:
    """Upper bound to reserve *before* an API call, assuming bounded token use."""
    if input_tokens < 0 or max_output_tokens < 0:
        raise ValueError("token counts cannot be negative")
    return (
        Decimal(input_tokens) * _money(input_per_million)
        + Decimal(max_output_tokens) * _money(output_per_million)
    ) / _MICROS


class BudgetLedger:
    """SQLite transactions guarantee that concurrent reservations respect both caps."""

    def __init__(self, path: Path, run_cap_usd: Decimal, day_cap_usd: Decimal) -> None:
        self.path = path
        self.run_limit = _cap_micros(run_cap_usd)
        self.day_limit = _cap_micros(day_cap_usd)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS reservations (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    reserved_micro INTEGER NOT NULL CHECK (reserved_micro >= 0),
                    actual_micro INTEGER,
                    state TEXT NOT NULL CHECK (state IN ('held','settled','cancelled'))
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_budget_run ON reservations(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_budget_day ON reservations(day_utc)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    @staticmethod
    def _date(now: datetime | None) -> str:
        current = now or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("budget timestamp must be timezone-aware")
        return current.astimezone(UTC).date().isoformat()

    @staticmethod
    def _used(conn: sqlite3.Connection, key: str, value: str) -> int:
        if key not in {"run_id", "day_utc"}:
            raise ValueError("invalid budget dimension")
        row = conn.execute(
            f"""SELECT COALESCE(SUM(CASE WHEN state = 'held' THEN reserved_micro
                WHEN state = 'settled' THEN actual_micro ELSE 0 END),0)
                FROM reservations WHERE {key} = ?""",
            (value,),
        ).fetchone()
        return int(row[0])

    def reserve(
        self,
        request_id: str,
        run_id: str,
        worst_case_usd: Decimal,
        now: datetime | None = None,
    ) -> None:
        if not request_id or not run_id:
            raise ValueError("request ID and run ID are required")
        charge = _charge_micros(worst_case_usd)
        day = self._date(now)
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if conn.execute(
                    "SELECT 1 FROM reservations WHERE request_id = ?", (request_id,)
                ).fetchone():
                    raise ReservationError("duplicate request ID; existing reservation preserved")
                if self._used(conn, "run_id", run_id) + charge > self.run_limit:
                    raise BudgetExceededError("per-run cost cap exceeded; no call permitted")
                if self._used(conn, "day_utc", day) + charge > self.day_limit:
                    raise BudgetExceededError("daily cost cap exceeded; no call permitted")
                conn.execute(
                    """INSERT INTO reservations
                    (request_id,run_id,day_utc,reserved_micro,actual_micro,state)
                    VALUES (?,?,?,?,NULL,'held')""",
                    (request_id, run_id, day, charge),
                )
                conn.commit()
            except (sqlite3.Error, ValueError):
                conn.rollback()
                raise

    def settle(self, request_id: str, actual_usd: Decimal) -> None:
        charge = _charge_micros(actual_usd)
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT reserved_micro,state FROM reservations WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if row is None or row[1] != "held":
                    raise ReservationError("cannot settle missing/non-held reservation")
                if charge > int(row[0]):
                    raise BudgetExceededError("actual charge exceeds reserved worst-case amount")
                conn.execute(
                    "UPDATE reservations SET actual_micro=?,state='settled' WHERE request_id=?",
                    (charge, request_id),
                )
                conn.commit()
            except (sqlite3.Error, ValueError):
                conn.rollback()
                raise

    def cancel(self, request_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT state FROM reservations WHERE request_id=?", (request_id,)
                ).fetchone()
                if row is None or row[0] != "held":
                    raise ReservationError("cannot cancel missing/non-held reservation")
                conn.execute(
                    "UPDATE reservations SET state='cancelled' WHERE request_id=?", (request_id,)
                )
                conn.commit()
            except (sqlite3.Error, ValueError):
                conn.rollback()
                raise

    def usage_micro(self, run_id: str, now: datetime | None = None) -> tuple[int, int]:
        with closing(self._connect()) as conn:
            return (
                self._used(conn, "run_id", run_id),
                self._used(conn, "day_utc", self._date(now)),
            )
