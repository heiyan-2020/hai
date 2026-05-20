"""Inducer — builds the prompt that forces the model to emit a tool call.

This models the force-decode example: a real design decision that an agent
once silently reverted, tanking the tool-call hit rate for days.
"""

# The canonical Qwen-style marker. Ending a prompt with this forces the model
# straight into a tool call instead of free-form text.
TOOL_CALL_MARKER = "</think>\n\n<tool_call>\n<function="


def build_inducer_prompt(context: str) -> str:
    """Build an inducer prompt from retrieved context.

    # PIN: enforce-tool-call-marker
    The returned prompt MUST end with TOOL_CALL_MARKER. Removing the marker
    makes the model free-style instead of calling a tool — the hit rate
    collapses and nothing else looks wrong.
    """
    return f"{context.strip()}\n{TOOL_CALL_MARKER}"
