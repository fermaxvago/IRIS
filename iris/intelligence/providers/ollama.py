"""Ollama adapter for local, provider-independent text inference."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from iris.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResult,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
)

DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_PROVIDER_ID = "ollama-local"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120.0

_Transport = Callable[[str, str, bytes | None, float], tuple[int, bytes]]


class OllamaOperationalError(RuntimeError):
    """Base class for expected Ollama discovery/transport failures."""

    failure_kind = "operational_error"

    def __init__(
        self,
        message: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class OllamaUnavailableError(OllamaOperationalError):
    """Raised when the configured Ollama endpoint cannot be reached."""

    failure_kind = "provider_unavailable"


class OllamaTimeoutError(OllamaOperationalError):
    """Raised when an Ollama request exceeds the configured timeout."""

    failure_kind = "timeout"


class OllamaAPIError(OllamaOperationalError):
    """Raised when Ollama reports a non-success HTTP response."""

    failure_kind = "api_error"

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(
            message,
            metadata={"ollama.http_status": status_code},
        )


class OllamaInferenceError(OllamaOperationalError):
    """Raised when Ollama explicitly rejects an inference request."""

    failure_kind = "inference_rejected"


class OllamaProtocolError(OllamaOperationalError):
    """Raised when the backend returns an unusable protocol response."""

    failure_kind = "protocol_error"


def _urllib_transport(
    method: str,
    url: str,
    body: bytes | None,
    timeout: float,
) -> tuple[int, bytes]:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = UrlRequest(url, data=body, headers=headers, method=method)

    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.read()
    except HTTPError as exc:
        try:
            return exc.code, exc.read()
        finally:
            exc.close()


class OllamaProvider:
    """Use one explicitly configured Ollama server as an intelligence provider."""

    def __init__(
        self,
        *,
        provider_id: str = DEFAULT_OLLAMA_PROVIDER_ID,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        timeout: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        _transport: _Transport | None = None,
    ) -> None:
        self._provider_id = _validate_identifier(provider_id, "provider_id")
        self._endpoint = _normalize_endpoint(endpoint)
        self._timeout = _validate_timeout(timeout)
        self._transport = _transport or _urllib_transport

    @property
    def provider_id(self) -> str:
        """Return the stable identity of this configured Ollama instance."""

        return self._provider_id

    @property
    def endpoint(self) -> str:
        """Return the configured HTTP endpoint without a trailing slash."""

        return self._endpoint

    @property
    def timeout(self) -> float:
        """Return the request timeout in seconds."""

        return self._timeout

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        """Discover installed text-generation models from the Ollama API.

        Reachability and protocol failures are represented by specific
        ``OllamaOperationalError`` subclasses because discovery has no result
        envelope in the provider contract.
        """

        payload = self._request_json(
            "GET",
            "/api/tags",
            operation="model discovery",
        )
        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            raise OllamaProtocolError(
                "Ollama model discovery response lacks a models list"
            )

        descriptors: list[ModelDescriptor] = []
        seen_model_ids: set[str] = set()
        for raw_model in raw_models:
            model = _require_object(raw_model, "Ollama model entry")
            model_id = _model_identifier(model)
            if model_id in seen_model_ids:
                raise OllamaProtocolError(
                    f"Ollama returned duplicate model identifier: {model_id}"
                )
            seen_model_ids.add(model_id)

            details_payload = self._request_json(
                "POST",
                "/api/show",
                payload={"model": model_id},
                operation=f"model inspection for {model_id}",
            )
            capabilities = _required_string_list(
                details_payload,
                "capabilities",
                context=f"Ollama model details for {model_id}",
            )
            if "completion" not in capabilities:
                continue

            details = _optional_object(
                details_payload,
                "details",
                context=f"Ollama model details for {model_id}",
            ) or _optional_object(
                model,
                "details",
                context=f"Ollama model entry for {model_id}",
            )
            model_info = _optional_object(
                details_payload,
                "model_info",
                context=f"Ollama model details for {model_id}",
            )
            metadata = _model_metadata(
                model,
                details,
                capabilities,
            )
            descriptors.append(
                ModelDescriptor(
                    model_id=model_id,
                    provider_id=self.provider_id,
                    location=ModelLocation.LOCAL,
                    capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
                    context_window=_context_window(details, model_info),
                    available=True,
                    metadata=metadata,
                )
            )

        return tuple(sorted(descriptors, key=lambda descriptor: descriptor.model_id))

    def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
        """Run non-streaming text inference for the explicitly requested model."""

        if not isinstance(request, IntelligenceRequest):
            raise TypeError("request must be an IntelligenceRequest")

        try:
            payload = self._request_json(
                "POST",
                "/api/generate",
                payload={
                    "model": request.model_id,
                    "prompt": request.content,
                    "stream": False,
                },
                operation=f"inference with {request.model_id}",
            )
            return self._normalize_inference(payload, request)
        except OllamaOperationalError as exc:
            return self._failed_result(request, exc)

    def _normalize_inference(
        self,
        payload: Mapping[str, object],
        request: IntelligenceRequest,
    ) -> IntelligenceResult:
        try:
            error = payload.get("error")
            if error is not None:
                if not isinstance(error, str) or not error.strip():
                    raise OllamaProtocolError(
                        "Ollama inference returned an invalid error payload"
                    )
                raise OllamaInferenceError(
                    f"Ollama rejected inference: {_truncate(error)}",
                    metadata={"ollama.error": _truncate(error)},
                )

            response_model = _required_string(
                payload,
                "model",
                context="Ollama inference response",
            )
            if response_model != request.model_id:
                raise OllamaProtocolError(
                    "Ollama inference response model does not match the request",
                    metadata={"ollama.response_model": response_model},
                )
            output = _required_string(
                payload,
                "response",
                context="Ollama inference response",
                allow_empty=True,
            )
            done = payload.get("done")
            if done is not True:
                raise OllamaProtocolError(
                    "Ollama returned an incomplete non-streaming response"
                )

            metadata = _inference_metadata(payload)
            return IntelligenceResult.succeeded(
                request,
                provider_id=self.provider_id,
                output=output,
                metadata=metadata,
            )
        except OllamaOperationalError as exc:
            return self._failed_result(request, exc)

    def _failed_result(
        self,
        request: IntelligenceRequest,
        error: OllamaOperationalError,
    ) -> IntelligenceResult:
        metadata: dict[str, object] = {
            "failure_kind": error.failure_kind,
            "ollama.endpoint": self.endpoint,
            **error.metadata,
        }
        if isinstance(error, OllamaAPIError) and error.status_code == 404:
            metadata["failure_kind"] = "model_not_found"
        return IntelligenceResult.failed(
            request,
            provider_id=self.provider_id,
            diagnostic=str(error),
            metadata=metadata,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        operation: str,
    ) -> Mapping[str, object]:
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        try:
            status, response_body = self._transport(
                method,
                f"{self.endpoint}{path}",
                body,
                self.timeout,
            )
        except TimeoutError as exc:
            raise OllamaTimeoutError(
                f"Ollama {operation} timed out after {self.timeout:g} seconds"
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise OllamaTimeoutError(
                    f"Ollama {operation} timed out after {self.timeout:g} seconds"
                ) from exc
            raise OllamaUnavailableError(
                f"Ollama is unavailable during {operation}"
            ) from exc

        if isinstance(status, bool) or not isinstance(status, int):
            raise TypeError("HTTP transport status must be an integer")
        if not isinstance(response_body, bytes):
            raise TypeError("HTTP transport body must be bytes")
        if not 200 <= status < 300:
            message = _api_error_message(response_body, status, operation)
            raise OllamaAPIError(status, message)

        return _decode_json_object(response_body, context=f"Ollama {operation}")


def _validate_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    return value


def _normalize_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str):
        raise TypeError("endpoint must be a string")
    normalized = endpoint.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("endpoint must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain a query or fragment")
    return normalized


def _validate_timeout(timeout: float) -> float:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be a number")
    value = float(timeout)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be finite and positive")
    return value


def _decode_json_object(body: bytes, *, context: str) -> Mapping[str, object]:
    try:
        decoded: object = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OllamaProtocolError(f"{context} returned invalid JSON") from exc
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise OllamaProtocolError(f"{context} must return a JSON object")
    return cast(dict[str, object], decoded)


def _api_error_message(body: bytes, status: int, operation: str) -> str:
    try:
        payload = _decode_json_object(body, context=f"Ollama {operation} error")
    except OllamaProtocolError:
        return f"Ollama {operation} failed with HTTP {status}"
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return f"Ollama {operation} failed: {_truncate(error)}"
    return f"Ollama {operation} failed with HTTP {status}"


def _truncate(value: str, limit: int = 500) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[:limit]}…"


def _require_object(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OllamaProtocolError(f"{context} must be a JSON object")
    return cast(dict[str, object], value)


def _optional_object(
    payload: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> Mapping[str, object] | None:
    value = payload.get(key)
    if value is None:
        return None
    return _require_object(value, f"{context}.{key}")


def _required_string(
    payload: Mapping[str, object],
    key: str,
    *,
    context: str,
    allow_empty: bool = False,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise OllamaProtocolError(f"{context}.{key} must be a string")
    return value


def _required_string_list(
    payload: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise OllamaProtocolError(f"{context}.{key} must be a string list")
    return tuple(value)


def _model_identifier(model: Mapping[str, object]) -> str:
    model_id = model.get("model")
    if not isinstance(model_id, str) or not model_id.strip():
        model_id = model.get("name")
    if not isinstance(model_id, str) or not model_id.strip():
        raise OllamaProtocolError("Ollama model entry lacks a model identifier")
    if model_id != model_id.strip():
        raise OllamaProtocolError(
            "Ollama model identifier contains surrounding whitespace"
        )
    return model_id


def _model_metadata(
    model: Mapping[str, object],
    details: Mapping[str, object] | None,
    capabilities: tuple[str, ...],
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "ollama.capabilities": tuple(sorted(capabilities)),
    }
    _copy_optional_string(model, "name", metadata, "ollama.name")
    _copy_optional_string(model, "digest", metadata, "ollama.digest")
    _copy_optional_string(model, "modified_at", metadata, "ollama.modified_at")
    _copy_optional_integer(model, "size", metadata, "ollama.size_bytes")

    if details is not None:
        _copy_optional_string(details, "format", metadata, "ollama.format")
        _copy_optional_string(details, "family", metadata, "ollama.family")
        _copy_optional_string(
            details,
            "parameter_size",
            metadata,
            "ollama.parameter_size",
        )
        _copy_optional_string(
            details,
            "quantization_level",
            metadata,
            "ollama.quantization_level",
        )
        families = details.get("families")
        if families is not None:
            if not isinstance(families, list) or not all(
                isinstance(family, str) for family in families
            ):
                raise OllamaProtocolError(
                    "Ollama model details.families must be a string list"
                )
            metadata["ollama.families"] = tuple(families)
    return metadata


def _context_window(
    details: Mapping[str, object] | None,
    model_info: Mapping[str, object] | None,
) -> int | None:
    if model_info is None:
        return None
    architecture = model_info.get("general.architecture")
    if not isinstance(architecture, str) and details is not None:
        architecture = details.get("family")
    if not isinstance(architecture, str) or not architecture:
        return None
    value = model_info.get(f"{architecture}.context_length")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _copy_optional_string(
    source: Mapping[str, object],
    source_key: str,
    target: dict[str, object],
    target_key: str,
) -> None:
    value = source.get(source_key)
    if value is None:
        return
    if not isinstance(value, str):
        raise OllamaProtocolError(f"Ollama field {source_key} must be a string")
    target[target_key] = value


def _copy_optional_integer(
    source: Mapping[str, object],
    source_key: str,
    target: dict[str, object],
    target_key: str,
) -> None:
    value = source.get(source_key)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise OllamaProtocolError(f"Ollama field {source_key} must be an integer")
    target[target_key] = value


def _inference_metadata(payload: Mapping[str, object]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    string_fields = {
        "created_at": "ollama.created_at",
        "done_reason": "ollama.done_reason",
    }
    integer_fields = {
        "total_duration": "ollama.total_duration_ns",
        "load_duration": "ollama.load_duration_ns",
        "prompt_eval_count": "ollama.prompt_eval_count",
        "prompt_eval_cached_count": "ollama.prompt_eval_cached_count",
        "prompt_eval_duration": "ollama.prompt_eval_duration_ns",
        "eval_count": "ollama.eval_count",
        "eval_duration": "ollama.eval_duration_ns",
    }
    for source_key, target_key in string_fields.items():
        _copy_optional_string(payload, source_key, metadata, target_key)
    for source_key, target_key in integer_fields.items():
        _copy_optional_integer(payload, source_key, metadata, target_key)
    return metadata
