"""Expected domain errors for PlanStep handling preparation."""


class PlanHandlingError(ValueError):
    """Base class for rejected PlanStep handling preparation data."""


class PlanHandlingInvariantError(PlanHandlingError):
    """Inputs or a result contradict Plan handling invariants."""


class InvalidControlDecisionKindError(PlanHandlingError):
    """Preparation received a decision other than STEP_SELECTED."""


class UnknownSelectedPlanStepError(PlanHandlingError):
    """The selected step does not exist in the supplied Plan."""


class SelectedStepNotReadyError(PlanHandlingError):
    """The selected step is no longer structurally READY."""


class SpecificationStepMismatchError(PlanHandlingError):
    """A specification belongs to a different PlanStep."""


class SpecificationKindMismatchError(PlanHandlingError):
    """A specification contradicts the PlanStep handling kind."""


class UnexpectedStepHandlingSpecificationError(PlanHandlingError):
    """A specification attempts to override an unspecified PlanStep."""


class StepHandlingPreparationIdentityError(PlanHandlingError):
    """A preparation result belongs to another Plan or PlanRun."""


class PreparationPlanIdentityError(StepHandlingPreparationIdentityError):
    """A preparation result references a different Plan."""


class PreparationRunIdentityError(StepHandlingPreparationIdentityError):
    """A preparation result references a different PlanRun."""


class StaleStepHandlingPreparationError(PlanHandlingError):
    """A result was prepared from a different PlanRun revision."""
