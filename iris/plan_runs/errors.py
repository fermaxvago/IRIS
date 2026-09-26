"""Expected domain errors for immutable PlanRun state transitions."""


class PlanRunError(ValueError):
    """Base class for rejected PlanRun data and operations."""


class PlanRunInvariantError(PlanRunError):
    """A PlanRun snapshot violates its structural invariants."""


class PlanRunIdentityError(PlanRunError):
    """A Plan, Run, update, observation, or blocker identity does not match."""


class StalePlanRunUpdateError(PlanRunError):
    """An update expected a revision other than the current revision."""


class UnknownPlanStepError(PlanRunError):
    """An operation references a step that is not part of the Plan."""


class InvalidStepTransitionError(PlanRunError):
    """A requested StepProgress transition is not legal."""


class ForeignEvidenceError(PlanRunError):
    """Evidence is absent, belongs to another Run, or has incompatible scope."""


class InvalidBlockerOperationError(PlanRunError):
    """A blocker operation is incompatible with the referenced step or blocker."""


class DuplicateRunIdentityError(PlanRunError):
    """A Run contains or receives a duplicate observation or blocker identity."""
