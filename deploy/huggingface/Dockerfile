# SYNERA API on a Hugging Face Docker Space. Differences from Dockerfile.api: port 7860 and a user with uid 1000,
# which is what Spaces run containers as. The ledger signing key is generated at start-up inside the container and is
# never part of the image.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=1 PORT=7860
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu torch && pip install ".[api,ml]"
COPY backend ./backend
COPY configs ./configs
COPY scripts ./scripts
COPY data ./data
RUN useradd --create-home --uid 1000 user && mkdir -p /app/artifacts && chown -R user /app
USER user
EXPOSE 7860
CMD ["sh", "-c", "python scripts/bootstrap.py --quick && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
