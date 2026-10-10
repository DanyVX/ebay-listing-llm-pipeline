# M2 structured generation

- The model sees a JSON user data object and a strict Pydantic JSON schema; unknown values must be omitted. Model output cannot contain raw HTML.
- `DeterministicClient` is a CPU-only baseline, **not an LLM** and not evidence of real model quality.
- `BudgetedHttpClient` is opt-in, with HTTPS for remote hosts, bounded retry, and a worst-case pre-call dollar reservation. It is *not activated* by the default CLI.
- Some vendors do not support `response_format=json_object` or `temperature=0`; compatibility must be tested per explicit endpoint/model. The generic JSON mode is validated post-response and repaired with feedback.
- Provider timeouts may occur after charge. Reservations remain held to fail closed until reconciliation.
- Max prompt byte/token sizes are not yet enforced for real providers; fitment chunking is deferred to M7.
