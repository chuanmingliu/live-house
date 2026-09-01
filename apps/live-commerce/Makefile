.PHONY: install run test clean

install:
	python -m pip install -e ".[all]"

run:
	uvicorn livecommerce.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

clean:
	rm -rf .pytest_cache src/*.egg-info src/**/__pycache__ tests/__pycache__
	rm -f data/*.db data/*.db-*
