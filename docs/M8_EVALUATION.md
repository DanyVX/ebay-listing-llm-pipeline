# M8 evaluation harness: evidence boundaries

The repository includes 100 fully synthetic cases and 40 *machine-generated expected-value* references. **These are not human-written annotations**, so the human-rubric criterion remains unfulfilled until two independent raters evaluate 30 outputs using eval/human_rubric.csv.

Use `python -m eval.benchmark --sample 100 --output results/offline.json` to run a real measured CPU-only deterministic baseline. `python -m eval.plot results/offline.json --output results/cost_quality.png` plots measured results. Every result includes its git SHA, package versions, platform and timestamp.

Three-model API comparison, prompt/router ablations, paid-model cost/latency numbers, and real injection attack-success rates remain **TBD (not yet measured)**. Do not compare a deterministic baseline with real LLMs as though they were the same experiment. The statistical functions support paired bootstrap intervals once real comparable outputs are supplied.
