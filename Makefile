run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v	

pine:
	python -m pipeline.sec_client

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

EVAL_PY ?= .venv-eval/Scripts/python.exe

# Free and deterministic: no LLM calls (main .venv)
eval:
	python -m evaluation.validate
	python -m evaluation.retrieval_check
	python -m evaluation.score_deterministic
	python -m evaluation.report

# Costly: real LLM calls, slow, rate-limited (run deliberately)
eval-run:
	python -m evaluation.run_agent

eval-grade:
	$(EVAL_PY) -m evaluation.grade_ragas