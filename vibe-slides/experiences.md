# Build-agent experiences

Cross-project lessons accumulated from past `/build-slides` runs — corrections, gotchas, and pattern tweaks that should carry from one deck to the next.

**The build agent reads this every build, alongside the project's `vibe-slides.md`.** On conflict, project-level `vibe-slides.md` wins (project beats global). Otherwise, every rule below is binding.

Add new entries as `## <short topic>` with a one-line rule and a brief **Why:** so future-you can judge edge cases. Keep entries terse — this file is read on every build.

<!-- entries below -->
