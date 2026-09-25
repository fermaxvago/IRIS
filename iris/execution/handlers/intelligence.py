"""Adapter connecting orchestration to existing intelligence routing/runtime."""

from iris.execution.contracts import IntelligenceExecutor, IntelligenceRouteExecutor
from iris.execution.models import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
    IntelligenceExecutionInput,
)
from iris.intelligence import (
    IntelligenceRequest,
    IntelligenceRouteStatus,
    ModelNotFoundError,
    ModelUnavailableError,
    ProviderNotFoundError,
)
from iris.orchestrator import OrchestrationTarget


class IntelligenceExecutionHandler:
    """Route an existing IntelligenceNeed, invoke the selected runtime once."""

    target = OrchestrationTarget.INTELLIGENCE
    handler_reference = "intelligence.routing-runtime"

    def __init__(
        self,
        router: IntelligenceRouteExecutor,
        runtime: IntelligenceExecutor,
    ) -> None:
        self._router = router
        self._runtime = runtime

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        requirement = request.decision.requirement
        execution_input = request.execution_input
        if requirement is None or requirement.intelligence_need is None:
            raise ValueError("intelligence decision lacks IntelligenceNeed")
        if not isinstance(execution_input, IntelligenceExecutionInput):
            raise TypeError("intelligence handler requires IntelligenceExecutionInput")
        route = self._router.route(
            requirement.intelligence_need,
            execution_input.resources,
        )
        if route.status is IntelligenceRouteStatus.UNSATISFIED:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="intelligence_route_unsatisfied",
                    message="no intelligence resource satisfies the declared need",
                    details={"route_reason": route.reason.value},
                ),
                metadata={"route_status": route.status.value},
            )
        selected = route.selected_resource
        if selected is None:  # an impossible IntelligenceRoute invariant
            raise ValueError("satisfied intelligence route lacks a resource")
        inference_request = IntelligenceRequest(
            content=execution_input.content,
            model_id=selected.model_id,
            request_id=request.execution_id,
            metadata={
                **execution_input.metadata,
                "decision_id": request.decision.decision_id,
                "request_id": request.decision.request_id,
            },
        )
        try:
            result = self._runtime.execute(selected.provider_id, inference_request)
        except (
            ProviderNotFoundError,
            ModelNotFoundError,
            ModelUnavailableError,
        ) as exc:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="intelligence_resource_unavailable",
                    message=str(exc),
                    details={
                        "provider_id": selected.provider_id,
                        "model_id": selected.model_id,
                    },
                ),
                metadata={"route_status": route.status.value},
            )
        output = ExecutionOutput(
            value={
                "content": result.output,
                "provider_id": result.provider_id,
                "model_id": result.model_id,
            },
            reference=f"{result.provider_id}/{result.model_id}",
        )
        metadata = {
            "route_status": route.status.value,
            "route_reason": route.reason.value,
            "unmet_preferences": [item.value for item in route.unmet_preferences],
            "runtime_metadata": result.metadata,
        }
        if not result.success:
            if result.diagnostic is None:  # protected by IntelligenceResult
                raise ValueError("failed intelligence result lacks a diagnostic")
            return HandlerOutcome(
                status=ExecutionStatus.FAILED,
                output=output,
                failure=ExecutionFailure(
                    code="intelligence_operational_failure",
                    message=result.diagnostic,
                    details={
                        "provider_id": result.provider_id,
                        "model_id": result.model_id,
                    },
                ),
                metadata=metadata,
            )
        return HandlerOutcome(
            status=ExecutionStatus.SUCCEEDED,
            output=output,
            metadata=metadata,
        )
