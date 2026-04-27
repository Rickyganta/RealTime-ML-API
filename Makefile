.PHONY: setup dev-api dashboard repair-venv up down loadtest loadtest-read loadtest-mixed seed-interactions gen-benchmark-png gen-readme-header

setup:
	python3 scripts/download_movielens.py
	docker compose up --build -d
	docker compose exec api python scripts/seed_movies.py

dev-api:
	chmod +x scripts/dev_api.sh
	./scripts/dev_api.sh

dashboard:
	./.venv/bin/python -m streamlit run dashboard/app.py --server.port 8502 --server.address 127.0.0.1

repair-venv:
	./.venv/bin/python -m pip install --force-reinstall -r requirements.txt

gen-benchmark-png:
	./.venv/bin/python scripts/generate_benchmark_png.py

gen-readme-header:
	./.venv/bin/python scripts/generate_streamlit_readme_header.py

seed-interactions:
	./.venv/bin/python scripts/seed_interactions.py

up:
	docker compose up --build

down:
	docker compose down

loadtest: loadtest-read

loadtest-read:
	set -a && [ -f .env ] && . ./.env && set +a; \
	export LOADTEST_BYPASS_TOKEN="$${LOADTEST_BYPASS_TOKEN:-dev-only-bypass}"; \
	./.venv/bin/python -m locust -f locust/locustfile_readonly.py --host http://localhost:8000

loadtest-mixed:
	set -a && [ -f .env ] && . ./.env && set +a; \
	export LOADTEST_BYPASS_TOKEN="$${LOADTEST_BYPASS_TOKEN:-dev-only-bypass}"; \
	./.venv/bin/python -m locust -f locust/locustfile_mixed.py --host http://localhost:8000
