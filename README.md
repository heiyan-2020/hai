# hai

A marketplace of agent plugins by heiyan, installable in Claude Code and Codex.

## Install

### Claude Code

In Claude Code, add this marketplace once, then install any plugin from it:

```
/plugin marketplace add heiyan-2020/hai
/plugin install pin@hai
```

Replace `<your-github-username>` with the GitHub account this repo lives under.
After installing, run `/reload-plugins`. The skill or command names are then
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
└── README.md
```

## Adding another plugin

1. Put the plugin in its own subdirectory.
2. Add `.claude-plugin/plugin.json` for Claude Code.
3. Add `.codex-plugin/plugin.json` for Codex.
4. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./<dir>"`.
5. Add an entry to `.agents/plugins/marketplace.json` with `"source": { "source": "local", "path": "./<dir>" }`.
6. Commit and push. Claude Code users get it with `/plugin marketplace update hai`; Codex users get it with `codex plugin marketplace upgrade hai`.

Claude Code plugin entries omit `version`, so every pushed commit is treated as
a new version and `marketplace update` always pulls the latest. Codex plugin
versions live in each `.codex-plugin/plugin.json` and should be bumped when you
publish changes.
