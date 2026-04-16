.PHONY: test db-bootstrap run-app run-worker seed-stack1 seed-stack2

test:
	pytest -q

db-bootstrap:
	python scripts/db_bootstrap.py

seed-stack1:
	python scripts/seed_stack1.py

run-app:
	python -m app.main

run-worker:
	python -m app.worker

seed-stack2:
	python scripts/seed_stack2.py
