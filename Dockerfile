# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --quiet pytest

# Default command runs the two-run demo (transient failure + idempotent re-run).
# Override:
#   docker run --rm <image> python sim/cli.py --dry-run
#   docker run --rm <image> python evals/run.py
#   docker run --rm <image> python evals/run.py golden-forms.json sim/data/forms-responses.json sim/data/mapping-config-forms.json
#   docker run --rm <image> python -m pytest sim/tests/ -q
CMD ["python", "sim/run.py"]
