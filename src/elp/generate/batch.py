"""Bounded, recoverable, deterministic batch runner with SQLite checkpoints."""

import asyncio
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from elp.generate import generate_draft
from elp.generate.engine import PROMPT_VERSION, SYSTEM_PROMPT
from elp.ground.injection import screen_input
from elp.ground.verify import verify_draft
from elp.llm.offline import DeterministicClient
from elp.policy import PolicyConfig
from elp.render import render_description
from elp.rules import check_listing, trim_title
from elp.schema import InputRow, Listing, ListingMeta


@dataclass(frozen=True)
class BatchSummary:
    total: int
    processed: int
    cached: int
    success: int
    warning: int
    failed: int
    output: Path
    failures: Path


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Checkpoints:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS rows (
                row_index INTEGER PRIMARY KEY,
                row_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            )"""
        )
        self.conn.commit()

    def lookup(self, index: int, row_hash: str) -> tuple[str, dict[str, Any]] | None:
        row = self.conn.execute(
            "SELECT status,payload FROM rows WHERE row_index=? AND row_hash=?",
            (index, row_hash),
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def store(self, index: int, row_hash: str, status: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO rows(row_index,row_hash,status,payload) VALUES(?,?,?,?)
            ON CONFLICT(row_index) DO UPDATE SET
            row_hash=excluded.row_hash, status=excluded.status, payload=excluded.payload""",
            (index, row_hash, status, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def export(self, output: Path, failures: Path) -> tuple[int, int, int]:
        output.parent.mkdir(parents=True, exist_ok=True)
        failures.parent.mkdir(parents=True, exist_ok=True)
        ok = warn = failed = 0
        tmp_output = output.with_suffix(output.suffix + ".tmp")
        tmp_failed = failures.with_suffix(failures.suffix + ".tmp")
        try:
            with (
                tmp_output.open("w", encoding="utf-8") as accepted,
                tmp_failed.open("w", encoding="utf-8") as rejects,
            ):
                for status, payload in self.conn.execute(
                    "SELECT status,payload FROM rows ORDER BY row_index"
                ):
                    if status == "failed":
                        failed += 1
                        rejects.write(payload + "\n")
                    elif status == "ok":
                        ok += 1
                        accepted.write(payload + "\n")
                    else:
                        warn += 1
                        accepted.write(payload + "\n")
            tmp_output.replace(output)
            tmp_failed.replace(failures)
        finally:
            tmp_output.unlink(missing_ok=True)
            tmp_failed.unlink(missing_ok=True)
        return ok, warn, failed

    def close(self) -> None:
        self.conn.close()


def _generate(row_data: dict[str, Any], policy: PolicyConfig, run_id: str) -> dict[str, Any]:
    """One row; returns a serializable result. All model operations are offline in M7."""
    row = InputRow.model_validate(row_data)
    guard = screen_input(row)
    if guard.blocked:
        raise ValueError("source_prompt_injection_blocked")
    draft_result = asyncio.run(generate_draft(guard.sanitized, DeterministicClient()))
    if draft_result.draft is None or draft_result.response is None:
        raise ValueError("generation_failed: " + str(draft_result.error))
    draft = draft_result.draft
    title, truncated = trim_title(draft.title, 80)
    if truncated:
        draft = draft.model_copy(update={"title": title})
    issues = check_listing(draft, guard.sanitized, policy)
    grounded = verify_draft(guard.sanitized, draft)
    if truncated:
        draft.warnings.append("Title truncated to 80 characters")
    if guard.flagged_fields:
        draft.warnings.append("Untrusted supplier instructions were removed")
    if any(violation.severity == "error" for violation in issues):
        raise ValueError(
            "compliance_error:"
            + ",".join(issue.code for issue in issues if issue.severity == "error")
        )
    if grounded.ungrounded_claims:
        raise ValueError("ungrounded_claim:" + ";".join(grounded.ungrounded_claims)[:400])
    warnings = draft.warnings + [
        violation.code for violation in issues if violation.severity == "warn"
    ]
    listing = Listing(
        sku=row.sku,
        **draft.model_dump(exclude={"warnings", "provenance"}),
        warnings=warnings,
        provenance=grounded.provenance,
        description_html=render_description(draft, guard.sanitized),
        meta=ListingMeta(
            model=draft_result.response.model,
            prompt_version=PROMPT_VERSION,
            rules_version=policy.version,
            run_id=run_id,
            tokens_input=draft_result.response.input_tokens,
            tokens_output=draft_result.response.output_tokens,
            grounding_score=grounded.score,
            prompt_hash=_hash(SYSTEM_PROMPT),
        ),
        status="warn" if warnings else "ok",
        violations=[v.to_dict() for v in issues],
    )
    return listing.model_dump(mode="json")


async def run_batch(
    input_path: Path,
    state_path: Path,
    output_path: Path,
    failures_path: Path,
    policy: PolicyConfig,
    *,
    run_id: str = "offline",
    concurrency: int = 4,
    dry_run: bool = False,
) -> BatchSummary:
    if concurrency < 1 or concurrency > 64:
        raise ValueError("concurrency must be between 1 and 64")
    if dry_run:
        total = sum(1 for line in input_path.open(encoding="utf-8") if line.strip())
        return BatchSummary(total, 0, 0, 0, 0, 0, output_path, failures_path)
    lock_path = state_path.with_suffix(".lock")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Another run or stale lock exists at {lock_path}; inspect before deleting"
        ) from exc
    os.close(lock_fd)
    checkpoint = Checkpoints(state_path)
    total = processed = cached = 0
    semaphore = asyncio.Semaphore(concurrency)
    tasks: set[asyncio.Task[None]] = set()

    async def one(index: int, record: str, signature: str) -> None:
        nonlocal processed
        async with semaphore:
            try:
                parsed = json.loads(record)
                payload = await asyncio.to_thread(_generate, parsed, policy, run_id)
                status = str(payload["status"])
            except (ValueError, TypeError, KeyError) as exc:
                status = "failed"
                payload = {"row_index": index, "status": status, "reason": str(exc)[:500]}
            checkpoint.store(index, signature, status, payload)
            processed += 1

    try:
        with input_path.open(encoding="utf-8") as stream:
            for index, record in enumerate(stream):
                if not record.strip():
                    continue
                total += 1
                signature = _hash(record + policy.version + PROMPT_VERSION + SYSTEM_PROMPT)
                if checkpoint.lookup(index, signature):
                    cached += 1
                    continue
                task = asyncio.create_task(one(index, record, signature))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
                if len(tasks) >= concurrency * 4:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if tasks:
                await asyncio.gather(*tasks)
        ok, warnings, failed = checkpoint.export(output_path, failures_path)
        return BatchSummary(
            total, processed, cached, ok, warnings, failed, output_path, failures_path
        )
    finally:
        checkpoint.close()
        lock_path.unlink(missing_ok=True)
