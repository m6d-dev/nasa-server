FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /code

COPY requirements.txt .
# xgboost is optional: without it patterns come from the rule (BACKEND_TZ §8.3)
ARG WITH_XGBOOST=1
RUN pip install -r requirements.txt && if [ "$WITH_XGBOOST" = "1" ]; then pip install "xgboost>=3,<4"; fi

COPY src ./src
COPY docs/actions.yaml ./docs/actions.yaml

EXPOSE 8000
CMD ["python", "-m", "src.main"]
