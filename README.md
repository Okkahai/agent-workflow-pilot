# Agent workflow pilot

Python 3.12 package scaffold. No application behavior yet.

## Calculator

`agent_workflow_pilot.calculator` provides `add(a, b)`, `subtract(a, b)`,
`multiply(a, b)`, and `divide(a, b)`. Each accepts built-in integers and
finite floats and preserves Python's arithmetic result semantics. Booleans and
other nonnumeric values raise `TypeError`; NaN and infinite float operands raise
`ValueError`. Division by `0`, `0.0`, or `-0.0` raises `ZeroDivisionError`.

```python
from agent_workflow_pilot.calculator import add, divide

add(2, 3)  # 5
divide(5, 2)  # 2.5
```

Install dependencies and run the smoke test:

```sh
uv sync --locked
uv run --locked pytest
```

CI runs pytest for pushes to main and pull requests targeting main.

## Reusable engineering harness

Start with [the universal standard](docs/engineering-standard.md), [onboarding template](docs/templates/onboarding.md), and [executed evidence](docs/evidence.md). The policy CLI validates trusted evidence; it does not collect credentials or merge PRs.
[Project onboarding](docs/templates/onboarding.md) and [T3 controller runbook](docs/t3-runbook.md).
