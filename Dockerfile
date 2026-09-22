FROM python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Frozen product/pre-flight gates remain unchanged; Run A' adds only the isolated
# email-stage script on this experiment branch.
RUN python -m py_compile main.py outreach_v101.py smoke_test.py preflight_v101_test.py run_wave2_email_only.py \
    && python smoke_test.py \
    && python preflight_v101_test.py

CMD ["python", "run_wave2_email_only.py"]
