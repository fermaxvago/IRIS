"""Errors owned by bounded PlanRun progress advancement."""


class PlanRunProgressAdvancementError(ValueError):
    """Base error for WP023 composition invariants."""


class PlanRunProgressAdvanceInvariantError(PlanRunProgressAdvancementError):
    """The reducer/controller composition violated an advancement invariant."""
