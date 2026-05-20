# hai

A marketplace of Claude Code plugins by Yuexuan Zhang.

## Install

In Claude Code, add this marketplace once, then install any plugin from it:

```
/plugin marketplace add <your-github-username>/hai
/plugin install pin@hai
```

Replace `<your-github-username>` with the GitHub account this repo lives under.
After installing, run `/reload-plugins`. The skill or command names are then
namespaced by plugin, e.g. `/pin:pin-aware-agent`.

To pick up later updates:

```
/plugin marketplace update hai
```

## Plugins

| Plugin | What it does |
|--------|--------------|
| [`pin`](./pin) | Pin + Protocol disciplines for agent-driven research — lock design decisions against silent rollback, make every conclusion-bearing data element traceable to code, and keep the human genuinely in the loop via machine audit, an adversarial Codex audit, and an interactive grounding quiz. |

## Repository layout

```
hai/
├── .claude-plugin/
│   └── marketplace.json   # the marketplace: lists every plugin
├── pin/                   # one plugin = one subdirectory
│   └── .claude-plugin/plugin.json
└── README.md
```

## Adding another plugin

1. Put the plugin in its own subdirectory with a `.claude-plugin/plugin.json`
   (it does **not** need its own `marketplace.json`).
2. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./<dir>"`.
3. Commit and push — users get it with `/plugin marketplace update hai`.

Plugin entries omit `version`, so every pushed commit is treated as a new
version and `marketplace update` always pulls the latest.
