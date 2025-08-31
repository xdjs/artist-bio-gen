# Repository Guidelines

## Project Structure & Module Organization
- **Package**: `artist_bio_gen/` - Modular Python package with separated concerns
- **Entry points**: `run_artists.py` (backward compatibility wrapper), `python -m artist_bio_gen.main`
- **Test runner**: `run_tests.py` - Comprehensive test suite
- **Tests**: `tests/` directory organized by module (`tests/core/`, `tests/api/`, etc.)
- **Assets**: `examples/example_artists.csv` sample input
- **Config**: `.env.example` (template), `.env.local` (secrets, ignored by Git)
- **Dependencies**: `requirements.txt` (runtime + dev tools)

### Package Modules
- `api/` - OpenAI API client and operations
- `database/` - PostgreSQL connection and operations
- `core/` - Business logic (parsing, processing, output)
- `cli/` - Command-line interface and argument parsing
- `utils/` - Shared utilities (logging, validation, helpers)
- `models/` - Data models and type definitions

## Build, Test, and Development Commands
- Install: `pip install -r requirements.txt`
- Run locally: `python3 run_artists.py --input-file examples/example_artists.csv --prompt-id <id>`
- Run as package: `python3 -m artist_bio_gen.main --input-file examples/example_artists.csv --prompt-id <id>`
- All tests: `python3 run_tests.py` (104 tests, 100% success rate)
- Format: `black artist_bio_gen/ tests/`
- Type check: `mypy artist_bio_gen/`

## Coding Style & Naming Conventions
- Python 3.11+, 4‑space indentation, PEP 8.
- Use type hints and docstrings; prefer small, pure functions.
- Files and functions: `snake_case`; constants: `UPPER_SNAKE_CASE`.
- Keep CLI help exhaustive; update examples when flags change.
- Run `black` before pushing; keep imports ordered (black/PEP 8).

## Testing Guidelines
- Framework: `unittest` via `run_tests.py` (no network in tests)
- Organization: tests in `tests/` organized by module (`tests/core/`, `tests/api/`, `tests/database/`, etc.)
- Naming: `test_*.py` files; mirror module and feature names
- Coverage: 104 tests with 100% success rate across all modules
- Add tests for new functionality, error paths, and module interfaces
- Test isolation: each module tested independently with proper imports

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
