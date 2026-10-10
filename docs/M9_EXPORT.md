# M9 CLI/export

Commands are `elp ingest`, `elp run`, `elp validate`, `elp export`, `elp eval`, `elp costs`, and `elp policy-check`. All default to offline processing. There are **no** eBay API calls, source scrapers, or vendor integrations.

CSV cells beginning with spreadsheet-formula characters are apostrophe-prefixed before CSV quoting. JSONL keeps the typed, nested original. Exports replace files atomically and reject malformed listing objects without clobbering the destination.

A fully verified eBay bulk/Inventory API payload format is a later stretch goal. The present flat CSV is **not** a claim of an accepted eBay upload layout. Human/model evaluations and a demo GIF are outstanding; a v0.1.0 release tag should not be claimed until the Definition of Done is independently verified.
