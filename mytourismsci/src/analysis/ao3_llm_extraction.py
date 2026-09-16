"""AO3: LLM-assisted extraction of policy commitments.

Extract quantitative tourism commitments from Malaysian government policy
documents (RMK13, state tourism master plans) using Claude Sonnet 4.5.
Human validation target: >= 85% precision on stratified sample.

Inputs: docs/policy_documents/ (PDF sources)
Outputs: outputs/ (structured extractions, validation report)
Dependencies: anthropic, pandas, pdfplumber
"""
