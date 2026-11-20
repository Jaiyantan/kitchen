# Async and batch nodes

## When to reach for which

| You have | Use |
|---|---|
| One job, synchronous | `Node` |
| One job, needs `await` (async LLM/API client) | `AsyncNode` - same methods, `async def prep/exec/post/exec_fallback` |
| One job, applied to a list, one at a time | `BatchNode` - `prep` returns a list, `exec` runs once per item |
| One job, applied to a list, all at once | `AsyncParallelBatchNode` - same shape, items run concurrently via `asyncio.gather` |
| A whole sub-graph, run once per item, one at a time | `BatchFlow` / `AsyncBatchFlow` - `prep` returns a list of params dicts |
| A whole sub-graph, run once per item, all at once | `AsyncParallelBatchFlow` |

Default to the sequential version first. Reach for the parallel version only once the sequential one is correct - see `references/development-flow.md`.

## Writing an async node

Method names don't change - `prep`, `exec`, `post`, `exec_fallback` - just write them as `async def` and `await` inside them:

```python
class CallLLM(AsyncNode):
    async def prep(self, shared):
        return shared["prompt"]

    async def exec(self, prompt):
        return await async_llm_client.complete(prompt)

    async def post(self, shared, prep_res, exec_res):
        shared["response"] = exec_res
```

Run the containing flow with `await AsyncFlow(start).run(shared)`.

## Mixing sync and async in one graph

`AsyncFlow` runs both kinds: it awaits an `AsyncNode`, and runs a plain `Node` synchronously in the same loop. A plain `Flow` refuses to run an `AsyncNode` at all - it raises `TypeError` immediately rather than silently getting back a coroutine it never awaits. If you see that error, the fix is almost always to wrap the whole graph's `.run()` call in `AsyncFlow` instead of `Flow`, not to change the node.

## Batch nodes: order and concurrency

`BatchNode` and `AsyncBatchNode` preserve input order and run items one after another - safe default, predictable, no surprises if items depend on shared resources with limited concurrency (rate limits, a single DB connection).

`AsyncParallelBatchNode` still returns results in input order, but all items start at once via `asyncio.gather`. Use it when items are genuinely independent (different API calls, different files) and the cost of running serially would dominate. Don't use it when items share a mutable resource you haven't made concurrency-safe - see the `shared` warning below.

## The one real hazard: parallel runs writing to the same `shared`

`AsyncParallelBatchFlow` runs N copies of a sub-graph concurrently, but every copy gets the *same* `shared` dict unless the sub-graph's nodes are careful. If each item's nodes write to `shared["result"]`, the last one to finish wins and the other N-1 results are gone - silently, no error, no warning. Either:

- key writes by the item's id (`shared[f"result_{self.params['id']}"]`), using `self.params` to carry that id in (the per-run node copy means `self.params` set via `set_params` is safe to read inside a parallel run), or
- have the sub-graph's terminal node return the result as a label-adjacent value collected by the batch node's own `post()`, rather than writing into the shared dict at all.

This is the only place in the framework where "shared state" and "concurrent" combine dangerously. Everywhere else, the shallow-copy-per-step behavior means a node's own `self` state can't leak between parallel runs - it's specifically `shared`, because it's deliberately *not* copied, that needs this discipline from you.
