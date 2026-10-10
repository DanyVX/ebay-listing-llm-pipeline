# Contributing

- Open an issue before expanding a milestone; branches: `m<N>-<slug>`.
- Keep commits small and Conventional Commit styled.
- Run `python scripts/tasks.py lint`, `typecheck`, `test`, and `privacy-scan` before review.
- Do not commit real supplier or seller data, business identifiers, credentials, prompts from unrelated products, model weights, or large files.
- No live eBay requests. Use only synthetic fixtures and mocked LLM calls.
- Changes to rule assumptions require source URLs, dates, and a design-log entry. A changed prompt must increment its version.
