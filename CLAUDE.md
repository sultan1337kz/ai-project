# CLAUDE.md — Security Findings Triage Agent

## Who I am and why this project exists
- I'm a senior Java backend developer (~12 years, banking/fintech: Spring Boot, Apache Camel, integrations).
- I'm learning Python and building AI agents. This project is (1) my learning vehicle and (2) a portfolio piece for "AI Agent Engineer" roles.
- Interviewers will ask me *why* every design decision was made. I must understand and be able to defend all code in this repo. Optimize for my understanding, not just for working code.

## What we are building
An agent that triages security findings from scanner reports (ZAP, nuclei, Semgrep) produced against my **local** OWASP Juice Shop lab:
ingest → normalize → dedupe → classify (severity, false positive?) → enrich (CWE/CVE, source code context) → recommend fix → **human approval** → create GitHub issue.

## Stack
- Python 3.12, `uv` for dependencies, `ruff` + `mypy` (strict-ish), `pytest`
- LangGraph (state graph, Postgres checkpointer, interrupts for human-in-the-loop)
- MCP servers via the official MCP Python SDK (FastMCP)
- LiteLLM as the LLM gateway (model tiering, budgets, fallbacks); AWS Bedrock as provider (Anthropic API allowed for local dev)
- Postgres (checkpoints + memory), Langfuse / OpenTelemetry for tracing
- Docker Compose for local env, GitHub Actions for CI, AWS for deployment (later)

## Repository layout
```
lab/                  # docker-compose for Juice Shop + scripts to run scanners manually
reports/              # raw scanner reports (inputs), committed samples only
src/triage/
  models.py           # normalized Finding schema (pydantic)
  parsers/            # zap.py, nuclei.py, semgrep.py -> Finding
  mcp_servers/
    findings/         # read-only: list_findings, get_finding
    reference/        # read-only: CWE/NVD lookup, search Juice Shop source
    tracker/          # WRITE: create_issue (idempotent, approval-gated)
  agent/              # LangGraph graph, nodes, state, prompts
  memory/             # per-engagement store (FP decisions, history)
  gateway/            # LiteLLM config
evals/                # golden dataset, eval runners, metrics
tests/                # unit + integration + failure-injection tests
docs/learning/        # learning notes per module (Russian)
DECISIONS.md          # architecture decision log
README.md             # portfolio-facing overview (English)
```

## Hard safety rules (never break these)
- The agent NEVER runs scanners or any offensive tooling. I run scanners manually, only against my local lab (localhost). The agent only reads reports.
- Any action with side effects (creating issues, writing to external systems) must go through an explicit human approval step in the graph.
- Write-tools must be idempotent (idempotency key derived from finding fingerprint + engagement id).
- Memory and data are isolated per engagement. No cross-engagement reads.
- No secrets in code or commits. Use `.env` (gitignored) locally and AWS Secrets Manager in the cloud. Provide `.env.example`.

## How to work with me
1. **Plan first.** Before writing code for a new module, give me a short plan: components, key decisions, 1–2 alternatives you rejected and why. Wait for my OK.
2. **Small steps.** One module or one meaningful change per step. After each step: run `ruff`, `mypy`, `pytest`, and summarize what changed.
3. **Don't over-engineer.** No abstractions, layers or dependencies I didn't ask for. If you think something is needed, propose it, don't add it.
4. **Ask when unsure** about a design decision instead of guessing.
5. **Make failures visible.** No silent `except: pass`. Errors are logged with context and either handled explicitly or re-raised.

## Code comments
- Comment the **why**, not the what. Explain non-obvious decisions, edge cases, failure modes.
- When a Python or agent concept differs from Java, a short Java analogy is welcome, e.g. `# like @Transactional, but ...` or `# pydantic model ≈ Java record + Bean Validation`.
- Keep comments production-quality: this repo will be reviewed by hiring managers. No tutorial-style essays in code — those go to `docs/learning/`.
- Code, comments, README, DECISIONS.md — in **English**.

## Learning notes (docs/learning/)
After finishing each module, create or update `docs/learning/<NN>-<module>.md` **in Russian** with:
1. **Что делает модуль** и как он вписывается в систему (1 абзац + место в пайплайне)
2. **Ключевые концепции** простым языком (например: tool use loop, MCP, чекпоинты LangGraph, идемпотентность, evals). Где уместно — сравнение с Java/Spring.
3. **Python-особенности**, которые встретились в этом модуле (async, type hints, pydantic, context managers и т.п.)
4. **Альтернативы**: что ещё можно было сделать и почему выбрано это
5. **Что может сломаться** и как это проявится (симптомы в логах/трейсах)
6. **Вопросы для самопроверки**: 3–5 вопросов в стиле технического интервью (без ответов)
7. **Упражнение**: одно небольшое изменение, которое я должен сделать сам руками

## Decision log (DECISIONS.md)
For every architectural decision, append an entry:
```
## ADR-NNN: <title>
- Context:
- Options considered:
- Decision:
- Consequences / trade-offs:
```

## Testing expectations
- Unit tests for parsers and pure logic.
- Integration tests for MCP servers and graph nodes (mock the LLM where behavior is deterministic).
- Failure-injection tests: tool timeout, malformed report, process crash mid-run (resume from checkpoint), duplicate approval / repeated create_issue.
- Evals (separate from tests): golden dataset of labeled findings, measure classification accuracy and FP detection; later gated in CI.

## Commands
- Install: `uv sync`
- Lint/types: `uv run ruff check . && uv run mypy src`
- Tests: `uv run pytest`
- Lab up: `docker compose -f lab/docker-compose.yml up -d`
