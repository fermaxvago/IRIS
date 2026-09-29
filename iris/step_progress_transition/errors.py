"""Domain errors for StepProgress transition decisions."""


class StepProgressTransitionError(ValueError):
    """Base class for rejected transition-decision operations."""


class TransitionAssessmentIdentityError(StepProgressTransitionError):
    """An assessment has incompatible Plan, Run, step, or revision lineage."""


class TransitionAssessmentEvidenceError(StepProgressTransitionError):
    """Assessment evidence contradicts the current canonical Run lineage."""


class TransitionPolicyContractViolationError(StepProgressTransitionError):
    """A transition policy has invalid provenance or returned an invalid result."""


class TransitionPolicyExecutionError(StepProgressTransitionError):
    """A transition policy failed while making its operational decision."""


class TransitionDecisionIdentityError(StepProgressTransitionError):
    """A transition decision has invalid identity, state, or time lineage."""


class StaleStepProgressTransitionDecisionError(TransitionDecisionIdentityError):
    """A transition decision does not observe the current PlanRun revision."""


class TransitionDecisionGenerationError(StepProgressTransitionError):
    """An injected clock or decision-ID service failed its contract."""
