"""Already completed sibling must not run again after retries (#9484)."""
import asyncio
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import TimeoutPolicy


class State(TypedDict, total=False):
    x: int
    effects: Annotated[list[str], operator.add]


async def main():
    counts = {"ok": 0, "retry": 0}
    completed_event = asyncio.Event()

    async def completed(_state):
        counts["ok"] += 1
        completed_event.set()
        return {"effects": ["ok"]}

    async def fails_twice(_state):
        await completed_event.wait()
        await asyncio.sleep(0.05)
        counts["retry"] += 1
        if counts["retry"] <= 2:
            raise RuntimeError("synthetic failure")
        return {"effects": ["recovered"]}

    graph = StateGraph(State)
    graph.add_node("completed", completed, timeout=TimeoutPolicy(run_timeout=3600))
    graph.add_node("fails_twice", fails_twice)
    graph.add_edge(START, "completed")
    graph.add_edge(START, "fails_twice")
    graph.add_edge(["completed", "fails_twice"], END)
    app = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "9484-sibling-repeat"}}

    for n in range(3):
        try:
            result = await app.ainvoke({"x": 1} if n == 0 else None, config)
            assert n == 2, f"Unexpected success on attempt {n}"
        except RuntimeError as exc:
            assert n < 2 and str(exc) == "synthetic failure"

    assert counts == {"ok": 1, "retry": 3}, counts
    assert result["effects"].count("ok") == 1, result
    assert result["effects"].count("recovered") == 1, result
    print("SIBLING_REPLAY_PASS", counts)


if __name__ == "__main__":
    asyncio.run(main())
