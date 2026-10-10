# Limitations and known gaps

- **M0 only:** ingestion, real LLM generation, grounding, compliance execution, rendering, exports, and evaluation are not implemented.
- Rule YAML covers only a small verified subset. Per-category item specifics must come from a current eBay taxonomy/marketplace lookup; there is no legal clearance.
- No live eBay publishing, API requests, scraping, or user data.
- Fresh-clone install, Python 3.11/3.12 CI, and Docker builds have not yet been verified.
- No lockfile is committed: execution environment has no registry connectivity. Direct dependencies are pinned; transitive dependencies are not fully locked yet.
- Sandbox is CPU-only; Docker, GPU, and gitleaks are unavailable locally. CI setup remains to be exercised.
- CI secret scans only detect known patterns; a **private local denylist** must be maintained outside the repository. No automated scanner guarantees complete leak detection.
- Budget reservation bounds require future provider adapters to reserve **worst-case** output token charges before calling providers. M0 does not call providers.
- The repository is MIT licensed but this does **not** license models, supplier data, third-party descriptions, or real seller assets.

- M1 input can detect common encodings but does not auto-detect arbitrary legacy encodings; ambiguous two-digit years are rejected. Raw long Excel numeric IDs may be irrecoverably damaged by Excel. Read [M1 ingest decisions](M1_INGEST.md).

- M1-M9 offline prototype exists; 3 real-model evaluation, 40 hand-written gold references, 30 double-rated human samples, provider API integration, verified eBay category aspect lookups, crash-kill demonstration and final demo are incomplete. The current evaluation references are MACHINE-GENERATED and explicitly labeled as such.
