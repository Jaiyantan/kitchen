---
name: kitchen
description: Use when building, wiring, testing or debugging an AI agent or workflow with the kitchen framework (Node, Flow, shared state, async/batch variants). Also use whenever the person says "cook with kitchen" (or "let's cook", "cook up <goal>") - that phrase means run the full procedure in "the trigger phrase" section below. Load this before writing the first node of a new agent, and before touching an existing kitchen graph.
---

# kitchen

kitchen models an agent as a graph. Three parts, nothing else:

- **Node** - one job. Runs `prep(shared)` → `exec(prep_res)` → `post(shared, prep_res, exec_res)`, and `post` returns a label.
- **Flow** - reads the label the current node returned, looks it up in that node's `successors`, and runs whatever is wired there. Stops when nothing matches.
- **shared** - one plain dict every node reads from and writes to. Nothing passes directly between nodes; it all goes through this dict.

An agent and a plain pipeline are the same graph. The only difference is whether `post()` computes its label from a fixed rule (pipeline) or from a judgment call over `shared` (agent, e.g. a tool-choice decided by an LLM call inside `exec()`).

## The trigger phrase: "cook with kitchen"

When the person says "cook with kitchen", "let's cook", or "cook up <something>", treat it as shorthand for the whole procedure below, not just a request to write some nodes. Do this, in order, without being asked again:

1. **Get the goal, tools, and done-condition in one exchange.** If the message after the trigger phrase already states what the agent should do, what it can call, and what "finished" means, extract those three from it. If any of the three is missing, ask for exactly that and stop - don't guess a tool list or a success condition.
2. **Write the shared-state schema and the node list, then stop and show them.** Follow `references/development-flow.md` steps 1 and 2. Present both as short lists, not prose. Wait for a go-ahead before writing a single class - unless the person's message included "no checkpoints" or "don't stop", in which case proceed straight through and just narrate each step as you do it.
3. **Write every node with `exec` stubbed, wire the graph, then stop and show `flow.validate()` and `flow.to_mermaid()`.** This is `references/development-flow.md` steps 3-4. Again, wait for a go-ahead unless checkpoints were waived.
4. **Replace stubs with real logic one node at a time** (step 6), add retries/fallback deliberately (step 7), add concurrency only once the serial version is proven correct (step 8).
5. **Finish by re-running `validate()` and regenerating the diagram** (step 10), and say in one or two sentences what was built and where the diagram is.

The two checkpoints (after step 2, after step 4) are the point of the trigger phrase - they're what stop a wrong graph from turning into three debugged-the-hard-way LLM calls. Don't skip them silently just because the request sounded simple.

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
