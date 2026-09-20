from __future__ import annotations

import pytest

from iris.core import Request


def test_request_creation_preserves_identity_source_and_content() -> None:
    request = Request(
        request_id="request-001",
        content="estado",
        source="cli",
        metadata={"session": "local"},
    )

    assert request.request_id == "request-001"
    assert request.content == "estado"
    assert request.source == "cli"
    assert request.metadata == {"session": "local"}


def test_request_generates_a_non_empty_identifier() -> None:
    request = Request(content="estado", source="cli")

    assert request.request_id


def test_request_copies_metadata_into_a_read_only_view() -> None:
    metadata = {"session": "initial"}
    request = Request(content="estado", source="cli", metadata=metadata)

    metadata["session"] = "changed"

    assert request.metadata["session"] == "initial"
    with pytest.raises(TypeError):
        request.metadata["new"] = "value"  # type: ignore[index]


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"content": "estado", "source": ""}, ValueError),
        ({"content": "estado", "source": "cli", "request_id": " "}, ValueError),
        ({"content": 1, "source": "cli"}, TypeError),
        ({"content": "estado", "source": "cli", "metadata": []}, TypeError),
        ({"content": "estado", "source": "cli", "metadata": {1: "value"}}, TypeError),
    ],
)
def test_request_rejects_invalid_fields(kwargs, error_type) -> None:
    with pytest.raises(error_type):
        Request(**kwargs)
