# Designing shared state

`shared` is one dict. Every node can read any key and write any key. That freedom is also the entire risk surface of this framework - nothing stops one node from overwriting a key another node is still relying on, because there's no schema enforcing it.

## Write the shape down before writing any node

Before the first `class` statement, write what you expect `shared` to look like at each stage, even just as a comment:

```python
# shared = {
#     "goal": str,            # set once, at the start, never written again
#     "notes": list[str],     # append-only, written by every tool node
#     "chosen_tool": str,     # overwritten each loop by decide
#     "final_answer": str,    # written once, by the terminal node
# }
```

This is the only design document this framework forces on you. Skipping it is how two nodes end up fighting over the same key.

## `shared` vs `self.params`

- **`shared`** is the run's accumulating memory - things that get read by a *later* node because an *earlier* node produced them. If node B needs something node A computed, it goes in `shared`.
- **`self.params`** is per-run configuration handed down from the `Flow` via `set_params()` - the same value, unchanged, available to every node for the duration of one run. Use it for things like a user ID, a request ID, a feature flag - settings, not results. Don't put something in `params` that one node is supposed to write and another supposed to read; that's what `shared` is for. Don't put something in `shared` that never changes for the whole run and isn't produced by any node; that's what `params` is for.

## Keeping it small (memory)

- **Write only what the next node needs, not everything you have.** A node that fetched a 50-page document and only needs three facts from it should write the three facts to `shared`, not the whole document, unless a later node genuinely needs the whole document again.
- **Prefer overwriting a key to appending, unless you actually need history.** `shared["notes"].append(...)` is right when a later decision depends on everything gathered so far (classic agent scratchpad). `shared["latest_result"] = ...` is right when only the most recent value matters. Appending by default is the most common way this kind of framework's memory use grows without bound across a long-running loop.
- **Drop what you're done with.** If a key was only needed to get from node A to node B and nothing downstream reads it, `del shared[key]` in B's `post()` (or whichever node is the last reader). The framework won't do this for you - there's no lifetime tracking on keys, which is also why it's cheap and has no other overhead.
- **BatchFlow and parallel batch runs share the same `shared` dict across all items** unless you partition it. If five items run through `AsyncParallelBatchFlow` and each writes `shared["result"]`, they clobber each other. Give each item its own key (`shared[f"result_{item_id}"]`), or better, have each item's sub-flow return its result instead of writing to a shared key, and collect results in the batch node's own `post()`.

## A node's `self` is not shared state

Every step of a `Flow` runs on a shallow copy of the node (`copy.copy`), specifically so that something a node writes to `self` during one run doesn't leak into the next run or into a sibling run executing in parallel. Don't rely on `self.anything` surviving between calls to the same node instance across different `Flow.run()` calls - if it needs to survive, it belongs in `shared`, not on the node.
