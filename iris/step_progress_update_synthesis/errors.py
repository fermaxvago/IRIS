"""Domain errors for StepProgressUpdate synthesis."""


class StepProgressUpdateSynthesisError(ValueError):
    """Base class for rejected StepProgressUpdate synthesis operations."""


class NonActionableTransitionDecisionError(StepProgressUpdateSynthesisError):
    """A valid transition decision does not request a state change."""


class TransitionAssessmentBindingError(StepProgressUpdateSynthesisError):
    """The supplied assessment cannot support the transition decision."""


class StepProgressUpdateGenerationError(StepProgressUpdateSynthesisError):
    """An injected update-ID or clock service failed its contract."""
