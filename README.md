# Agent workflow pilot

Python 3.12 package scaffold. No application behavior yet.

Install dependencies and run the smoke test:

```sh
uv sync --locked
uv run --locked pytest
```

CI runs pytest for pushes to main and pull requests targeting main.
