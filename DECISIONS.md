# Architecture Decision Log

## ADR-001: Project tooling — uv, src-layout, strict mypy
- Context: Greenfield Python 3.12 project that must be reproducible locally and in CI, and readable by reviewers coming from typed languages.
- Options considered:
  - Dependency management: uv vs Poetry vs pip + requirements.txt.
  - Layout: src-layout vs flat layout.
  - Typing: mypy strict vs mypy default vs no type checking.
- Decision: uv with a committed `uv.lock` (CI runs `uv sync --locked`); src-layout (`src/triage`) built with `uv_build`; mypy `strict = true`, relaxed only per-module via overrides; ruff for both lint and format.
- Consequences / trade-offs:
  - uv is one fast tool for Python version, venv, deps and lock; it is younger than Poetry, but its lockfile and `pyproject.toml` are standard enough to migrate away from.
  - src-layout forces tests to import the installed package, catching packaging mistakes early, at the cost of an extra directory level.
  - Strict mypy adds friction with untyped libraries (LangGraph/LiteLLM may need overrides), but catches contract errors between graph nodes and tools before runtime.
