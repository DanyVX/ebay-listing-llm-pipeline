# M3: injection resistance

Supplier fields are untrusted, delimited in model prompts, and screened by an offline heuristic. Suspicious segments are removed or the record is blocked. This guard is intentionally separate from deterministic compliance and grounding checks.

The fixture contains 26 synthetic attacks spanning role spoofing, multilingual directives, confusables, and URLs. Unit tests test recognition only. **No real model attack-success rate has been measured.** Detector false positives and missed adversarial phrasing remain possible. Vendor content is never treated as trusted instructions.
