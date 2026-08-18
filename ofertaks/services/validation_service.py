"""Small independent-answer consensus for canonical product data quality."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from ofertaks.database.repository import Repository
from ofertaks.models.knowledge import (
    ADMIN,
    MATCH_CONFIRMED,
    ProductAlias,
    ValidationAnswer,
)
from ofertaks.normalization.product_normalizer import normalize_product_name


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    required_independent_confirmations: int = 3


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: str
    answer_count: int
    consensus_answer: str | None


class ValidationService:
    def __init__(self, repository: Repository, policy: ValidationPolicy | None = None):
        self.repository = repository
        self.policy = policy or ValidationPolicy()

    def submit(self, answer: ValidationAnswer) -> ValidationResult:
        self.repository.record_validation_answer(answer)
        return self.evaluate(answer.validation_task_id)

    def evaluate(self, task_id: int) -> ValidationResult:
        answers = self.repository.validation_answers(task_id)
        votes = Counter(row["answer"] for row in answers if row["answer"] not in {"NOT_SURE", "SKIP"})
        if len(votes) > 1:
            status, consensus = "NEEDS_REVIEW", None
        elif not votes:
            status, consensus = "OPEN", None
        else:
            consensus, count = votes.most_common(1)[0]
            if count < self.policy.required_independent_confirmations:
                status = "TENTATIVE"
            else:
                status = "REJECTED" if consensus == "NO" else "CONFIRMED"
        self.repository.set_validation_task_status(task_id, status)
        if status == "CONFIRMED":
            self._apply_confirmed_task(task_id, consensus)
        return ValidationResult(status, len(answers), consensus)

    def resolve_as_admin(self, task_id: int, contributor_id: str, answer: str) -> ValidationResult:
        self.repository.record_validation_answer(
            ValidationAnswer(
                id=None,
                validation_task_id=task_id,
                contributor_id=contributor_id,
                contributor_role=ADMIN,
                answer=answer,
                created_at=datetime.now(UTC),
            )
        )
        status = "CONFIRMED" if answer.upper() == "YES" else "REJECTED"
        self.repository.set_validation_task_status(task_id, status)
        if status == "CONFIRMED":
            self._apply_confirmed_task(task_id, answer.upper())
        return ValidationResult(status, len(self.repository.validation_answers(task_id)), answer.upper())

    def _apply_confirmed_task(self, task_id: int, answer: str | None) -> None:
        if answer != "YES":
            return
        tasks = [task for task in self.repository.list_validation_tasks("CONFIRMED", limit=500) if task["id"] == task_id]
        if not tasks:
            return
        task = tasks[0]
        raw_id, product_id = task.get("raw_observation_id"), task.get("candidate_product_id")
        if raw_id is None or product_id is None:
            return
        raw = next((row for row in self.repository.raw_observations() if row["id"] == raw_id), None)
        if not raw:
            return
        self.repository.link_raw_observation(raw_id, product_id, MATCH_CONFIRMED, 0.95)
        normalized = normalize_product_name(raw["raw_name"])
        self.repository.add_product_alias(
            ProductAlias(
                id=None,
                product_id=product_id,
                raw_name=raw["raw_name"],
                normalized_name=normalized.normalized_name,
                matching_status=MATCH_CONFIRMED,
                matching_confidence=0.95,
                store_id=raw.get("store_id"),
                merchant_id=raw.get("merchant_id"),
                chain_id=raw.get("chain_id"),
                source_context="HUMAN_VALIDATION",
                source_raw_observation_id=raw_id,
            )
        )
