"""Expected domain errors for one PlanRun control decision."""


class PlanControlError(ValueError):
    """Base class for rejected PlanRun control data and operations."""


class PlanControlInvariantError(PlanControlError):
    """Canonical PlanRun projections contradict control invariants."""


class PolicyContractViolationError(PlanControlError):
    """A StepSelectionPolicy returned a malformed or incompatible result."""


class UnknownSelectedStepError(PolicyContractViolationError):
    """A policy selected a step that does not exist in the observed Plan."""


class NonCandidateSelectedStepError(PolicyContractViolationError):
    """A policy selected a known step outside the READY candidate set."""


class ControlDecisionIdentityError(PlanControlError):
    """A decision does not belong to the supplied Plan or PlanRun."""


class PlanIdentityMismatchError(ControlDecisionIdentityError):
    """A decision references a different Plan."""


class RunIdentityMismatchError(ControlDecisionIdentityError):
    """A decision references a different PlanRun."""


class StaleControlDecisionError(PlanControlError):
    """A decision observed a revision other than the current Run revision."""
