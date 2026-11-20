"""
A real agent loop: decide -> (search -> decide)* -> answer.

`call_llm` is a stub so this runs offline. Swap in any provider, e.g.:

    from anthropic import Anthropic
    client = Anthropic()
    def call_llm(prompt):
        r = client.messages.create(model="claude-sonnet-5-5", max_tokens=1024,
                                   messages=[{"role": "user", "content": prompt}])
        return r.content[0].text
"""

from kitchen import Node, Flow


def call_llm(prompt):
    # Fake model: search once, then answer.
    if "NOTES: (none)" in prompt:
        return "ACTION: search\nQUERY: capital of France"
    return "ACTION: answer\nANSWER: Paris"


def web_search(query):
    return f"[result for '{query}'] Paris is the capital of France."


class Decide(Node):
    def prep(self, shared):
        notes = "\n".join(shared["notes"]) or "(none)"
        return f"QUESTION: {shared['question']}\nNOTES: {notes}\nReply with ACTION: search|answer"

    def exec(self, prompt):
        lines = dict(l.split(": ", 1) for l in call_llm(prompt).splitlines())
        return lines

    def post(self, shared, prompt, reply):
        if reply["ACTION"] == "search":
            shared["query"] = reply["QUERY"]
        else:
            shared["answer"] = reply["ANSWER"]
        return reply["ACTION"]  # the label the Flow routes on


class Search(Node):
    def prep(self, shared):
        return shared["query"]

    def exec(self, query):
        return web_search(query)

    def post(self, shared, query, result):
        shared["notes"].append(result)
        return "decide"


class Answer(Node):
    def post(self, shared, prep_res, exec_res):
        print("Answer:", shared["answer"])


decide, search, answer = Decide(), Search(), Answer()
decide - "search" >> search
decide - "answer" >> answer
search - "decide" >> decide

agent = Flow(decide, max_steps=20)

if __name__ == "__main__":
    shared = {"question": "What is the capital of France?", "notes": []}
    agent.run(shared)
    print("notes:", shared["notes"])
