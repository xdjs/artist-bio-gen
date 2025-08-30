# Repository Guidelines

## Project Structure & Module Organization
- Root scripts: `run_artists.py` (CLI/main), `run_tests.py` (test runner).
- Tests: `tests/` directory with `test_*.py` files (CLI, parsing, logging, data checks).
- Assets: `example_artists.csv` sample input.
- Config: `.env.example` (template), `.env.local` (secrets, ignored by Git).
- Dependencies: `requirements.txt` (runtime + dev tools).

## Build, Test, and Development Commands
- Install: `pip install -r requirements.txt`
- Run locally: `python3 run_artists.py --input-file example_artists.csv --prompt-id <id>`
- All tests: `python3 run_tests.py`
- Single test file: `python3 run_tests.py test_run_artists.py`
- Format: `black .`
- Type check: `mypy run_artists.py`

## Coding Style & Naming Conventions
- Python 3.11+, 4‑space indentation, PEP 8.
- Use type hints and docstrings; prefer small, pure functions.
- Files and functions: `snake_case`; constants: `UPPER_SNAKE_CASE`.
- Keep CLI help exhaustive; update examples when flags change.
- Run `black` before pushing; keep imports ordered (black/PEP 8).

## Testing Guidelines
- Framework: `unittest` via `run_tests.py` (no network in tests).
- Naming: place tests in `tests/` as `test_*.py`; mirror feature names.
- Add tests for new flags/parsing, logging output, and error paths.
- Running examples:
  - `python3 run_tests.py test_input_parser.py`
  - `python3 run_tests.py test_logging_monitoring.py`
  - `python3 run_tests.py test_run_artists.py`

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).
- Scope small and focused; include why + what changed.
- PRs must include: description, linked issues, how to run (exact command), and sample stdout/`out.jsonl` snippet.
- Require green tests; run `black` and `mypy` locally.

## Security & Configuration Tips
- Never commit secrets. Use `.env.local` with `OPENAI_API_KEY` and optional `OPENAI_PROMPT_ID`.
- Share non‑secret defaults in `.env.example`.
- Prefer `--dry-run` when validating inputs or reproducing issues.

## Agent‑Specific Instructions
- Do not change CLI flags without updating README, tests, and help text.
- Keep networked calls behind feature flags; tests must pass offline.
- Preserve stdout formatting and JSONL schema when modifying output.
