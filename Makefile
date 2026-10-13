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
