# M5 grounding verifier

The deterministic verifier checks exact structured fitment subsets, part/model/year/numeric tokens, brand and MPN, provenance keys, and unsupported generic quality claims against source fields. Year range expansion is allowed. Differences in numeric formatting such as 12V vs 12 V normalize to the same token.

The score is supported checks / total checks and **is not a calibrated probability of truth**. The regex is conservative and has both false-positive and false-negative cases (full paraphrase equivalence and free-form qualitative claims are open problems). Source text might itself be false; this mechanism verifies attribution, not supplier authenticity. LLM fact-checking is optional and must never replace deterministic verification.
