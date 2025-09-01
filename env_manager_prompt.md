# Implement a central Environment manager for **artist-bio-gen**

## Goal
Create a single class that **loads, validates, and serves** all configuration values (env vars) for the app. It must support:
1) `.env.local` file (optional; via `python-dotenv` if present)  
2) OS environment variables (`os.environ`)  
3) **CLI overrides** (always win)

All code should access config **only** through this class.

## Files & wiring
- New file: `artist_bio_gen/config/env.py`
- Light refactors:
  - `artist_bio_gen/cli/main.py` → apply CLI overrides via the Env manager
  - `artist_bio_gen/database/config.py`, `artist_bio_gen/api/client.py`, etc. → replace `os.getenv(...)` with `Env.current().XYZ`
- Keep optional `python-dotenv` behavior (no hard dep).

## Variables (from .env.example)
- `OPENAI_API_KEY` (required)
- `OPENAI_PROMPT_ID` (optional)
- `DATABASE_URL` (required; Postgres URL)
- `OPENAI_ORG_ID` (optional)

## Class design
Implement `Env` as a **frozen dataclass** with typed fields, plus a process-wide **singleton** accessor:

```python
# artist_bio_gen/config/env.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Mapping

@dataclass(frozen=True)
class Env:
    OPENAI_API_KEY: str
    DATABASE_URL: str
    OPENAI_PROMPT_ID: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None

    # ---- lifecycle ----
    @staticmethod
    def load(cli_overrides: Mapping[str, str] | None = None) -> "Env":
        """
        Load in this precedence:
        1) defaults (None)
        2) .env.local (if python-dotenv is installed and file exists)
        3) os.environ
        4) cli_overrides (highest)
        Validate required fields; return an Env instance.
        """

    @staticmethod
    def current() -> "Env":
        """
        Return the globally-initialized Env. Raises if not yet initialized.
        """

    # ---- helpers ----
    def to_dict(self) -> dict: ...
```

### Loading precedence & behavior
- **Step 1: defaults** — start with `None` for all.
- **Step 2: .env.local** — attempt `from dotenv import load_dotenv`; if import fails, skip silently. If present, call `load_dotenv(".env.local", override=False)`.
- **Step 3: OS env** — read with `os.getenv`.
- **Step 4: CLI overrides** — dict of key→value, applied last.
- **Validation** — if `OPENAI_API_KEY` or `DATABASE_URL` is missing/empty → print a concise error to stderr and exit with non-zero (or raise a custom `ConfigError` caught in the CLI entrypoint). Trim whitespace.
- **Freezing** — the dataclass is frozen; values are immutable after init.
- **Singleton** — store the created instance in a private module-level `_ENV`. `Env.load()` sets it, `Env.current()` returns it.

### CLI integration
In `artist_bio_gen/cli/main.py`:
- After parsing args, build a dict of overrides with **only** keys that were provided on the CLI (e.g., `--db-url`, `--openai-api-key`, `--openai-prompt-id`, `--openai-org-id`).
- Map CLI names → env keys:
  - `--db-url` → `DATABASE_URL`
  - `--openai-api-key` → `OPENAI_API_KEY`
  - `--openai-prompt-id` → `OPENAI_PROMPT_ID`
  - `--openai-org-id` → `OPENAI_ORG_ID`
- Call `Env.load(cli_overrides)` **once at startup**.

### Usage examples (replace old getenvs)
- In `api/client.py`:
  ```python
  from artist_bio_gen.config.env import Env
  def make_openai_client():
      env = Env.current()
      # use env.OPENAI_API_KEY, env.OPENAI_ORG_ID
  ```
- In `database/config.py`:
  ```python
  env = Env.current()
  dsn = env.DATABASE_URL
  ```

### Optional niceties
- Add `@classmethod def from_mapping(cls, m: Mapping[str,str])` for testing.
- Add `.mask()` method for safe logging (e.g., mask API key).
- Accept `DATABASE_URL` variants (e.g., trim quotes).

### Logging & errors
- On load failure (missing required vars), emit messages like:
  - `ERROR: OPENAI_API_KEY is required but was not provided (env/CLI).`
  - `ERROR: DATABASE_URL is required but was not provided (env/CLI).`
- Exit code `2` for config errors.
- On success, optionally log a debug line summarizing which source set each var (default/env/cli)—but **never** print secret values; only the presence.

### Tests (add under `tests/`)
- `test_env_load_order.py`:
  - When both env and CLI provide a var, CLI wins.
  - When `.env.local` is present but `python-dotenv` missing, loading proceeds without error.
  - Missing required vars → raises `ConfigError`.
  - Optional vars omitted → instance has `None`.

### Migration checklist
- Replace `apply_environment_defaults()` with `Env.load(...)` at process start.
- Replace all `os.getenv("X")` with `Env.current().X`.
- Update docs: explain precedence (CLI > env > .env.local).

### Deliverables
1) `artist_bio_gen/config/env.py` implementing the class, loader, singleton.  
2) Refactors to use `Env.current()` in API and DB modules.  
3) Minimal tests for load precedence and validation.  
4) README snippet documenting the precedence and how to override via CLI.

### Style
- Python 3.11+, type hints, small functions, clear docstrings.
- No hard dependency on `python-dotenv` (optional import).
- Keep surface area small: `Env.load`, `Env.current`, `to_dict`.

---

If helpful, also add a small **bootstrap** at `artist_bio_gen/main.py` that calls `Env.load(...)` immediately after parsing args, before any network or DB work.
