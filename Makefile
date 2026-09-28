.PHONY: test run-backend run-frontend

test:
	cd backend && pytest -q

run-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm install && npm run dev -- --host 0.0.0.0
