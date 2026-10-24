"""Two consent-gated local readings; no context, model, or persistent telemetry.

The CLI is the trusted caller responsible for obtaining human authorization.
This process-local contract is not authentication or physical-device identity.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import monotonic

from iris.capabilities import (
    SYSTEM_STATUS_CAPABILITY_ID,
    CapabilityInput,
    CapabilityRuntime,
    SystemResourceObservation,
    create_default_runtime,
)
from iris.intelligence.conversation import ConversationBusyError, ConversationSession

BASELINE_LIFETIME_SECONDS = 600


class ResourceComparisonError(ValueError):
    """An observation or comparison cannot be accepted."""


class ResourceCaptureError(ResourceComparisonError):
    """The canonical capability did not produce a complete reading."""


class ResourceProvenanceError(ResourceCaptureError):
    """The registered capability returned the wrong identity."""


class ResourceCapacityChangedError(ResourceComparisonError):
    """The two readings do not describe the same total RAM capacity."""


@dataclass(frozen=True, slots=True)
class ResourceDelta:
    """Difference between two readings, without trend or cause inference."""

    baseline: SystemResourceObservation
    current: SystemResourceObservation
    ram_delta_gib: float
    cpu_delta_pp: float


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ResourceComparisonError(f"{name} must be timezone-aware UTC")
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError) as exc:
        raise ResourceComparisonError(f"{name} has invalid UTC offset") from exc
    if offset is None or offset.total_seconds() != 0:
        raise ResourceComparisonError(f"{name} must be timezone-aware UTC")
    return value


def _canonical_observation(
    value: object, *, now: datetime
) -> SystemResourceObservation:
    if type(value) is not SystemResourceObservation:
        raise ResourceComparisonError("system.status observation is not canonical")
    try:
        copy = replace(value)
    except (TypeError, ValueError) as exc:
        raise ResourceComparisonError("system.status observation is malformed") from exc
    if copy != value or not value.complete:
        raise ResourceComparisonError("system.status observation is incomplete")
    if _utc(value.captured_at, "captured_at") > now:
        raise ResourceComparisonError("system.status observation is future-dated")
    return value


def compare_resource_observations(
    baseline: SystemResourceObservation,
    current: SystemResourceObservation,
    *,
    now: datetime,
) -> ResourceDelta:
    """Pure validation and arithmetic over two canonical observations."""

    checked_now = _utc(now, "validation time")
    first = _canonical_observation(baseline, now=checked_now)
    second = _canonical_observation(current, now=checked_now)
    if second.captured_at <= first.captured_at:
        raise ResourceComparisonError("observation timestamps are not increasing")
    if second.ram_total_gb != first.ram_total_gb:
        raise ResourceCapacityChangedError("total RAM capacity changed")
    assert first.cpu_percent is not None and second.cpu_percent is not None
    assert first.ram_used_gb is not None and second.ram_used_gb is not None
    return ResourceDelta(
        baseline=first,
        current=second,
        ram_delta_gib=second.ram_used_gb - first.ram_used_gb,
        cpu_delta_pp=second.cpu_percent - first.cpu_percent,
    )


@dataclass(frozen=True, slots=True)
class ComparisonSessionStamp:
    """Session identity at the instant before the CLI asks for consent."""

    session_id: str
    generation: int


@dataclass(frozen=True, slots=True)
class _RetainedBaseline:
    observation: SystemResourceObservation
    stamp: ComparisonSessionStamp
    retained_at: float
    capability_id: str = SYSTEM_STATUS_CAPABILITY_ID


class LocalResourceComparison:
    """Own one ephemeral baseline for exactly one chat invocation."""

    def __init__(
        self,
        session: ConversationSession,
        *,
        capability_runtime: CapabilityRuntime | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
        utc_clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(session, ConversationSession):
            raise TypeError("session must be ConversationSession")
        self._session = session
        self._capabilities = capability_runtime or create_default_runtime()
        self._monotonic_clock = monotonic_clock
        self._utc_clock = utc_clock or (lambda: datetime.now(UTC))
        self._baseline: _RetainedBaseline | None = None

    def stamp(self) -> ComparisonSessionStamp:
        """Read session identity without treating revision as baseline identity."""

        session_id = self._session.session_id
        try:
            snapshot = self._session.diagnostic_snapshot()
        except ConversationBusyError as exc:
            raise ResourceComparisonError("conversation is busy") from exc
        if self._session.session_id != session_id:
            raise ResourceComparisonError("conversation identity changed")
        return ComparisonSessionStamp(session_id, snapshot.generation)

    def _require_stamp(self, expected: ComparisonSessionStamp) -> None:
        if type(expected) is not ComparisonSessionStamp or self.stamp() != expected:
            self._baseline = None
            raise ResourceComparisonError("conversation identity changed")

    def _monotonic_now(self) -> float:
        try:
            value = self._monotonic_clock()
        except Exception as exc:
            self._baseline = None
            raise ResourceComparisonError("monotonic clock unavailable") from exc
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            self._baseline = None
            raise ResourceComparisonError("monotonic clock is invalid")
        return float(value)

    def _utc_now(self) -> datetime:
        try:
            return _utc(self._utc_clock(), "validation time")
        except Exception as exc:
            self._baseline = None
            raise ResourceComparisonError("UTC validation clock is invalid") from exc

    def _valid_baseline(self) -> _RetainedBaseline | None:
        baseline = self._baseline
        if baseline is None:
            return None
        if baseline.capability_id != SYSTEM_STATUS_CAPABILITY_ID:
            self._baseline = None
            return None
        try:
            if self.stamp() != baseline.stamp:
                self._baseline = None
                return None
            age = self._monotonic_now() - baseline.retained_at
            if age < 0:
                raise ResourceComparisonError("monotonic clock regressed")
            if age >= BASELINE_LIFETIME_SECONDS:
                self._baseline = None
                return None
            _canonical_observation(baseline.observation, now=self._utc_now())
        except ResourceComparisonError:
            self._baseline = None
            raise
        return baseline

    def status(self) -> bool:
        """Inspect validity without observation or inference."""

        return self._valid_baseline() is not None

    def cancel(self) -> None:
        """Discard the sole retained reading."""

        self._baseline = None

    def _capture(self) -> SystemResourceObservation:
        try:
            result = self._capabilities.execute(
                SYSTEM_STATUS_CAPABILITY_ID,
                CapabilityInput(payload={"output_mode": "structured"}),
            )
        except ValueError as exc:
            if str(exc) == "capability result identifier does not match the invocation":
                raise ResourceProvenanceError(
                    "system.status provenance mismatch"
                ) from exc
            raise ResourceCaptureError("system.status capture failed") from exc
        except Exception as exc:
            raise ResourceCaptureError("system.status capture failed") from exc
        if result.capability_id != SYSTEM_STATUS_CAPABILITY_ID:
            raise ResourceProvenanceError("system.status provenance mismatch")
        if not result.success:
            raise ResourceCaptureError("system.status capture failed")
        try:
            return _canonical_observation(result.output, now=self._utc_now())
        except ResourceComparisonError as exc:
            raise ResourceCaptureError(str(exc)) from exc

    def establish(
        self, approved_stamp: ComparisonSessionStamp
    ) -> SystemResourceObservation:
        """Called only after the trusted CLI authorizes capture and retention."""

        self._require_stamp(approved_stamp)
        self._valid_baseline()
        try:
            candidate = self._capture()
            self._require_stamp(approved_stamp)
            retained_at = self._monotonic_now()
            self._require_stamp(approved_stamp)
        except ResourceProvenanceError:
            self._baseline = None
            raise
        except ResourceComparisonError:
            self._valid_baseline()  # Expired prior state is never preserved.
            raise
        self._baseline = _RetainedBaseline(candidate, approved_stamp, retained_at)
        return candidate

    def compare_now(self, approved_stamp: ComparisonSessionStamp) -> ResourceDelta:
        """Capture once, validate again, and consume only on a valid comparison."""

        self._require_stamp(approved_stamp)
        baseline = self._valid_baseline()
        if baseline is None:
            raise ResourceComparisonError("no active baseline")
        try:
            current = self._capture()
        except ResourceProvenanceError:
            self._baseline = None
            raise
        except ResourceComparisonError:
            self._valid_baseline()  # Preserve only a still-valid baseline.
            raise
        self._require_stamp(approved_stamp)
        if self._valid_baseline() is not baseline:
            raise ResourceComparisonError("baseline expired during capture")
        try:
            delta = compare_resource_observations(
                baseline.observation, current, now=self._utc_now()
            )
        except ResourceCapacityChangedError:
            self._baseline = None
            raise
        self._baseline = None  # Consume before any caller presentation.
        return delta
