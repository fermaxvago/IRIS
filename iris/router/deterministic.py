"""Initial deterministic Router for explicit terminal commands."""

from __future__ import annotations

from iris.core.request import Request
from iris.router.models import RouteDecision, RouteTarget

_COMMAND_ROUTES: dict[str, tuple[RouteTarget, str]] = {
    "estado": (
        RouteTarget.SYSTEM_STATUS,
        "recognized the system status command",
    ),
    "ayuda": (
        RouteTarget.CLI_HELP,
        "recognized the CLI help command",
    ),
    "salir": (
        RouteTarget.CLI_EXIT,
        "recognized the CLI exit command",
    ),
}


class DeterministicRouter:
    """Choose a destination using exact, inspectable command rules only."""

    def route(self, request: Request) -> RouteDecision:
        """Return a decision without invoking handlers or causing side effects."""

        normalized_content = request.content.strip().casefold()
        matched_route = _COMMAND_ROUTES.get(normalized_content)

        if matched_route is None:
            return RouteDecision(
                target=RouteTarget.UNKNOWN,
                reason="no deterministic routing rule matched",
                metadata={"normalized_content": normalized_content},
            )

        target, reason = matched_route
        return RouteDecision(
            target=target,
            reason=reason,
            metadata={"matched_command": normalized_content},
        )
