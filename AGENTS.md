# Agent instructions for this repo

This is the `kitchen` framework: an AI agent is a graph of `Node`, `Flow`, and a shared dict. Full instructions for building with it live in a skill at `.agents/skills/kitchen/SKILL.md` - **read that file before writing or editing any node, flow, or agent in this repo.** It routes you to task-specific references (writing a node, wiring a flow, shared-state design, async/batch, testing, debugging, the full build process) rather than dumping everything into this file.

## If your tool reads `.agents/skills/` directly

Nothing to do - point it at `.agents/skills/kitchen/SKILL.md` (Cursor, Antigravity, Codex, and other tools that follow the open Agent Skills format read this path already).

## Claude Code

Claude Code looks in `.claude/skills/`, not `.agents/skills/`. Symlink or copy it once per clone:

```bash
mkdir -p .claude/skills
ln -s ../../.agents/skills/kitchen .claude/skills/kitchen
```

## Quick facts, if you read nothing else

- `kitchen.py` is the entire framework, no dependencies.
- Run `python test_kitchen.py` before and after any change to `kitchen.py` - it has no test runner dependency either.
- Before trusting a graph you wired, run `Flow(start).validate()` and `Flow(start).to_mermaid()` - see `.agents/skills/kitchen/SKILL.md`.

## For developers using this repo

To build a new agent, say: **"cook with kitchen: `<goal>`, tools are `<what it can call>`, done when `<what counts as finished>`"**. The skill knows what to do with that phrase - it runs the full build procedure itself, with two checkpoints before it writes real logic or makes a real call. You don't need to write out the development flow by hand.
