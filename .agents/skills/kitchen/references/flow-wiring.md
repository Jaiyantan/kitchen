# Wiring a flow

## Basic edges

```python
a >> b                  # after a, go to b, on label "default"
a - "burnt" >> c        # after a, if it returned "burnt", go to c instead
```

A node can have any number of labeled successors. `a >> b` is shorthand for `a.next(b, label="default")`. Wiring the same label twice on one node overwrites the first and warns - that's almost always a bug (you meant a different label, or you're wiring the same node twice by accident).

## Branching

Wire every label a node's `post()` can actually return. If `post` returns `"burnt"` and nothing is wired to that label on that node, the Flow stops there - silently finishing the run, not crashing, with a `UserWarning` ("Flow ends: label 'burnt' not found..."). That warning is the signal; if you see it and didn't expect the flow to end there, you forgot an edge.

## Loops

```python
cook - "burnt" >> chop     # send the work back a step
```

Looping is just an edge that points at a node already in the path. Nothing about the mechanism is different from any other edge - but always pair a loop with `max_steps`:

```python
Flow(chop, max_steps=20).run(shared)
```

Without it, a routing bug that returns the same label forever runs forever. `flow.validate()` tells you if you forgot - it detects cycles in the wired graph and flags them if `max_steps` is `None`.

## Nesting

A `Flow` is itself a `Node` - it has `prep`/`exec`/`post` like any node, it just runs a sub-graph in the middle. This means:

- You can wire a `Flow` as a step inside a bigger `Flow`: `outer_flow - "label" >> inner_flow`.
- The inner flow's last label becomes its return value to the outer flow (its default `post` just returns it), so the outer flow can route on what happened inside the inner one.
- If you want the sub-flow to do more than pass the label through, override its `prep`/`post` - they run once, before and after the whole sub-graph, not per node inside it.

Use nesting when a chunk of the graph is a reusable unit (e.g. a "research" sub-flow you plug into three different agents) - not as a way to avoid naming nodes. If you're nesting a one-node flow just to avoid writing `Flow(single_node)` at the call site, that's unnecessary indirection.

## `flow.start(node)`

Lets you build the `Flow` object before you've finished wiring:

```python
f = Flow()
start = f.start(chop)
start >> cook >> serve
f.run(shared)
```

Equivalent to `Flow(chop)`. Only useful when something else about the flow (like `max_steps`) needs to be set before you've decided the first node.

## What `set_params` is for, here

`flow.set_params({...})` pushes the same dict into `self.params` on every node the flow runs - read `references/shared-state.md` for when to use `params` instead of `shared`.
