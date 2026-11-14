# LangGraph issue #9484 — candidate fix for review

Issue: https://github.com/langchain-ai/langgraph/issues/9484

## Reference

- Upstream base commit: `08a2016953789a4f579b4d36bd1967941ec62012`
- Candidate branch: `fix-9484-candidate` in this public fork
- Python used for the focused check: 3.12.16 on a Linux GitHub runner
- Installed source identified itself as LangGraph 1.2.22
- Original issue reproducer SHA-256: `82abc9c745a20247d2063c7813e974e64b028ae556cf18a184b59bcd3e719576`

## Reproduce from this branch

Use a fresh environment with Python 3.12:

```bash
git clone https://github.com/lucafranco1994pot-cloud/langgraph.git
cd langgraph
git checkout fix-9484-candidate
python -m pip install -e ./libs/langgraph

python issue-9484-review/test_distinct_units.py
python issue-9484-review/test_sibling_replay.py
```

Expected output lines:

```text
DISTINCT_UNITS_PASS {'A': 1, 'B': 1, 'C': 1} 11|23|37
SIBLING_REPLAY_PASS {'ok': 1, 'retry': 3}
```

The source file `libs/langgraph/langgraph/pregel/_loop.py` already contains the candidate modification on this branch. Do **not** apply the patch again. To review the source change against the frozen upstream commit:

```bash
git diff 08a2016953789a4f579b4d36bd1967941ec62012..HEAD -- libs/langgraph/langgraph/pregel/_loop.py
```

For the original reproduction, use the Python code provided in the public issue. On the unchanged upstream commit with both timeouts configured, the child graph returns an incomplete result after resume. Disabling either timeout makes the original scenario return `7+7+7`. The candidate change made the original scenario and both controls return `7+7+7` in focused testing.

## Intended change

In `PregelLoop._reapply_writes_to_succeeded_nodes`, skip restoring partial output writes for tasks whose checkpointed status has an error. This prevents such writes being mistaken for successful task completion in the tested resume scenario.

## Scope and limitations

- The two tests exercise in-process error recovery using `InMemorySaver`, not a new process or persistent checkpoint backend.
- The distinct-units test checks three planned logical tasks separately, including their execution counts and outputs. It does not establish a general exactly-once execution guarantee.
- The sibling test observes a completed sibling once while a different sibling fails twice and then recovers.
- No external provider side effects, full upstream test-suite run, or independent regression test against this candidate are claimed.
- Dependencies are installed from the fixed source commit but are not fully locked in this standalone reproduction.

Thanks to everyone investigating the issue, including @sakshiagra1903 for preparing an independent regression test. Further counterexamples are welcome.
