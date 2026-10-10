# M7 resumable batch runner

- Offline-first asynchronous bounded batch with SQLite checkpoints and commit-per-row. Stable row-index ordering, cache invalidation on input hash + prompt/rules version, recoverable failure records, partial success export and atomically replaced output snapshots.
- Exclusive lock file rejects concurrent writers; **a crash can leave a stale lock**. Investigate and remove manually before resume. Multiple hosts sharing the same database are unsupported.
- `--dry-run` counts rows and never creates state or contacts an API. Live HTTP integration remains opt-in only and is not CLI-wired at M7.
- Cost caps remain enforced in the separate opt-in HTTP client. Offline runs use the deterministic no-spend baseline.
- Fatal OS failures such as disk full still abort; earlier committed row checkpoints remain for reruns.
- Async orchestration offloads row computation to bounded worker threads because the M7 baseline is local. True concurrent remote clients and cancellation mid-provider-call are not yet production-hardened.
