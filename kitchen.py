"""
kitchen: a minimalist framework for building AI agents.

An agent is a graph with three parts:

    Node   -> a station in the kitchen (chopping, cooking, serving). Does the work.
    Flow   -> the recipe. Reads the label a node returns and picks the next node.
    shared -> the kitchen storage. A plain dict every node can read and write.

Each node runs in three steps:

    prep(shared)                  read what it needs from the store
    exec(prep_res)                do the actual work (call an LLM, a tool, anything)
    post(shared, prep_res, exec_res) -> label
                                  write results back, return a label for the Flow

Wiring:

    a >> b                 after a, go to b      (label "default")
    a - "burnt" >> c       if a returns "burnt", go to c
    flow.start(a)          set the start node after creating the Flow

The Flow stops when the current node has no successor for the returned label
(with a warning if the node had other successors). A Flow is itself a Node, so
flows nest. A Flow's own prep runs before its graph and its post runs after;
by default post returns the graph's last label.

Extras:

    Node(max_retries=3, wait=1)   retry exec on error, then call exec_fallback
    Node(name="chop")             a readable name, used in warnings and diagrams
    self.params                   per-run settings a Flow hands to every node
    BatchNode / BatchFlow         run exec per item / run the graph per params dict
    Flow(start, max_steps=50)     stop a runaway agent loop
    flow.to_mermaid()             render the wired graph as a diagram you can view
    flow.validate()               list structural issues before you run anything

Each step of a Flow runs on a shallow copy of the node, so anything a node
stores on `self` stays within that run. Mutable attributes set in __init__
(a list, a dict) are still shared between copies.

Async: subclass AsyncNode and write `async def prep/exec/post/exec_fallback`,
then `await AsyncFlow(start).run(shared)`. AsyncFlow mixes sync and async nodes.
A plain Flow refuses async nodes.
"""

import asyncio
import copy
import time
import warnings

DEFAULT = "default"


class Node:
    def __init__(self, max_retries=1, wait=0, name=None):
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        self.name = name or type(self).__name__  # shown in warnings and diagrams
        self.params = {}
        self.successors = {}
        self.max_retries = max_retries
        self.wait = wait
        self.cur_retry = 0  # which try is running, readable inside exec

    # ---- the work: override these ----

    def prep(self, shared):
        return None

    def exec(self, prep_res):
        return None

    def exec_fallback(self, prep_res, exc):
        raise exc  # called after the last failed try; override to recover

    def post(self, shared, prep_res, exec_res):
        return DEFAULT

    # ---- running ----

    def set_params(self, params):
        self.params = params

    def run(self, shared):
        if self.successors:
            warnings.warn(f"{self.name}.run() won't follow successors. Use a Flow.")
        return self._run(shared)

    def __repr__(self):
        return f"<{self.name}>"

    def _run(self, shared):
        prep_res = self.prep(shared)
        exec_res = self._exec(prep_res)
        return self.post(shared, prep_res, exec_res)

    def _exec(self, prep_res):
        for self.cur_retry in range(self.max_retries):
            try:
                return self.exec(prep_res)
            except Exception as exc:
                if self.cur_retry == self.max_retries - 1:
                    return self.exec_fallback(prep_res, exc)
                if self.wait > 0:
                    time.sleep(self.wait)

    # ---- wiring ----

    def next(self, node, label=DEFAULT):
        if label in self.successors:
            warnings.warn(f"Overwriting successor for label '{label}'")
        self.successors[label] = node
        return node

    def __rshift__(self, node):
        return self.next(node)

    def __sub__(self, label):
        if not isinstance(label, str):
            raise TypeError("edge label must be a string")
        return _Edge(self, label)


class _Edge:
    """Holds `node - "label"` until `>> target` completes it."""

    def __init__(self, src, label):
        self.src, self.label = src, label

    def __rshift__(self, node):
        return self.src.next(node, self.label)


class BatchNode(Node):
    """prep returns a list; exec runs once per item (each with its own retries)."""

    def _exec(self, items):
        return [Node._exec(self, item) for item in items or []]


class Flow(Node):
    """The recipe: walks the graph from the start node, routing on each label."""

    def __init__(self, start=None, max_steps=None, name=None):
        super().__init__(name=name)
        self.start_node = start
        self.max_steps = max_steps  # optional guard for agent loops

    def start(self, node):
        self.start_node = node
        return node

    def post(self, shared, prep_res, exec_res):
        return exec_res  # pass the graph's last label up to a parent Flow

    def _run(self, shared):
        prep_res = self.prep(shared)
        label = self._orch(shared)
        return self.post(shared, prep_res, label)

    def _orch(self, shared, params=None):
        curr, label, steps, params = self._begin(params)
        while curr is not None:
            self._check_steps(steps)
            if isinstance(curr, AsyncNode):
                raise TypeError(f"{type(curr).__name__} is async, run it with AsyncFlow")
            curr.set_params(params)
            label = curr._run(shared)
            curr = copy.copy(self._next(curr, label))
            steps += 1
        return label

    def _begin(self, params):
        if self.start_node is None:
            raise ValueError("Flow has no start node")
        params = dict(self.params) if params is None else params
        return copy.copy(self.start_node), None, 0, params

    def _next(self, curr, label):
        nxt = curr.successors.get(label or DEFAULT)
        if nxt is None and curr.successors:
            warnings.warn(f"Flow ends: label {label!r} not found in {list(curr.successors)}")
        return nxt

    def _check_steps(self, steps):
        if self.max_steps is not None and steps >= self.max_steps:
            raise RuntimeError(f"Flow exceeded max_steps={self.max_steps}")

    # ---- introspection: ask the graph about itself ----

    def to_mermaid(self):
        """Render the wired graph as a Mermaid flowchart definition.

        Paste the result into https://mermaid.live, a markdown file that
        renders Mermaid, or this project's doc tooling. A nested Flow is
        drawn as a single box (its own internal graph is not expanded).
        """
        if self.start_node is None:
            return "flowchart TD\n    %% (empty: no start node)"
        lines, ids, seen = ["flowchart TD"], {}, set()

        def node_id(n):
            if id(n) not in ids:
                ids[id(n)] = f"n{len(ids)}"
            return ids[id(n)]

        def walk(n):
            if n is None or id(n) in seen:
                return
            seen.add(id(n))
            lines.append(f'    {node_id(n)}["{n.name}"]')
            for label, nxt in n.successors.items():
                if nxt is None:
                    continue
                arrow = "-->" if label == DEFAULT else f"-->|{label}|"
                lines.append(f"    {node_id(n)} {arrow} {node_id(nxt)}")
            for nxt in n.successors.values():
                walk(nxt)

        walk(self.start_node)
        return "\n".join(lines)

    def validate(self):
        """Walk the graph and return a list of plain-English warnings.

        Catches the two most common agent-loop mistakes before you run
        anything: a node with no way forward, and a cycle with no max_steps
        to stop it if the routing logic never breaks out.
        """
        if self.start_node is None:
            return ["this flow has no start node"]
        issues, seen, has_cycle = [], set(), [False]

        def walk(n, path):
            if id(n) in path:
                has_cycle[0] = True
                return
            if id(n) in seen:
                return
            seen.add(id(n))
            if not n.successors:
                issues.append(f"'{n.name}' has no outgoing edges (fine if it's meant to end the flow)")
            for nxt in n.successors.values():
                if nxt is not None:
                    walk(nxt, path | {id(n)})

        walk(self.start_node, set())
        if has_cycle[0] and self.max_steps is None:
            issues.append("this graph has a cycle and max_steps is not set, a stuck loop would run forever")
        return issues


class BatchFlow(Flow):
    """prep returns a list of params dicts; the whole graph runs once per dict."""

    def _run(self, shared):
        batches = self.prep(shared) or []
        for bp in batches:
            self._orch(shared, {**self.params, **bp})
        return self.post(shared, batches, None)


# ---------------------------------------------------------------- async


class AsyncNode(Node):
    """Same steps, but awaitable. Override with `async def`."""

    async def prep(self, shared):
        return None

    async def exec(self, prep_res):
        return None

    async def exec_fallback(self, prep_res, exc):
        raise exc

    async def post(self, shared, prep_res, exec_res):
        return DEFAULT

    async def run(self, shared):
        if self.successors:
            warnings.warn(f"{type(self).__name__}.run() won't follow successors. Use AsyncFlow.")
        return await self._run(shared)

    async def _run(self, shared):
        prep_res = await self.prep(shared)
        exec_res = await self._exec(prep_res)
        return await self.post(shared, prep_res, exec_res)

    async def _exec(self, prep_res):
        for self.cur_retry in range(self.max_retries):
            try:
                return await self.exec(prep_res)
            except Exception as exc:
                if self.cur_retry == self.max_retries - 1:
                    return await self.exec_fallback(prep_res, exc)
                if self.wait > 0:
                    await asyncio.sleep(self.wait)


class AsyncBatchNode(AsyncNode):
    """Runs exec per item, one after another."""

    async def _exec(self, items):
        return [await AsyncNode._exec(self, item) for item in items or []]


class AsyncParallelBatchNode(AsyncNode):
    """Runs exec per item, all at once. Results keep the input order."""

    async def _exec(self, items):
        return list(await asyncio.gather(*(AsyncNode._exec(self, i) for i in items or [])))


class AsyncFlow(Flow, AsyncNode):
    """Like Flow, but awaits async nodes. Sync nodes and sync Flows run as is."""

    async def post(self, shared, prep_res, exec_res):
        return exec_res

    async def _run(self, shared):
        prep_res = await self.prep(shared)
        label = await self._orch_async(shared)
        return await self.post(shared, prep_res, label)

    async def _orch_async(self, shared, params=None):
        curr, label, steps, params = self._begin(params)
        while curr is not None:
            self._check_steps(steps)
            curr.set_params(params)
            if isinstance(curr, AsyncNode):
                label = await curr._run(shared)
            else:
                label = curr._run(shared)
            curr = copy.copy(self._next(curr, label))
            steps += 1
        return label


class AsyncBatchFlow(AsyncFlow):
    """Runs the graph once per params dict, one after another."""

    async def _run(self, shared):
        batches = await self.prep(shared) or []
        for bp in batches:
            await self._orch_async(shared, {**self.params, **bp})
        return await self.post(shared, batches, None)


class AsyncParallelBatchFlow(AsyncFlow):
    """Runs the graph once per params dict, all at once. Write to separate keys in shared."""

    async def _run(self, shared):
        batches = await self.prep(shared) or []
        await asyncio.gather(*(self._orch_async(shared, {**self.params, **bp}) for bp in batches))
        return await self.post(shared, batches, None)
