FROM python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Real outreach batches are gated by deterministic synthetic pre-flight tests.
RUN python -m py_compile main.py outreach_v101.py smoke_test.py preflight_v101_test.py \
    && python smoke_test.py \
    && python preflight_v101_test.py

CMD ["python", "main.py"]
