"""Distinct planned Send unit identities on resume (LangGraph #9484)."""
import asyncio
from collections import Counter
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, TimeoutPolicy

EXPECTED = {"A": "11", "B": "23", "C": "37"}


def merge_unique(left, right):
    result = dict(left)
    for key, value in right.items():
        if key in result:
            raise AssertionError(f"Duplicate completed unit {key}")
        result[key] = value
    return result


class ParentState(TypedDict, total=False):
    x: int
    total: str


class ChildState(TypedDict, total=False):
    x: int
    results: Annotated[dict[str, str], merge_unique]
    total: str


async def main():
    executed = []
    child = StateGraph(ChildState)
    child.add_node("prepare", lambda s: {"x": s["x"]})

    async def item(s):
        await asyncio.sleep(0.01)
        unit = s["unit"]
        executed.append(unit)
        return {"results": {unit: EXPECTED[unit]}}

    child.add_node("item", item)
    child.add_node(
        "join", lambda s: {"total": "|".join(s["results"][k] for k in ("A", "B", "C"))}
    )
    child.add_edge(START, "prepare")
    child.add_conditional_edges(
        "prepare", lambda s: [Send("item", {"unit": k}) for k in EXPECTED], ["item"]
    )
    child.add_edge("item", "join")
    child.add_edge("join", END)
    compiled_child = child.compile()
    compiled_child.step_timeout = 3600
    failures = [True]

    async def run_child(s):
        result = await compiled_child.ainvoke({"x": s["x"], "results": {}})
        return {"total": result.get("total", "<incomplete>")}

    async def flaky(_s):
        if failures and failures.pop():
            raise RuntimeError("service unavailable")
        return {}

    parent = StateGraph(ParentState)
    parent.add_node("run_child", run_child, timeout=TimeoutPolicy(run_timeout=3600))
    parent.add_node("flaky", flaky)
    parent.add_edge(START, "run_child")
    parent.add_edge(START, "flaky")
    parent.add_edge(["run_child", "flaky"], END)
    app = parent.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "9484-distinct"}}
    try:
        await app.ainvoke({"x": 7}, config)
    except RuntimeError as exc:
        assert str(exc) == "service unavailable"
    else:
        raise AssertionError("First run should fail")
    result = await app.ainvoke(None, config)
    counts = Counter(executed)
    assert counts == Counter(EXPECTED.keys()), counts
    assert result["total"] == "11|23|37", result
    print("DISTINCT_UNITS_PASS", dict(counts), result["total"])


if __name__ == "__main__":
    asyncio.run(main())
