# Model card

**No trained or pretrained model is distributed or called at M0.**

The `fixture-local` adapter uses deterministic canned synthetic responses only, not a machine learning model. Intended use: testing configuration and error handling without network, data sharing, or spend.

Model details, licensing, dataset limitations, evaluation, and bias analysis: TBD once a model is selected and its license verified. Do not imply real-model results from fixture tests.

The deterministic baseline copies and restructures approved fields and is not pretrained; its outputs are not real LLM measurements. Optional HTTP provider adapters require explicit model, authenticated key, verified model pricing and positive user budgets before using external services. Provider model licenses must be checked individually.
