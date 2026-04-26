.PHONY: test db-bootstrap run-app run-bootstrap run-bots run-worker run-worker-projector run-worker-reminder run-worker-all smoke-import smoke-settings smoke-dispatcher smoke-worker-modes smoke-launch seed-stack1 seed-stack2

test:
	pytest -q

db-bootstrap:
	python scripts/db_bootstrap.py

seed-stack1:
	python scripts/seed_stack1.py

run-app: run-bootstrap

run-bootstrap:
	APP_RUN_MODE=bootstrap python -m app.main

run-bots:
	APP_RUN_MODE=polling python -m app.main

run-worker:
	python -m app.worker

run-worker-projector:
	WORKER_MODE=projector python -m app.worker

run-worker-reminder:
	WORKER_MODE=reminder python -m app.worker

run-worker-all:
	WORKER_MODE=all python -m app.worker


smoke-import:
	python scripts/smoke_import_app.py

smoke-settings:
	python scripts/smoke_settings.py

smoke-dispatcher:
	python scripts/smoke_dispatcher.py

smoke-worker-modes:
	python scripts/smoke_worker_modes.py

smoke-launch: smoke-import smoke-settings smoke-worker-modes smoke-dispatcher

seed-stack2:
	python scripts/seed_stack2.py
