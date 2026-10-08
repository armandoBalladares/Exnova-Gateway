.PHONY: install run test docker-up
install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
run:
	APP_ENV=local uvicorn app.main:create_app --factory --reload --port 8000
test:
	pytest
docker-up:
	APP_ENV=dev docker compose up --build -d
