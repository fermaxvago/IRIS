"""Domain errors for Goal and Planning contracts."""


class PlanningError(ValueError):
    """Base class for expected Planning contract errors."""


class PlanValidationError(PlanningError):
    """A Plan violates identity or dependency-graph invariants."""


class DuplicatePlanningRuleError(PlanningError):
    """Two deterministic rules claim the same normalized objective."""
