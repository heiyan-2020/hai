# Safeguard

A native Claude Code plugin for automatic English input translation and local
JSONL after-send auditing. It uses the official mods APIs. No Python, Node.js,
custom launcher, shell function, Herdr build, or HTTP proxy is required. Model
requests and authentication remain owned by Claude Code.

Install from the hai marketplace:

```sh
claude plugin install safeguard --marketplace heiyan-2020/hai
```

Configure the translation API URL, model and API key in `/plugin` → Safeguard →
Configure. The key is a sensitive native plugin option; it is not included in
this package. Then start Claude normally in any project and type as usual.
On hosts without secure credential storage, leave the key option unset and set
`API key file` to an absolute UTF-8 file path containing only the key. Keep that
file private (`chmod 600` on Unix), outside the plugin and any repository.
Use `/safeguard-audit` to inspect diagnostics. The plugin never edits skill files.

## Translation request settings

DeepSeek models use `thinking: {"type":"disabled"}` and `reasoning_effort: "none"`
by default. This is shared by input translation and optional display translation.
Other model names do not receive these DeepSeek-specific fields. The **Disable
DeepSeek thinking** option can be turned off for a provider that needs its defaults.

**Translation max output tokens** defaults to **32768** and accepts integer values
from 256 through 131072 (for example 65536). Set it in `/plugin` → Safeguard →
Configure. It is a generation ceiling, not a target length; provider limits still
apply. Input or output truncated by the provider is never accepted as complete.

Failed display rows now show a safe reason: HTTP status, network failure, timeout,
output truncation with the configured token limit, invalid/empty JSON, language
validation, or changed protected literals. Raw provider errors, prompts, and
credentials are never included in the label. The original stays visible, and
`/safeguard-display retry` retries the failed blocks. Older versions discarded
these details, so a previous generic failure cannot be diagnosed retroactively.

## Optional Chinese response display

Enable **Translate assistant display to Chinese** in `/plugin` → Safeguard →
Configure. English responses stream normally. After the turn finishes, visible
assistant text blocks are translated in the background and replaced in place in
the terminal. Native Markdown rendering is retained.

A single live progress pane shows the active block number, a short source excerpt,
elapsed seconds, and a completed/total bar. In wide terminals it docks at the upper
right; if the native UI defers the pane at narrow widths, a compact pinned status
shows the same progress. It does not repeatedly post toasts. Each assistant block
also carries a waiting, translating, translated, unchanged, or failed label.
Counts cover currently visible distinct text blocks plus any in-flight block;
scrolling can change the total. A failed block counts as processed and is called
out separately. The translation API provides no within-request percentage.
The panel closes three seconds after completion and closes immediately when
original display is selected. Closing it manually keeps it dismissed until
`/safeguard-display zh` is run; compact status remains available. Tool rows, permission
dialogs, thinking blocks, and nonterminal surfaces are not rewritten.

This sends assistant prose to your configured translation provider as well as
submitted input. Fenced code, inline code, and link destinations are masked
locally and restored exactly. This option is off by default.

`/safeguard-display original` shows original text; `/safeguard-display zh` enables
Chinese display for this session; `/safeguard-display retry` retries failed
translations. These commands only affect the UI and do not start model turns.
The original English remains in JSONL and subsequent model requests. Translations
are cached only in bounded session memory. A failed or truncated translation
leaves the original visible; no response text is lost. Very large text blocks
(over 100,000 characters) also keep the original. Restarting may translate visible
history again. This is turn-complete translation, not token-by-token translation.

The input is translated automatically on Enter. Failed/incomplete translations,
changed code/URL literals and remaining Chinese drop the submission. This first
version accepts text only. Language and semantic judgments partly rely on the
translation model. Only submitted input goes to that provider; audit context stays
local. Missing translation configuration blocks submissions while the plugin is
loaded. Disabling the plugin also disables its protection.

Context inspection is AFTER SEND. Recorded requests are rebuilt from shape,
message hashes, base/keep/tail deltas and cache overlays, and verified against the
recorded SHA-256 request digest. Unknown schemas, missing data and corruption do
not count as clean. Some model calls, notably compaction in the tested build,
are not recorded. Attribution, metadata and transport headers are omitted from
these records. This is not a full network-request guarantee.

Translation requires the native mods API (introduced in the Claude 2.1 series;
the APIs used here are documented for 2.1.299+). There is no exact patch-version
lock. Tested on 2.1.319; future request-log formats are accepted only when digest
verification succeeds. Use `claude plugin validate` to check the installed CLI's
understanding of the plugin. Unsupported/missing logs produce coverage warnings.

Small logs use native file reads. Larger logs use bounded reads through standard
OS utilities (`sh`, `dd`, `base64` on macOS/Linux, PowerShell on Windows), avoiding
the native file-read size ceiling without another language runtime. The Windows
reader is implemented but not validated on a Windows host. Audit summaries keep
the last 20 findings for up to 20 sessions in Claude's native plugin store; the
original JSONL is the complete source. Notifications use native UI only, are
deduplicated, and never write directly into a TUI or enter model context.

Optional local rule files contain an array (or a `rules` array) of rules:

```json
[{"type":"deny_pattern","scope":"all","pattern":"company-secret","flags":"i"}]
```

Scopes: `prompt` blocks submission, `context` reports after sending, `all` does
both. Patterns use JavaScript regular expressions; leading `(?i)`, `(?m)`, `(?s)`
are also accepted. Keep patterns simple. Built-in language checks stay enabled.

Run `claude plugin test` in this directory for isolated unit tests. The repository
also includes `tests/integration.py`, a real-CLI integration test using mock APIs
and fake credentials. Run `python3 tests/integration.py .` from this plugin
directory; Python is only needed for this development test.
For the real terminal test on macOS/Linux, install `pyte` in a development Python
environment and run `python3 tests/tui_integration.py .`. It checks actual screen
replacement, original/Chinese toggling, code masking, unchanged follow-up model
history, and unchanged assistant JSONL, using localhost APIs and fake credentials.

## Data flow and visibility

Every nonempty submitted text prompt, including already English input, goes to
your configured translation provider. That provider receives the original text
and a translation instruction. The translated input is passed to native Claude
Code, which assembles context and sends the model request using its own network
client and credentials. This plugin does not implement a model API proxy.

The plugin does not append its audit findings, rule files, translation key, or
translation instruction to model context. Audit reads and source-file matching
are local. Optional response display translation sends masked assistant prose
to the translation provider, but never writes the translation into model history. Chinese text elsewhere in existing context, files, skills, or tool
results may already reach the model before the after-send audit reports it.

This does not promise invisibility to Anthropic. Claude Code owns request
metadata and its separate analytics/error-reporting channels. Its documented
plugin analytics can report installation or usage activity; visibility depends
on trust tier and telemetry settings. This plugin does not alter those settings.
See [plugin measurement](https://code.claude.com/docs/en/plugins/measure) and
[data usage](https://code.claude.com/docs/en/data-usage). No claim is made that
its traffic is byte-for-byte identical to a session without plugins.

This plugin requires Claude Code Mods APIs and is not a Codex plugin.
