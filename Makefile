# Tor-li dev helpers. The Python venv lives at the repo root (venv/); backend
# commands run from backend/ and reference it as ../venv/bin/...
#
# Usage:
#   make backend      # run FastAPI on :8000 (auto-reload)
#   make frontend     # serve the consumer SPA on :3001
#   make kill-ports   # free :8000 and :3001 (fixes "Address already in use")
#   make test         # backend unit tests
#   make dev          # kill stale ports, then start the backend

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3001

.PHONY: backend frontend kill-ports test dev

backend:
	cd backend && ../venv/bin/uvicorn app.main:app --port $(BACKEND_PORT) --reload

frontend:
	cd frontend/consumer && python3 -m http.server $(FRONTEND_PORT)

# Kill whatever is holding the dev ports. Leading '-' so a no-match is not fatal.
kill-ports:
	-@lsof -ti tcp:$(BACKEND_PORT)  | xargs kill -9 2>/dev/null || true
	-@lsof -ti tcp:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null || true
	@echo "freed ports $(BACKEND_PORT) + $(FRONTEND_PORT)"

test:
	cd backend && ../venv/bin/python -m pytest tests/ -q

dev: kill-ports backend
