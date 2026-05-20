"""Assertion behind the `enforce-tool-call-marker` pin."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inducer import TOOL_CALL_MARKER, build_inducer_prompt


def test_marker_suffix():
    prompt = build_inducer_prompt("some retrieved context about the weather")
    assert prompt.endswith(TOOL_CALL_MARKER), (
        "inducer prompt must end with the tool-call marker — without it the "
        "model free-styles instead of emitting a tool call"
    )
