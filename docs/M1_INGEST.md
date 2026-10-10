# M1 ingest decisions

- CSV uses streaming `csv.reader` with delimiter sniffing, UTF-8 BOM, and a documented cp1252 fallback.
- XLSX is read-only streamed via openpyxl. Excel's loss of precision for long numeric identifiers cannot be repaired; oversized floating identifiers are rejected via downstream missing-SKU validation. Keep identifiers as text in source.
- Duplicate policies are `error`, `first`, `last`, `merge`. Disk-backed SQLite preserves bounded memory. Merge means last nonempty field wins (not semantic concatenation).
- Two-digit year ranges are rejected as ambiguous rather than guessed.
- Non-English titles are **flagged**, not translated. No live provider call is made.
- Images are URL-pattern checked locally; network reachability is not tested.
- Rows that normalize incorrectly go to rejects.csv with a reason code, not their source data.
- Per-cell strings larger than 100 KB and malformed CSV encodings require additional hardening; see LIMITATIONS.
