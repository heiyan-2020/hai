"""Unit tests for structured markdown fact checking."""
import os

import fact_check
import factlib

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")


def test_demo_facts_are_valid():
    report = factlib.validate_facts(os.path.join(DEMO, "facts"), DEMO)
    assert report["ok"]
    assert report["summary"]["total"] == 4
    assert report["summary"]["internal"] == 2
    assert report["summary"]["external"] == 1
    assert report["summary"]["derived"] == 1


def test_fact_check_main_returns_zero_for_demo():
    assert fact_check.main([os.path.join(DEMO, "facts"), "--research-root", DEMO]) == 0


def _write_protocol(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "eval.py").write_text("accuracy = correct / total\n")
    (tmp_path / "protocol.md").write_text(
        "---\n"
        "task: eval\n"
        "artifacts: [{path: 'data/if-001/result.json'}]\n"
        "---\n\n"
        "# result\n\n"
        "## Element: accuracy\n"
        "- nature: MEASURED\n"
        "- file: src/eval.py\n"
        "```python\n"
        "accuracy = correct / total\n"
        "```\n"
    )


def _write_internal_fact(tmp_path, claim=None, protocol_element="accuracy"):
    (tmp_path / "facts" / "internal").mkdir(parents=True)
    (tmp_path / "data" / "if-001").mkdir(parents=True)
    (tmp_path / "data" / "if-001" / "result.json").write_text('{"accuracy": 0.9}\n')
    _write_protocol(tmp_path)
    claim = claim or "Model A records 90% accuracy on the tiny evaluation."
    fact = tmp_path / "facts" / "internal" / "if-001-accuracy.md"
    fact.write_text(
        "---\n"
        "id: if-001\n"
        "type: internal\n"
        "status: active\n"
        "created_at: '2026-05-22T00:00:00Z'\n"
        "question: What accuracy was recorded?\n"
        f"claim: {claim}\n"
        "tldr: Accuracy was 90%.\n"
        "metric: {name: accuracy, value: 90, unit: '%'}\n"
        "data:\n"
        "  primary_path: data/if-001/result.json\n"
        "protocol:\n"
        "  path: protocol.md\n"
        f"  elements: [{protocol_element}]\n"
        "repro:\n"
        "  command: python src/eval.py\n"
        "  commit: abc1234\n"
        "---\n\n"
        "# if-001 - Accuracy\n\n"
        "## Bottom line\n\n"
        "- Answer: Accuracy was 90%.\n"
        f"- Claim: {claim}\n"
        "- Metric: accuracy = 90%.\n\n"
        "## Key evidence\n\n"
        "| What it shows | Value | Source |\n"
        "|---|---|---|\n"
        "| Recorded accuracy | 90% | `data/if-001/result.json` |\n\n"
        "## Scope & limits\n\n"
        "- This fact only covers the tiny evaluation.\n\n"
        "## Lineage\n\n"
        "- Protocol `protocol.md`, element `accuracy`.\n\n"
        "## Reproduction\n\n"
        "```bash\npython src/eval.py\n```\n\n"
        "- Commit abc1234. Verified: result file recorded.\n"
    )


def test_internal_fact_validates(tmp_path):
    _write_internal_fact(tmp_path)
    report = factlib.validate_facts(str(tmp_path / "facts"), str(tmp_path))
    assert report["ok"]


def test_internal_fact_rejects_causal_claim(tmp_path):
    _write_internal_fact(
        tmp_path,
        claim="Model A records 90% accuracy because the prompt is longer.",
    )
    report = factlib.validate_facts(str(tmp_path / "facts"), str(tmp_path))
    assert not report["ok"]
    assert any("causal" in problem for problem in report["problems"])


def test_internal_fact_rejects_missing_protocol_element(tmp_path):
    _write_internal_fact(tmp_path, protocol_element="missing")
    report = factlib.validate_facts(str(tmp_path / "facts"), str(tmp_path))
    assert not report["ok"]
    assert any("protocol element" in problem for problem in report["problems"])


def test_sections_must_be_in_order(tmp_path):
    _write_internal_fact(tmp_path)
    fact_path = tmp_path / "facts" / "internal" / "if-001-accuracy.md"
    text = fact_path.read_text()
    # Swap two sections so all are present but out of order.
    text = text.replace("## Key evidence", "## __TMP__", 1)
    text = text.replace("## Scope & limits", "## Key evidence", 1)
    text = text.replace("## __TMP__", "## Scope & limits", 1)
    fact_path.write_text(text)
    report = factlib.validate_facts(str(tmp_path / "facts"), str(tmp_path))
    assert not report["ok"]
    assert any("sections" in problem for problem in report["problems"])
