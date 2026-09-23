FROM python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN python -m py_compile main.py outreach_v101.py smoke_test.py preflight_v101_test.py run_wave2_evidence_only.py run_wave2_evidence_score_only.py run_wave2_hook_grounding_only.py run_wave2_all_gates_diagnostic.py run_wave2_ctg_evidence_substitution_only.py run_wave2_role_matrix_only.py run_wave2_omegacode_source_substitution_only.py run_wave2_omegacode_grounding_bundle_repair.py run_wave3_date_extraction_diagnostic.py run_wave3_date_extraction_full_rerun.py run_wave3_source_selection_full_rerun.py run_wave3_derived_state_recompute.py run_wave3_kkdigital_hook_grounding_repair.py run_wave3_brandactive_successor.py run_wave3_brandactive_evidence_discovery.py src/enrichment/date_extraction.py src/enrichment/source_selection.py src/enrichment/derived_state.py src/enrichment/brandactive_successor.py \
    && python smoke_test.py \
    && python preflight_v101_test.py \
    && python -m unittest test_date_extraction.py

CMD ["python", "run_wave3_brandactive_evidence_discovery.py"]
