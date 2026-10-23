"""
ReplayAuditService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..config.settings import Settings
from ..domain.models import AuditEntry, ReplayRecord
from ..events import EventPublisher, ReplayVerified
from ..fingerprint import FingerprintMismatchError, compute_fingerprint, verify_fingerprint
from ..repositories.audit_repository import AuditRepository
from ..repositories.replay_repository import ReplayRepository


class ReplayAuditService:
    """
    Records replay-safety proofs and immutable audit trail entries.
    In strict replay mode, re-running an engine against the same input
    fingerprint MUST reproduce the same output fingerprint or an error
    is raised.
    """

    def __init__(self, replay_repository: ReplayRepository, audit_repository: AuditRepository,
                 settings: Settings, publisher: EventPublisher) -> None:
        self._replay_repository = replay_repository
        self._audit_repository = audit_repository
        self._settings = settings
        self._publisher = publisher

    def record_replay(self, subject_type: str, subject_key: str, input_payload: Mapping[str, Any],
                       output_payload: Mapping[str, Any], engine_name: str, engine_version: str) -> ReplayRecord:
        input_fp = compute_fingerprint(input_payload)
        output_fp = compute_fingerprint(output_payload)

        if self._settings.replay_strict_mode:
            previous = self._replay_repository.find_by_input_fingerprint(input_fp)
            if previous is not None:
                try:
                    verify_fingerprint(output_payload, previous.output_fingerprint)
                except FingerprintMismatchError:
                    raise

        record = ReplayRecord(
            id=None, subject_type=subject_type, subject_key=subject_key,
            input_fingerprint=input_fp, output_fingerprint=output_fp,
            engine_name=engine_name, engine_version=engine_version,
        )
        stored = self._replay_repository.add(record)

        self._publisher.publish(ReplayVerified(
            subject_key=subject_key, fingerprint=output_fp,
            payload={"engine_name": engine_name, "engine_version": engine_version},
        ))
        return stored

    def append_audit(self, event_type: str, subject_type: str, subject_key: str,
                      payload: Mapping[str, Any]) -> AuditEntry:
        fp = compute_fingerprint({"event_type": event_type, "subject_type": subject_type,
                                   "subject_key": subject_key, "payload": dict(payload)})
        entry = AuditEntry(
            id=None, event_type=event_type, subject_type=subject_type, subject_key=subject_key,
            fingerprint=fp, payload=dict(payload),
        )
        return self._audit_repository.add(entry)
