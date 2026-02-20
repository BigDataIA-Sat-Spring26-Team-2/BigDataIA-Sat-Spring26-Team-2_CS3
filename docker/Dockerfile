# 1. Start with Python base image
FROM python:3.11-slim

# 2. Set working directory inside container
WORKDIR /app

# 3. Install system dependencies + Poetry
RUN apt-get update \
 && apt-get install -y curl \
 && curl -sSL https://install.python-poetry.org | python3 - \
 && ln -s /root/.local/bin/poetry /usr/local/bin/poetry \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# 4. Copy Poetry files first (for caching)
COPY pyproject.toml poetry.lock ./

# 5. Install dependencies (NO venv inside container)
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

# 5a. Install Playwright Chromium browser + its system dependencies
RUN playwright install chromium --with-deps

# 6. Copy application code
COPY app ./app

# 6. Tell Docker the app uses port 8000
EXPOSE 8000

# 7. Command to run when container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]