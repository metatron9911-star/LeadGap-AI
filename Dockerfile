FROM python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN python -m py_compile main.py outreach_v101.py smoke_test.py preflight_v101_test.py run_wave2_evidence_only.py run_wave2_evidence_score_only.py \
    && python smoke_test.py \
    && python preflight_v101_test.py

CMD ["python", "run_wave2_evidence_score_only.py"]
