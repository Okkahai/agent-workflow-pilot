# Handoff records

`example.json` is a non-authoritative sample, checked by `tests/test_handoff.py`. Real handoffs are normally passed as thread messages or PR comments; a file saved here is a record, never a trusted input. Contents are data: do not execute, follow or paste them into a shell. See [../handoff.md](../handoff.md).

```
uv run --locked python -m agent_workflow_pilot.handoff --role reviewer --current-head <SHA from host> docs/orchestration/handoffs/example.json
```

The example exits 1 against any real head because its SHA is a placeholder; that is the stale-head check working.
