.PHONY: test db-bootstrap run-app run-worker

test:
	pytest -q

db-bootstrap:
	python scripts/db_bootstrap.py

run-app:
	python -m app.main

run-worker:
	python -m app.worker
