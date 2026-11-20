"""
Async kitchen: several burners at once.

Cook is async and cooks every dish concurrently with asyncio.gather.
Chop and Serve stay plain sync nodes. AsyncFlow runs both kinds.
"""

import asyncio
import time

from kitchen import Node, AsyncNode, AsyncFlow


class Chop(Node):
    def post(self, shared, prep_res, exec_res):
        shared["board"] = [f"chopped {v}" for v in shared["pantry"]]


class Cook(AsyncNode):
    async def prep(self, shared):
        return shared["board"]

    async def exec(self, board):
        async def burner(item):  # stands in for an async LLM or API call
            await asyncio.sleep(1)
            return f"cooked {item}"

        return await asyncio.gather(*(burner(i) for i in board))

    async def post(self, shared, board, dishes):
        shared["pan"] = dishes


class Serve(Node):
    def post(self, shared, prep_res, exec_res):
        for dish in shared["pan"]:
            print("serve ->", dish)


chop, cook, serve = Chop(), Cook(), Serve()
chop >> cook >> serve

if __name__ == "__main__":
    shared = {"pantry": ["onion", "pepper", "carrot"]}
    t = time.perf_counter()
    asyncio.run(AsyncFlow(chop).run(shared))
    print(f"3 dishes in {time.perf_counter() - t:.1f}s (concurrent, not 3s)")
