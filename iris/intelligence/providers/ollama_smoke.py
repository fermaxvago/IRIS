"""Opt-in physical smoke test for the IRIS Ollama intelligence path."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from iris.intelligence import (
    IntelligenceRequest,
    IntelligenceRuntime,
    ModelNotFoundError,
    ProviderRegistry,
)
from iris.intelligence.providers.ollama import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_PROVIDER_ID,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    OllamaOperationalError,
    OllamaProvider,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Discover a model and run one real request through IntelligenceRuntime."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_OLLAMA_ENDPOINT)
    parser.add_argument("--provider-id", default=DEFAULT_OLLAMA_PROVIDER_ID)
    parser.add_argument("--timeout", type=float, default=DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: IRIS local intelligence OK",
    )
    args = parser.parse_args(argv)

    provider = OllamaProvider(
        provider_id=args.provider_id,
        endpoint=args.endpoint,
        timeout=args.timeout,
    )
    registry = ProviderRegistry([provider])
    runtime = IntelligenceRuntime(registry)

    try:
        models = provider.list_models()
        print(f"Provider reachable: {provider.provider_id} ({provider.endpoint})")
        if args.model not in {model.model_id for model in models}:
            print(f"Model not discovered: {args.model}")
            return 2

        print(f"Model discovered: {args.model}")
        result = runtime.execute(
            provider.provider_id,
            IntelligenceRequest(content=args.prompt, model_id=args.model),
        )
    except (OllamaOperationalError, ModelNotFoundError) as exc:
        print(f"Smoke test failed: {exc}")
        return 2

    if not result.success:
        print(f"Inference failed: {result.diagnostic}")
        return 1
    print("Inference status: success")
    print(result.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
