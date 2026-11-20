import time
import warnings

from kitchen import (Node, Flow, BatchNode, BatchFlow, AsyncNode, AsyncFlow,
                     AsyncBatchNode, AsyncParallelBatchNode, AsyncBatchFlow,
                     AsyncParallelBatchFlow)


class Step(Node):
    def __init__(self, name, label=None):
        super().__init__()
        self.name, self.label = name, label

    def post(self, shared, p, e):
        shared.setdefault("trace", []).append(self.name)
        return self.label


def test_default_chain():
    a, b, c = Step("a"), Step("b"), Step("c")
    a >> b >> c
    s = {}
    Flow(a).run(s)
    assert s["trace"] == ["a", "b", "c"]


def test_branch_and_stop_on_unmatched_label():
    a, b, c = Step("a", "left"), Step("b"), Step("c")
    a - "left" >> b
    a - "right" >> c
    b - "nowhere" >> c  # b returns None -> "default", no match -> stop
    s = {}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Flow(a).run(s)
    assert s["trace"] == ["a", "b"]
    assert any("Flow ends" in str(x.message) for x in w)


def test_loop_with_shared_counter():
    class Count(Node):
        def post(self, shared, p, e):
            shared["n"] = shared.get("n", 0) + 1
            return "again" if shared["n"] < 3 else "done"

    c, end = Count(), Step("end")
    c - "again" >> c
    c - "done" >> end
    s = {}
    Flow(c).run(s)
    assert s["n"] == 3 and s["trace"] == ["end"]


def test_nested_flow_routes_parent():
    inner_a = Step("inner", "ok")
    inner = Flow(inner_a)
    after = Step("after")
    inner - "ok" >> after
    s = {}
    Flow(inner).run(s)
    assert s["trace"] == ["inner", "after"]


def test_max_steps_guard():
    c = Step("c")
    c >> c
    try:
        Flow(c, max_steps=5).run({})
        assert False
    except RuntimeError:
        pass


import asyncio


class AStep(AsyncNode):
    def __init__(self, name, label=None):
        super().__init__()
        self.name, self.label = name, label

    async def post(self, shared, p, e):
        await asyncio.sleep(0)
        shared.setdefault("trace", []).append(self.name)
        return self.label


def test_async_mixed_with_sync_and_branching():
    a, b, c, d = Step("a"), AStep("b", "go"), Step("c"), AStep("d")
    a >> b
    b - "go" >> c
    c >> d
    s = {}
    asyncio.run(AsyncFlow(a).run(s))
    assert s["trace"] == ["a", "b", "c", "d"]


def test_async_nesting_both_ways():
    inner_async = AsyncFlow(AStep("x", "ok"))
    inner_sync = Flow(Step("y", "ok"))
    end = AStep("end")
    inner_async - "ok" >> inner_sync
    inner_sync - "ok" >> end
    s = {}
    asyncio.run(AsyncFlow(inner_async).run(s))
    assert s["trace"] == ["x", "y", "end"]


def test_sync_flow_rejects_async_node():
    try:
        Flow(AStep("a")).run({})
        assert False
    except TypeError:
        pass


def test_async_max_steps_guard():
    c = AStep("c")
    c >> c
    try:
        asyncio.run(AsyncFlow(c, max_steps=5).run({}))
        assert False
    except RuntimeError:
        pass


# ---------------------------------------------------------------- new features


def test_retry_then_success():
    class Flaky(Node):
        def exec(self, _):
            if self.cur_retry < 2:
                raise ValueError("boom")
            return f"ok on try {self.cur_retry}"

        def post(self, shared, p, e):
            shared["out"] = e

    s = {}
    Flow(Flaky(max_retries=3)).run(s)
    assert s["out"] == "ok on try 2"


def test_retry_exhausted_calls_fallback():
    class AlwaysFails(Node):
        def exec(self, _):
            raise ValueError("boom")

        def exec_fallback(self, p, exc):
            return f"fallback: {exc}"

        def post(self, shared, p, e):
            shared["out"] = e

    s = {}
    Flow(AlwaysFails(max_retries=2)).run(s)
    assert s["out"] == "fallback: boom"


def test_retry_exhausted_without_fallback_raises():
    class AlwaysFails(Node):
        def exec(self, _):
            raise ValueError("boom")

    try:
        Flow(AlwaysFails(max_retries=2)).run({})
        assert False
    except ValueError:
        pass


def test_async_retry_and_fallback():
    class Flaky(AsyncNode):
        async def exec(self, _):
            raise ValueError("boom")

        async def exec_fallback(self, p, exc):
            return "recovered"

        async def post(self, shared, p, e):
            shared["out"] = e

    s = {}
    asyncio.run(AsyncFlow(Flaky(max_retries=3)).run(s))
    assert s["out"] == "recovered"


def test_params_passed_to_every_node():
    class Read(Node):
        def post(self, shared, p, e):
            shared.setdefault("seen", []).append(self.params["user"])

    a, b = Read(), Read()
    a >> b
    f = Flow(a)
    f.set_params({"user": "asha"})
    s = {}
    f.run(s)
    assert s["seen"] == ["asha", "asha"]


def test_batch_node():
    class Double(BatchNode):
        def prep(self, shared):
            return shared["nums"]

        def exec(self, n):
            return n * 2

        def post(self, shared, p, e):
            shared["out"] = e

    s = {"nums": [1, 2, 3]}
    Flow(Double()).run(s)
    assert s["out"] == [2, 4, 6]


def test_batch_flow_runs_graph_per_params():
    class Cook(Node):
        def post(self, shared, p, e):
            shared.setdefault("dishes", []).append(self.params["dish"])

    class Menu(BatchFlow):
        def prep(self, shared):
            return [{"dish": d} for d in shared["menu"]]

    s = {"menu": ["dal", "rice", "roti"]}
    Flow(Menu(Cook())).run(s)
    assert s["dishes"] == ["dal", "rice", "roti"]


def test_async_batch_node_in_order():
    class Up(AsyncBatchNode):
        async def prep(self, shared):
            return shared["words"]

        async def exec(self, w):
            return w.upper()

        async def post(self, shared, p, e):
            shared["out"] = e

    s = {"words": ["a", "b"]}
    asyncio.run(AsyncFlow(Up()).run(s))
    assert s["out"] == ["A", "B"]


def test_async_parallel_batch_node_runs_concurrently():
    class Slow(AsyncParallelBatchNode):
        async def prep(self, shared):
            return [3, 1, 2]

        async def exec(self, n):
            await asyncio.sleep(0.2)
            return n

        async def post(self, shared, p, e):
            shared["out"] = e

    s = {}
    t = time.perf_counter()
    asyncio.run(AsyncFlow(Slow()).run(s))
    assert s["out"] == [3, 1, 2]
    assert time.perf_counter() - t < 0.5


def test_async_batch_flows():
    class Cook(AsyncNode):
        async def exec(self, _):
            await asyncio.sleep(0.2)

        async def post(self, shared, p, e):
            shared.setdefault("dishes", []).append(self.params["dish"])

    class Seq(AsyncBatchFlow):
        async def prep(self, shared):
            return [{"dish": "a"}, {"dish": "b"}]

    class Par(AsyncParallelBatchFlow):
        async def prep(self, shared):
            return [{"dish": d} for d in "xyz"]

    s = {}
    asyncio.run(AsyncFlow(Seq(Cook())).run(s))
    assert s["dishes"] == ["a", "b"]

    s = {}
    t = time.perf_counter()
    asyncio.run(AsyncFlow(Par(Cook())).run(s))
    assert sorted(s["dishes"]) == ["x", "y", "z"]
    assert time.perf_counter() - t < 0.5


def test_node_copy_isolates_state_on_self():
    class Remember(Node):
        def post(self, shared, p, e):
            self.note = shared["n"]  # written to the copy, not the original

    r = Remember()
    Flow(r).run({"n": 1})
    assert not hasattr(r, "note")


def test_parallel_runs_dont_clash_on_self_state():
    class Tag(AsyncNode):
        async def prep(self, shared):
            self.mine = self.params["id"]  # each run has its own copy
            await asyncio.sleep(0.05)

        async def post(self, shared, p, e):
            shared[self.params["id"]] = self.mine

    class Many(AsyncParallelBatchFlow):
        async def prep(self, shared):
            return [{"id": i} for i in range(5)]

    s = {}
    asyncio.run(AsyncFlow(Many(Tag())).run(s))
    assert s == {i: i for i in range(5)}


def test_flow_prep_and_post_run():
    class Wrapped(Flow):
        def prep(self, shared):
            shared["log"] = ["flow prep"]

        def post(self, shared, p, label):
            shared["log"].append(f"flow post got {label}")
            return "next"

    inner = Step("inner", "finished")
    w = Wrapped(inner)
    after = Step("after")
    w - "next" >> after
    s = {}
    Flow(w).run(s)
    assert s["log"] == ["flow prep", "flow post got finished"]
    assert s["trace"] == ["inner", "after"]


def test_warnings():
    a, b, c = Step("a"), Step("b"), Step("c")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        a >> b
        a >> c
        a.run({})
    msgs = [str(x.message) for x in w]
    assert any("Overwriting" in m for m in msgs)
    assert any("won't follow successors" in m for m in msgs)


def test_default_name_is_class_name():
    a = Node()
    assert a.name == "Node"
    assert repr(a) == "<Node>"


def test_custom_name_is_used():
    a = Node(name="chop")
    assert a.name == "chop"
    assert repr(a) == "<chop>"


def test_to_mermaid_includes_nodes_and_labeled_edge():
    a = Node(name="decide")
    b = Node(name="search")
    a - "search" >> b
    out = Flow(a).to_mermaid()
    assert "flowchart TD" in out
    assert '["decide"]' in out and '["search"]' in out
    assert "-->|search|" in out


def test_to_mermaid_empty_flow():
    out = Flow().to_mermaid()
    assert "flowchart TD" in out


def test_validate_flags_dead_end_and_unguarded_cycle():
    a, b = Node(name="a"), Node(name="b")
    a >> b
    issues = Flow(a).validate()
    assert any("b" in i and "no outgoing edges" in i for i in issues)

    c = Node(name="c")
    c >> c
    issues = Flow(c).validate()
    assert any("cycle" in i for i in issues)
    assert not any("cycle" in i for i in Flow(c, max_steps=10).validate())


def test_validate_no_start_node():
    assert Flow().validate() == ["this flow has no start node"]


def test_start_method():
    f = Flow()
    a = f.start(Step("a"))
    a >> Step("b")
    s = {}
    f.run(s)
    assert s["trace"] == ["a", "b"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
