---
name: kitchen
description: Use when building, wiring, testing or debugging an AI agent or workflow with the kitchen framework (Node, Flow, shared state, async/batch variants). Load this before writing the first node of a new agent, and before touching an existing kitchen graph.
---

# kitchen

kitchen models an agent as a graph. Three parts, nothing else:

- **Node** - one job. Runs `prep(shared)` → `exec(prep_res)` → `post(shared, prep_res, exec_res)`, and `post` returns a label.
- **Flow** - reads the label the current node returned, looks it up in that node's `successors`, and runs whatever is wired there. Stops when nothing matches.
- **shared** - one plain dict every node reads from and writes to. Nothing passes directly between nodes; it all goes through this dict.

An agent and a plain pipeline are the same graph. The only difference is whether `post()` computes its label from a fixed rule (pipeline) or from a judgment call over `shared` (agent, e.g. a tool-choice decided by an LLM call inside `exec()`).

## Route by task

| Task | Read |
|---|---|
| Writing a new node: `prep`/`exec`/`post`, retries, fallback | `references/node-authoring.md` |
| Wiring nodes into a graph: branching, loops, nesting, `max_steps` | `references/flow-wiring.md` |
| Deciding what belongs in `shared` vs `self.params`, keeping it small | `references/shared-state.md` |
| Running things concurrently, or over a list of items | `references/async-and-batch.md` |
| Writing tests for a node or a flow | `references/testing-agents.md` |
| Something is looping forever, warning, or routing to the wrong node | `references/debugging.md` |
| Starting a new agent from scratch, step by step | `references/development-flow.md` |

## Before writing any code

Run this check on every task, out loud, before opening an editor:

1. What are the distinct jobs? Each one is a node. If you can't name the job in three words, it's probably two nodes.
2. For each job: is "what happens next" fixed, or does it depend on what just happened? Fixed → a plain `>>` edge. Depends → the node's `post()` has to compute a label from `shared`, and there should be more than one wired successor for it to choose between.
3. What does every node need to read, and what will it write back? That list is the shape of `shared`. Write it down (a comment, a `TypedDict`, whatever) before writing the first node - see `references/shared-state.md`.
4. Does any edge point back to a node already in the path? If yes, the graph has a cycle - set `max_steps` on the `Flow` immediately, don't wait until it hangs.

## Two commands to run before trusting a new graph

```python
flow = Flow(start, max_steps=20)
print(flow.validate())     # structural issues: dead ends, unguarded cycles
print(flow.to_mermaid())   # paste into mermaid.live - this is the actual graph you wired, not the one you think you wired
```

`validate()` and `to_mermaid()` walk `start.successors` recursively; they tell you about the graph as written, which is the fastest way to catch a mis-wired edge before it costs you a debugging session against a live LLM call.
