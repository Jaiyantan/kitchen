# Building an agent with kitchen, start to finish

Follow this order. Every step after the first exists to catch a mistake before it costs a debugging session against a real LLM call.

## 1. Write the shared-state schema first, before any node

A comment or a `TypedDict` listing every key the run will use, who writes it, and who reads it. See `references/shared-state.md`. If you can't write this yet, you don't understand the task well enough to write nodes for it - this step is cheap, skipping it isn't.

## 2. List the nodes on paper before writing a class

One line per node: its name, what it reads, what it does, what it writes, what label(s) it can return. For a decision node, list every label it might return and which tool each one maps to - this list becomes your wiring in step 4.

A rule of thumb for splitting nodes: if a step needs its own retry policy, or you want to test it in isolation, or a human description of it needs "and", it's its own node.

## 3. Write every node, stubbing `exec`

Write the full `prep`/`post` for every node for real - they're pure logic, there's no reason to fake them. Stub `exec` with a hardcoded return value for now (`return "stub answer"`), especially for anything that calls an LLM or an external API. This lets you get the routing right before paying for a single real API call.

## 4. Wire the graph, then validate it before running anything

```python
flow = Flow(start, max_steps=20)   # set max_steps now if there's any loop, not after it hangs
print(flow.validate())
print(flow.to_mermaid())           # paste into mermaid.live, check it's the shape you meant
```

Fix every issue `validate()` reports. Compare the mermaid diagram against the list from step 2 - a missing or extra edge is far cheaper to catch here, looking at a picture, than by debugging a wrong final answer three steps later.

## 5. Run the stubbed graph end to end

With `exec` still stubbed, run the flow with a realistic `shared` dict and confirm the trace through nodes matches what you expect (use the `Step`-style pattern from `references/testing-agents.md` for a dry run with no real logic at all, before even your stubbed real nodes). This is the point where a routing bug (step 2 said the agent should branch to node X, but it branches to node Y) is cheapest to find.

## 6. Replace stubs with real `exec` logic, one node at a time

Swap in the real LLM call / API call / tool invocation for one node, test that node in isolation (`references/testing-agents.md`), then move to the next. Don't wire up every real call at once - if something breaks, you want to know which node broke it.

## 7. Add retries and fallbacks deliberately

For every node whose `exec` now does real I/O: decide on purpose whether failure should retry (`max_retries`, `wait`), degrade (`exec_fallback`), or stop the run (the default - re-raise). Don't leave this to the default everywhere; a node calling a flaky API with no retry and no fallback will take down runs that a `max_retries=3` would have survived.

## 8. Add concurrency only after step 6 is correct serially

If you need a batch of independent items processed faster, swap the relevant `Node`/`Flow` for its `Async*BatchNode`/`Async*BatchFlow` counterpart (`references/async-and-batch.md`) - only after the sequential version is correct. Parallelizing a graph you haven't finished debugging multiplies the number of things that can go wrong at once, and shared-state writes that were safe one-at-a-time can start clobbering each other the moment they run concurrently.

## 9. Write the tests you skipped while moving fast

By now you have: per-node unit tests (step 6), a routing test with trivial `Step` nodes (step 5, formalized), and `flow.validate()` as an assertion in a test rather than a print statement. Add one slower end-to-end test with real calls, kept separate from the fast suite.

## 10. Before shipping: re-run `validate()` and regenerate the diagram

Graphs drift as you iterate - an edge added in step 6 while debugging something, forgotten. Re-run both checks from step 4 one more time against the final wiring, and keep the `to_mermaid()` output (or a rendering of it) next to the code as documentation; it's generated from the actual graph, so it can't go stale the way a hand-drawn diagram does.
