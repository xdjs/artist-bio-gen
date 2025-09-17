# Review: Rate Limit Analysis & Implementation Plan

## Summary
- Strong, pragmatic plan that prioritizes reliability and aligns with project goals. A few SDK/HTTP details, testability constraints, and concurrency/pause mechanics need adjustment to fit our codebase and offline test suite.

## What’s Strong
- **Clear priorities**: Header parsing → backoff → pause/resume → concurrency.
- **Error‑aware backoff**: Separate strategies per error type with jitter.
- **Config surface**: CLI + env toggles planned with sensible defaults.
- **Testing/documentation**: Dedicated unit/integration tests and docs updates.

## Corrections & Gaps
- **Header access via SDK**: `client.responses.create()` does not expose HTTP headers. Use `client.responses.with_raw_response.create(...)` (or equivalent) to access `response.headers`. Adjust integration points accordingly.
- **Retry‑After handling**: Capture `Retry-After` from exception/HTTP response for 429/503. The SDK exceptions (e.g., `RateLimitError`) may carry response objects; fall back to default delays if absent.
- **Header formats/robust parsing**: `x-ratelimit-reset-*` values can be numeric seconds or duration-like strings (e.g., `20ms`). Implement tolerant parsing with units, guard division by zero, and handle missing/None gracefully.
- **Token tracking source**: Rate limit token usage often comes from response body `usage.total_tokens`, not headers. Incorporate body usage when available; don’t rely solely on header token fields.
- **Error taxonomy**: Map SDK exceptions and error codes precisely:
  - 429 rate limiting vs billing/“insufficient_quota” need different delays.
  - 5xx transient server errors use shorter backoff.
  - Use HTTP status + error code (when present) rather than string matching.
- **Pause/resume timing**: Prefer computed resume time from headers (`Retry-After`, `reset_requests/tokens`) over a fixed 24h pause. Fall back to conservative defaults when unknown.
- **Pause mechanics**: Avoid sleeping worker threads. Gate new task submission with a `threading.Event` or scheduler loop; let in‑flight tasks finish, then pause scheduling.
- **Concurrency scaling risk**: Adaptive concurrency adds complexity and can introduce flakiness. Ship behind a feature flag and default it off; consider deferring until the core is stable.
- **Thread safety & persistence**: Protect `QuotaMonitor` state with a `Lock`. If persisting state, use atomic writes (temp file + rename) and make disk persistence optional/disabled in tests.
- **Defaults & compatibility**: Keep monitoring enabled but conservative by default, and ensure behavior remains correct when headers are missing (no crashes, reasonable logging).
- **Logging volume**: Rate‑limit logs can spam under load. Add rate‑limited logging (e.g., every N requests or threshold crossings) and structured JSON to fit existing logging utils.
- **Test placement**: Follow our structure: `tests/api/test_quota_headers.py`, `tests/api/test_enhanced_backoff.py`, `tests/models/test_quota_models.py`, `tests/core/test_pause_resume.py`. Keep all tests offline with mocked SDK responses.
- **Streaming responses**: If we stream completions, headers are only available at the start, and usage stats arrive at the end. Ensure both code paths are covered (non‑streaming vs streaming), and tests simulate both.
- **Throughput assumptions**: The “~0.75 items/sec per worker” constant is optimistic for long prompts/latency variance. Make it configurable and validate against observed metrics.
- **Quota heuristic**: An 80% “daily” threshold may pause prematurely if minute RPM limits are fine. Blend both: minute‑level headroom and daily budget; prefer minute‑level to avoid unnecessary day‑long pauses.

## Concrete Tweaks to the Plan
- **API integration**: Add a small wrapper:
  - `responses_raw = client.responses.with_raw_response`
  - Use `resp = responses_raw.create(...); headers = resp.headers; body = resp.parse()`
  - Surface `headers` + `body.usage` to `QuotaMonitor`.
- **Backoff helper**: Single function `compute_backoff(attempt, kind, retry_after, base, cap, jitter)` used by the retry decorator. Ensure caps and 10% jitter are applied consistently.
- **Error classification util**: `classify_error(exc) -> {kind: rate_limit|quota|server|network, retry_after: Optional[int]}` using SDK types, `status_code`, and body error code when present.
- **Pause controller**: Implement `PauseController` with `Event`:
  - `pause()` sets event cleared; `wait()` blocks submitter; `resume_at(ts)` schedules resume.
  - Processor submits tasks only when `pause_event.is_set()`.
- **Configuration**:
  - Add env vars: `QUOTA_MONITORING`, `QUOTA_THRESHOLD`, `DAILY_REQUEST_LIMIT`, `PAUSE_DURATION_HOURS`, `QUOTA_LOG_INTERVAL`.
  - Update `.env.example`, CLI help, and validation ranges.
- **Tests**:
  - Mock `with_raw_response` objects exposing `headers` and `parse().usage`.
  - Unit tests for header parsing (missing/zero/units), backoff calculations, pause scheduling from reset headers, and thread safety under concurrency.

## Open Questions
- Should monitoring default to on for production but off for local runs, controlled by env? Proposal: on by default; set low verbosity in dev.
- Do we ever stream responses in this pipeline? If yes, confirm the exact call site to ensure raw headers and final usage are both captured.
- Do we need per‑prompt/token budgets (e.g., separate quotas per project) or only account against the account‑wide limit?

## Go/No‑Go
- Go, with the SDK header access change (`with_raw_response`) and pause mechanics adjustment. Defer adaptive concurrency behind a flag.

