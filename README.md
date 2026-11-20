# kitchen

A tiny, easy way to build AI agents.

## The idea

An agent is made of three simple parts:

- **Node** - one piece of work. It does one job, and only one.
- **Flow** - the order things happen in. It decides which piece of work
  runs next.
- **Shared storage** - one plain box (a dictionary) that every piece of
  work can read from and write to.

That's it. Nothing else to learn before you start building.

## How a piece of work runs

Every node does three things, in order:

1. **Look** - check the shared storage for whatever it needs.
2. **Do** - do its actual job (call an AI model, search the web, run a
   calculation, anything at all).
3. **Finish** - put its results into the shared storage, and say what
   should happen next.

That "what happens next" is just a word, like `"error"` or `"done"`. The
flow reads that word and sends the work to whichever node is wired up to
handle it. If nothing is wired up for that word, the flow stops.

## A simple example

```python
from kitchen import Node, Flow

class FetchData(Node):
    def post(self, shared, prep_res, exec_res):
        shared["data"] = [1, 2, 3]

class Process(Node):
    def post(self, shared, prep_res, exec_res):
        shared["total"] = sum(shared["data"])

class Report(Node):
    def post(self, shared, prep_res, exec_res):
        print("Total:", shared["total"])

fetch, process, report = FetchData(), Process(), Report()
fetch >> process >> report     # fetch, then process, then report

Flow(fetch).run({})
```

Running this prints `Total: 6`.

## Going back a step

A node can send the work back to an earlier one instead of forward:

```python
process - "error" >> fetch   # if processing returns "error", fetch again
```

This is also how an AI agent "thinks in a loop" - a node can send work
back to itself or to an earlier node, over and over, until it's ready to
move on.

## What's extra, in plain words

- **If a job fails, try again.** A node can be told to try a few times
  before giving up, with a short pause in between.
- **A backup plan.** If a job keeps failing, a node can have a fallback
  action instead of crashing.
- **Doing many things at once.** A node can be told to do its job for a
  whole list of items - one at a time, or all at the same time.
- **A safety stop.** You can set a limit on how many steps a flow is
  allowed to take, so a loop that never ends can't run forever.
- **Settings for a run.** You can hand small pieces of information (like a
  name or an ID) to every node in a flow, without putting them in the
  shared storage.

## Files in this folder

- `kitchen.py` - the framework itself.
- `example_kitchen.py` - the fetch/process/report example above, with a
  failure that sends the work back a step.
- `example_agent.py` - a small AI agent that decides whether to search for
  more information or give a final answer, in a loop.
- `example_async.py` - the same example, but doing several jobs at the
  same time instead of one after another.
- `test_kitchen.py` - checks that everything in `kitchen.py` actually works
  the way it's supposed to.

## Why build agents this way

Most of what goes wrong with AI agents comes from having too many moving
parts with no clear shape. Here, every piece of work is a node that does
one job, and the flow is the only thing deciding what happens next. When
something isn't working, you know exactly where to look.

## How to build with kitchen ?

### with Claude code :- 

Add the .agent to your claude Skills and just start prompting :- 

```
Claude cook with kitchen [your requirement]
```

plan the capabilities of your agent and the skills that you wish to see in your in agent
and prepare a clean design doc for before using "kitchen" to cook your agents..

### with Antigravity , Cursor and any others :- 

Just start prompting with the design doc being clear and ready 