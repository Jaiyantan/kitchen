"""The kitchen analogy, literally."""

from kitchen import Node, Flow


class Chop(Node):
    def prep(self, shared):
        return shared["pantry"]

    def exec(self, veggies):
        return [f"chopped {v}" for v in veggies]

    def post(self, shared, prep_res, chopped):
        shared["board"] = chopped
        print("chop  ->", chopped)


class Cook(Node):
    def prep(self, shared):
        shared["attempts"] = shared.get("attempts", 0) + 1
        return shared["board"], shared["attempts"]

    def exec(self, inputs):
        board, attempt = inputs
        burnt = attempt == 1  # first try burns, to show branching
        return board, burnt

    def post(self, shared, prep_res, exec_res):
        board, burnt = exec_res
        if burnt:
            print("cook  -> burnt, back to chopping")
            return "burnt"
        shared["pan"] = f"stir fry of {', '.join(board)}"
        print("cook  ->", shared["pan"])


class Serve(Node):
    def prep(self, shared):
        return shared["pan"]

    def post(self, shared, dish, exec_res):
        shared["plate"] = dish
        print("serve ->", dish)


chop, cook, serve = Chop(), Cook(), Serve()
chop >> cook >> serve
cook - "burnt" >> chop

if __name__ == "__main__":
    shared = {"pantry": ["onion", "pepper", "carrot"]}
    Flow(chop).run(shared)
    print("\nstorage:", shared)
