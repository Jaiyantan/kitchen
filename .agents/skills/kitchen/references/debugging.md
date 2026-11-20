# Debugging a kitchen graph

Start with these two calls, before reading further - they catch most of what's below without running the flow at all:

```python
flow = Flow(start, max_steps=20)
print(flow.validate())
print(flow.to_mermaid())   # paste into mermaid.live and look at the actual shape
```

## "UserWarning: Flow ends: label 'x' not found in [...]"

A node's `post()` returned a label with nothing wired to it on that node. This is not a crash - the flow just stops there, which is often worse, because the run looks like it finished successfully with a half-done result.

Fix: either wire the missing edge (`node - "x" >> next_node`), or check whether `post()` should have returned a different label (the label it returned might be a bug in the node's own logic, not a missing edge).

## The flow never returns (hangs, or `RuntimeError: Flow exceeded max_steps`)

The graph has a cycle, and the routing logic that's supposed to eventually break out of it isn't doing so. Check, in order:

1. Is `max_steps` set at all? If not, you'll hang instead of getting a clear error - set it, always, on any flow with a loop, even during development.
2. Is the condition that's supposed to exit the loop actually reachable? Print `shared` at the top of the deciding node's `post()` and look at what it's branching on across iterations - often a counter or flag isn't being updated the way you think.
3. Run `flow.validate()` - if it reports a cycle with no `max_steps`, that confirms the shape; it won't tell you *why* the exit condition isn't firing, but it confirms where to look.

## "UserWarning: Overwriting successor for label 'x'"

Two `node - "x" >> ...` calls (or a `>>` and a `- "x" >>`) targeted the same label on the same node. The second wiring silently wins. Usually either a copy-paste edge that should have used a different label, or the same node accidentally wired twice during setup (e.g. inside a loop that builds the graph).

## "TypeError: ... is async, run it with AsyncFlow"

A plain `Flow` hit an `AsyncNode` while walking the graph. Change `Flow(start).run(shared)` to `await AsyncFlow(start).run(shared)` - nothing about the node needs to change, a sync `Flow` just refuses to run async nodes rather than silently mishandling the coroutine.

## A node's result from the previous run is showing up again

Something is being read from `self` (an attribute set in a previous call) instead of from `shared`. Each step of a `Flow` runs on a shallow copy of the node specifically to prevent this, but a *mutable* attribute set in `__init__` (a list or dict) is still the same object across copies - if you did `self.cache = []` in `__init__` and append to it in `exec`, every copy shares that one list. Move anything that needs to vary per run into `shared`, not `self`.

## Two parallel items in a batch run clobbered each other's result

Classic: `AsyncParallelBatchFlow` ran N items concurrently, all N copies wrote to the same `shared["result"]` key, and only the last one to finish survived - silently, no warning. See the "hazard" section in `references/async-and-batch.md`. Key writes by item id, or collect results in the batch node's own `post()` instead of through `shared`.

## The agent keeps picking a tool that isn't wired

If a decision node's `exec()` can return a label (say, from an LLM choosing a tool name) that has no corresponding `node - "that_label" >> ...` edge, the flow silently ends instead of erroring (see the first entry above). `flow.validate()` won't catch this - it only inspects edges you actually wired, not labels a node *might* produce. The fix is discipline at the source: define the candidate labels once (constants, an enum, whatever) and use the same set both when constraining what the decision call can return and when wiring successors, so the two can't drift apart.
