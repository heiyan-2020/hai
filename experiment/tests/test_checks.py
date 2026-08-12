import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class CheckersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "run.py").write_text(
            "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--out-dir')\n",
            encoding="utf-8",
        )
        (self.root / "metrics.py").write_text(
            "def mean(values):\n    mean_ms = sum(values) / len(values)\n    return mean_ms\n",
            encoding="utf-8",
        )
        research = self.root / ".claude-research"
        (research / "protocols").mkdir(parents=True)
        (research / "facts" / "internal").mkdir(parents=True)
        (research / "data" / "if-001").mkdir(parents=True)
        (research / "data" / "if-001" / "summary.json").write_text(
            '{"mean_ms": 3.0}\n', encoding="utf-8"
        )
        (research / "data" / "if-001" / "raw.jsonl").write_text(
            '{"latency_ms": 2.0}\n{"latency_ms": 4.0}\n', encoding="utf-8"
        )
        self.protocol = research / "protocols" / "latency-protocol.md"
        self.protocol.write_text(
            """---
task: latency
script: "run.py"
parameters:
  - name: "--out-dir"
fixed: []
---

# Latency Protocol

## Run root shape
```text
<run_root>/
  summary.json [bears conclusions]
```

## Artifact: summary.json
contains: mean latency
git_tracked: false
fields:
  - mean_ms (important)

### Field: mean_ms
- nature: DERIVED
- source_field: summary.json -> mean_ms
- file: metrics.py
- formula: mean_ms = sum(values) / len(values)
```python
mean_ms = sum(values) / len(values)
```
""",
            encoding="utf-8",
        )
        self.fact = research / "facts" / "internal" / "if-001-latency.md"
        self.fact.write_text(
            """---
id: if-001
type: internal
status: active
created_at: "2026-08-12T00:00:00Z"
question: "What was mean latency?"
claim: "Mean latency was 3.0 ms in the checked run."
tldr: "Mean latency was 3.0 ms; only the checked run is covered."
metric:
  name: mean_ms
  value: 3.0
  unit: ms
data:
  primary_path: data/if-001/summary.json
  supporting_paths:
    - data/if-001/raw.jsonl
protocol:
  path: protocols/latency-protocol.md
  fields:
    - artifact: summary.json
      field: mean_ms
repro:
  command: "python3 run.py --out-dir .claude-research/data/if-001"
  commit: "0123456"
  branch: "main"
  environment: "Python 3"
  hardware: "CPU"
---

# if-001 - Latency

## Bottom line
- Answer: Mean latency was 3.0 ms; only the checked run is covered.
- Claim: Mean latency was 3.0 ms in the checked run.
- Metric: mean_ms = 3.0 ms

## Key evidence
The stored result is `data/if-001/summary.json`.

## Scope & limits
- Covers one checked run.

## Lineage
Protocol field summary.json#mean_ms materialized at `data/if-001/summary.json`.

## Reproduction
Recompute from the stored rows:
```bash
python3 -c 'import json,statistics; print(statistics.fmean(json.loads(x)["latency_ms"] for x in open(".claude-research/data/if-001/raw.jsonl")))'
```
Verified: the recomputation returned 3.0 ms. Regenerate with `python3 run.py --out-dir .claude-research/data/if-001`.
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_check(self, script, *args):
        return subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / script), *map(str, args)],
            cwd=self.root,
            text=True,
            capture_output=True,
        )

    def test_valid_protocol_and_fact(self):
        protocol = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(protocol.returncode, 0, protocol.stdout + protocol.stderr)
        fact = self.run_check(
            "fact_check.py",
            self.root / ".claude-research" / "facts",
            "--research-root",
            self.root / ".claude-research",
        )
        self.assertEqual(fact.returncode, 0, fact.stdout + fact.stderr)

    def test_protocol_rejects_unlocatable_snippet(self):
        text = self.protocol.read_text(encoding="utf-8").replace(
            "mean_ms = sum(values) / len(values)", "mean_ms = 99"
        )
        self.protocol.write_text(text, encoding="utf-8")
        result = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(result.returncode, 1)
        self.assertIn("snippet not found", result.stdout)

    def test_fact_rejects_structurally_invalid_protocol(self):
        text = self.protocol.read_text(encoding="utf-8").replace(
            "  summary.json [bears conclusions]", "  summary.json"
        )
        self.protocol.write_text(text, encoding="utf-8")
        result = self.run_check(
            "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("failed Protocol validation", result.stdout)

    def test_protocol_rejects_code_outside_project_root(self):
        outside = Path(self.temp.name).parent / "experiment-outside.py"
        outside.write_text("mean_ms = 3.0\n", encoding="utf-8")
        try:
            text = self.protocol.read_text(encoding="utf-8").replace(
                'script: "run.py"', f'script: "{outside}"'
            ).replace("- file: metrics.py", f"- file: {outside}")
            self.protocol.write_text(text, encoding="utf-8")
            result = self.run_check("protocol_check.py", self.protocol)
            self.assertEqual(result.returncode, 1)
            self.assertIn("escapes project root", result.stdout)
        finally:
            outside.unlink(missing_ok=True)

    def test_fact_rejects_unknown_protocol_field(self):
        text = self.fact.read_text(encoding="utf-8").replace(
            "field: mean_ms", "field: missing_metric"
        )
        self.fact.write_text(text, encoding="utf-8")
        result = self.run_check(
            "fact_check.py",
            self.root / ".claude-research" / "facts",
            "--research-root",
            self.root / ".claude-research",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Protocol field not found", result.stdout)

    def test_protocol_validates_delegated_child(self):
        (self.root / "plot.py").write_text(
            "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--out')\nbar = draw(mean_ms)\n",
            encoding="utf-8",
        )
        child = self.protocol.parent / "figure-protocol.md"
        child.write_text(
            """---
task: latency-figure
script: "plot.py"
parameters:
  - name: "--out"
fixed: []
---
## Run root shape
```text
latency.png [bears conclusions]
```
## Artifact: latency.png
contains: latency bar
git_tracked: false
fields:
  - mean_bar (important)
### Field: mean_bar
- nature: DERIVED
- source_field: latency.png -> mean bar
- file: plot.py
- formula: bar length = mean_ms
```python
bar = draw(mean_ms)
```
""",
            encoding="utf-8",
        )
        parent = self.protocol.read_text(encoding="utf-8").replace(
            "  summary.json [bears conclusions]",
            "  summary.json [bears conclusions]\n  latency.png [bears conclusions, delegated]",
        ) + """
## Artifact: latency.png
contains: latency visualization
git_tracked: false
lineage_protocol: "figure-protocol.md"
"""
        self.protocol.write_text(parent, encoding="utf-8")
        result = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fact_rejects_empty_collection(self):
        self.fact.unlink()
        result = self.run_check(
            "fact_check.py",
            self.root / ".claude-research" / "facts",
            "--research-root",
            self.root / ".claude-research",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("RESULT: INVALID", result.stdout)

    def test_fact_rejects_paths_outside_research_root(self):
        outside = self.root / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        link = self.root / ".claude-research" / "data" / "if-001" / "outside-link"
        link.symlink_to(outside)
        original = self.fact.read_text(encoding="utf-8")
        for path in ("/etc/hosts", "../outside.json", "data/if-001/outside-link"):
            with self.subTest(path=path):
                self.fact.write_text(
                    original.replace("data/if-001/summary.json", path, 1),
                    encoding="utf-8",
                )
                result = self.run_check(
                    "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("escapes research root", result.stdout)

    def test_fact_rejects_wrong_fact_and_data_directories(self):
        outside = self.root / "outside" / "internal" / self.fact.name
        outside.parent.mkdir(parents=True)
        outside.write_text(self.fact.read_text(encoding="utf-8"), encoding="utf-8")
        result = self.run_check(
            "fact_check.py", outside, "--research-root", self.root / ".claude-research"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must live directly", result.stdout)

        text = self.fact.read_text(encoding="utf-8").replace(
            "data/if-001/summary.json", "protocols/latency-protocol.md", 1
        )
        self.fact.write_text(text, encoding="utf-8")
        result = self.run_check(
            "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must live under data/if-001/", result.stdout)

    def test_fact_rejects_command_that_only_names_script(self):
        original = self.fact.read_text(encoding="utf-8")
        for command in (
            "echo run.py",
            "echo python3 run.py",
            "python3 run.py && echo extra",
            "python3 run.py $(echo extra)",
            "python3 -c run.py",
            "python3 --version run.py",
        ):
            with self.subTest(command=command):
                self.fact.write_text(
                    original.replace(
                        "python3 run.py --out-dir .claude-research/data/if-001", command, 1
                    ),
                    encoding="utf-8",
                )
                result = self.run_check(
                    "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("must invoke the Protocol script", result.stdout)

    def test_fact_accepts_interpreter_option(self):
        text = self.fact.read_text(encoding="utf-8").replace(
            "python3 run.py --out-dir .claude-research/data/if-001",
            "python3 -u run.py --out-dir .claude-research/data/if-001",
            1,
        )
        self.fact.write_text(text, encoding="utf-8")
        result = self.run_check(
            "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fact_requires_verified_result_outside_command(self):
        text = self.fact.read_text(encoding="utf-8").replace(
            "python3 -c 'import json,statistics; print(statistics.fmean(json.loads(x)[\"latency_ms\"] for x in open(\".claude-research/data/if-001/raw.jsonl\")))'",
            "echo Verified: 3.0",
        ).replace("Verified: the recomputation returned 3.0 ms. ", "")
        self.fact.write_text(text, encoding="utf-8")
        result = self.run_check(
            "fact_check.py", self.fact, "--research-root", self.root / ".claude-research"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("must record the recomputation result", result.stdout)

    def test_protocol_rejects_duplicate_paths_and_unknown_marker(self):
        text = self.protocol.read_text(encoding="utf-8").replace(
            "  summary.json [bears conclusions]",
            "  summary.json [bears conclusions]\n  summary.json [bears conclusions, nonsense]",
        )
        self.protocol.write_text(text, encoding="utf-8")
        result = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate paths", result.stdout)
        self.assertIn("invalid marker", result.stdout)

    def test_protocol_rejects_unmarked_output(self):
        text = self.protocol.read_text(encoding="utf-8").replace(
            "  summary.json [bears conclusions]",
            "  summary.json [bears conclusions]\n  raw.jsonl",
        )
        self.protocol.write_text(text, encoding="utf-8")
        result = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid marker", result.stdout)

    def test_protocol_rejects_delegation_outside_protocol_root(self):
        outside = self.root / "outside-protocol.md"
        outside.write_text(self.protocol.read_text(encoding="utf-8"), encoding="utf-8")
        parent = self.protocol.read_text(encoding="utf-8").replace(
            "  summary.json [bears conclusions]",
            "  summary.json [bears conclusions]\n  latency.png [bears conclusions, delegated]",
        ) + f"""
## Artifact: latency.png
contains: latency visualization
git_tracked: false
lineage_protocol: "{outside}"
"""
        self.protocol.write_text(parent, encoding="utf-8")
        result = self.run_check("protocol_check.py", self.protocol)
        self.assertEqual(result.returncode, 1)
        self.assertIn("escapes Protocol root", result.stdout)


if __name__ == "__main__":
    unittest.main()
