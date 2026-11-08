# hai

A marketplace of agent plugins by heiyan, installable in Claude Code and Codex.

## Install

### Claude Code

In Claude Code, add this marketplace once, then install any plugin from it:

```
/plugin marketplace add heiyan-2020/hai
/plugin install pin@hai
/plugin install experiment@hai
/plugin install autoresearch@hai
/plugin install me@hai
/plugin install safeguard@hai
```

For Safeguard, configure its translation provider in `/plugin` and restart Claude.
Safeguard requires Claude Code Mods APIs and is not available in Codex.
For skill plugins, after installing, run `/reload-plugins`. The skill or command names are then
namespaced by plugin, e.g. `/pin:pin-aware-agent`.

To pick up later updates:

```
/plugin marketplace update hai
```

### Codex

In Codex, add the same repo as a marketplace, then install plugins from it:

```bash
codex plugin marketplace add heiyan-2020/hai
codex plugin add pin@hai
codex plugin add vibe-slides@hai
codex plugin add experiment@hai
codex plugin add autoresearch@hai
codex plugin add me@hai
```

To pick up later updates:

```bash
codex plugin marketplace upgrade hai
```

## Plugins

| Plugin | What it does |
|--------|--------------|
| [`pin`](./pin) | Pin + Protocol + Fact disciplines for agent-driven research — lock design decisions against silent rollback, make every conclusion-bearing data element traceable to code, keep citeable observations structured, and keep the human genuinely in the loop via machine audit, an adversarial Codex audit, and an interactive grounding quiz. |
| [`vibe-slides`](./vibe-slides) | Author academic slide decks via a markdown DSL — extract a theme and components from a `.pptx` template, iterate on a content-only outline, then compile to `.pptx` with pptxgenjs. |
| [`sop`](./sop) | Standard operating procedure skills for repeatable engineering and analysis workflows — submit merge/pull requests, walk through branch diffs before a merge, triage public-safe files from a mixed private branch, initialize local-only files across workspaces, analyze surprising empirical results with falsifiable hypotheses, and fix problems at the root cause instead of overfitting a patch to the one example you saw. |
| [`experiment`](./experiment) | Run lightweight, reproducible experiments: Protocols declare artifact lineage and internal Facts materialize concrete runs as structured evidence. |
| [`autoresearch`](./autoresearch) | Research-design skills grounded in top systems papers. `create-novelty` turns a research topic into an OSDI/SOSP-grade plan: the problem, baselines down to their root cause, an insight that makes the design obvious in hindsight, related-work deltas, and the experiments and per-novelty ablations reviewers expect. It draws on 100 dissected OSDI/SOSP papers (2016–2026). |
| [`me`](./me) | Human-centered skills: the goal is that you understand more, not that the agent finishes the task. `teach-me-this` hides a paper you have not read behind a private answer card, then turns it into 2–3 exercises: find the research problem from messy observations, design the solution, design the key experiments, or transfer the idea. You write a complete answer, it is scored against a fixed rubric, then the paper's answer is revealed and you analyze the gap. It ends with feedback per ability and a log that tracks weak spots across papers. |
| [`safeguard`](./safeguard) | Claude Code only: automatic English input translation and local after-send JSONL context auditing, with native UI diagnostics. |

## Repository layout

```
hai/
├── .agents/
│   └── plugins/marketplace.json   # Codex marketplace
├── .claude-plugin/
│   └── marketplace.json           # Claude Code marketplace
├── pin/                   # one plugin = one subdirectory
│   ├── .claude-plugin/plugin.json
│   └── .codex-plugin/plugin.json
├── vibe-slides/
│   ├── .claude-plugin/plugin.json
│   └── .codex-plugin/plugin.json
├── experiment/
│   ├── .claude-plugin/plugin.json
│   └── .codex-plugin/plugin.json
├── autoresearch/
│   ├── .claude-plugin/plugin.json
│   └── .codex-plugin/plugin.json
├── me/
│   ├── .claude-plugin/plugin.json
│   └── .codex-plugin/plugin.json
├── safeguard/             # Claude Code Mods API only
│   └── .claude-plugin/plugin.json
└── README.md
```

## Adding another plugin

1. Put the plugin in its own subdirectory.
2. Add `.claude-plugin/plugin.json` for Claude Code.
3. For plugins that support Codex, add `.codex-plugin/plugin.json`.
4. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./<dir>"`.
5. For plugins that support Codex, add an entry to `.agents/plugins/marketplace.json` with `"source": { "source": "local", "path": "./<dir>" }`.
6. Commit and push. Claude Code users get it with `/plugin marketplace update hai`; Codex users get it with `codex plugin marketplace upgrade hai`.

Claude Code plugin entries omit `version`, so every pushed commit is treated as
a new version and `marketplace update` always pulls the latest. Codex plugin
versions live in each `.codex-plugin/plugin.json` and should be bumped when you
publish changes.
