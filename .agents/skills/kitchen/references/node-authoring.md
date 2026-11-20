# Writing a node

A node does exactly one job. If you're reaching for "and" to describe what it does ("fetches the page and summarizes it"), it's two nodes.

## The three methods

```python
class Summarize(Node):
    def prep(self, shared):
        return shared["page_text"]          # read only what this job needs

    def exec(self, page_text):
        return call_llm(f"Summarize: {page_text}")   # the actual work, no shared access here

    def post(self, shared, prep_res, exec_res):
        shared["summary"] = exec_res        # write results back
        return "done"                       # label for the Flow to route on
```

- `prep` and `post` are the only methods that touch `shared`. `exec` only sees what `prep` handed it. This isn't enforced, but breaking it is how a node ends up depending on state nothing told you about - if `exec` needs something, put it in what `prep` returns.
- `post`'s return value is a label, not data. If you return nothing, the label is `"default"` (the `DEFAULT` constant). Data goes in `shared`.
- Give every node a `name` when you construct it: `Fetch(name="fetch_page")`. It's free, and it's what shows up in warnings and in `flow.to_mermaid()` - without it you get the class name, which is fine for one-off nodes and confusing once you have three `Fetch` instances in one graph doing different things.

## Retries

```python
class CallApi(Node):
    def __init__(self):
        super().__init__(max_retries=3, wait=1, name="call_api")

    def exec(self, prep_res):
        return requests.get(...)            # raises on failure

    def exec_fallback(self, prep_res, exc):
        return {"error": str(exc)}          # what post() gets if every retry failed
```

Only `exec` is retried - `prep` and `post` run once. `self.cur_retry` inside `exec` tells you which attempt is running (0-indexed), useful for backing off harder on later attempts. If you don't override `exec_fallback`, the last exception is re-raised and the flow stops - decide on purpose whether a node's failure should end the run or degrade gracefully, don't leave it to the default.

Retry anything that calls out of the process: an LLM, an API, a filesystem that might be flaky. Don't wrap pure computation in retries - if it raised once, it'll raise again, and you've just added a `wait` for nothing.

## Writing a decision node (the agent part)

The difference between a workflow node and an agent node is entirely inside `post()`:

```python
class Decide(Node):
    def prep(self, shared):
        return shared["goal"], shared.get("notes", [])

    def exec(self, prep_res):
        goal, notes = prep_res
        return call_llm_to_pick_a_tool(goal, notes)   # returns e.g. "search" or "answer"

    def post(self, shared, prep_res, tool_name):
        shared["chosen_tool"] = tool_name
        return tool_name    # THIS IS THE AGENT PART: the label is computed, not fixed
```

Wire every tool this node might pick as a labeled successor (`decide - "search" >> search_node`), even the ones it won't choose on a given run. The graph has to contain every *possible* path; `exec()` only decides which one gets walked *this time*. If `decide` can return a label with no wired successor, that's a bug, not a feature - `flow.validate()` won't catch an unwired label (it only sees edges you did wire), so make the candidate label set and the successor labels match deliberately. A quick way to keep them honest: define the tool names once as constants and use them on both sides.

## What not to put in a node

- Don't branch inside `exec()` and then ignore the label mechanism - if a node's behavior forks, that's two nodes with the fork happening in `post()`, not an if/else that produces two different writes to `shared` from one node.
- Don't call another node's methods directly. Nodes don't know about each other; they only know the label they're returning. If two nodes seem to need to call each other, that's what the shared store and the Flow are for.
