## Title

<!-- Use Conventional Commits: feat:, fix:, docs:, chore:, refactor:, test: -->
<!-- Example: feat(api): integrate raw response header parsing (Task 2.1) -->

## Summary

- What changed and why (1–3 bullets)
- Context/links to plans or specs (e.g., plans/rate_limit_implementation_plan.md)

## Linked Issues

- Closes #<issue-number>
- Related to #<issue-number>

## How To Run

```bash
# Full test suite (offline-safe)
python3 run_tests.py

# Format and type-check
black artist_bio_gen/ tests/
mypy artist_bio_gen/

# Example run (adjust flags as needed)
python3 run_artists.py \
  --input-file examples/example_artists.csv \
  --prompt-id <id> \
  --output out.jsonl \
  --dry-run
```

## Sample Output

<!-- Paste a small snippet (5–10 lines) showing expected stdout and/or out.jsonl records. -->

```text
<paste a brief, anonymized excerpt of stdout>
```

```jsonl
{"artist_id": "...", "artist_name": "...", "response_text": "...", "response_id": "..."}
```

## Checklist

- [ ] Tests pass locally: `python3 run_tests.py`
- [ ] Code formatted: `black artist_bio_gen/ tests/`
- [ ] Type checks pass: `mypy artist_bio_gen/`
- [ ] No secrets committed; .env.local ignored
- [ ] README/help text updated if CLI flags changed
- [ ] Plan updated (if part of a tracked plan) and task marked completed

## Risk & Rollout

- Risk: Low / Medium / High
- Rollout: Merge → monitor → revert plan if needed
- Notes: Any migration, config, or operational considerations

