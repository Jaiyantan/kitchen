# Testing nodes and flows

No special test runner or fixtures are needed - `kitchen.py` has no dependencies, and neither do its tests. `test_kitchen.py` in this repo is the pattern: plain `assert` statements in `test_*` functions, run directly with `python test_kitchen.py` or under `pytest`.

## Test a node in isolation before wiring it

A node's three methods are plain functions of their arguments - test them without a `Flow` at all:

```python
def test_decide_picks_search_when_no_notes_yet():
    node = Decide()
    shared = {"goal": "find the capital of France", "notes": []}
    prep_res = node.prep(shared)
    label = node.post(shared, prep_res, node.exec(prep_res))
    assert label == "search"
```

Stub out whatever `exec` calls (the LLM, the API) rather than hitting the real thing - a node's `exec` is deliberately the only method that talks to the outside world, which is exactly what makes it easy to substitute in a test.

## Test routing with trivial nodes, not real ones

To check that a graph is wired the way you think, don't run it with real LLM calls - use nodes whose `post()` just returns a fixed label and records that it ran, the way this repo's `test_kitchen.py` does with its `Step` helper:

```python
class Step(Node):
    def __init__(self, name, label=None):
        super().__init__(name=name)
        self.label = label

    def post(self, shared, p, e):
        shared.setdefault("trace", []).append(self.name)
        return self.label

def test_burnt_path_returns_to_chop():
    chop, cook, serve = Step("chop", "ok"), Step("cook", "burnt"), Step("serve")
    chop >> cook
    cook - "burnt" >> chop
    cook - "ok" >> serve
    # won't terminate if the routing is wrong - give it a budget
    shared = {}
    try:
        Flow(chop, max_steps=5).run(shared)
    except RuntimeError:
        pass
    assert shared["trace"][:2] == ["chop", "cook"]
```

This separates "is the graph wired correctly" from "does the real `exec` logic work" - test both, separately. A wiring bug and a logic bug look identical from the outside (wrong final answer); this split is what lets you tell them apart quickly.

## Test retries and fallback with a counter, not a flaky real call

```python
def test_retries_then_succeeds():
    class Flaky(Node):
        def exec(self, _):
            if self.cur_retry < 2:
                raise ValueError("not yet")
            return "ok"
    node = Flaky(max_retries=3)
    assert node._exec(None) == "ok"
```

`self.cur_retry` is readable inside `exec`, which is what makes a deterministic retry test possible without sleeping or mocking a clock.

## Before trusting a new flow, check the graph itself

```python
flow = Flow(start, max_steps=20)
assert flow.validate() == []          # or inspect what it returns
```

Put this in a test for any flow with branches or loops. It catches the two cheapest-to-prevent, most-annoying-to-debug mistakes - a dead end you didn't mean, and a cycle with no `max_steps` - without needing to run the flow at all.

## What to stub, what to let run for real

- Stub: anything that costs money, calls a real LLM, hits a real network, or is non-deterministic.
- Let run for real: `prep`/`post` logic, routing, retries, the graph structure itself.
- Write one slower end-to-end test with real calls, kept separate (a different file or a marker) from the fast unit tests above, so the fast suite can run on every change.
