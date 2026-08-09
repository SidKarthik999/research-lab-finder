.PHONY: backup migrate test docker-build docker-run restore-to-neon

DB_NAME := research_lab_finder
BACKUP_DIR := database/backups

backup:
	mkdir -p $(BACKUP_DIR)
	pg_dump -d $(DB_NAME) -f "$(BACKUP_DIR)/$(DB_NAME)_$$(date +%Y%m%d_%H%M%S).sql"

migrate:
	python -m database.migrate

test:
	python -m pytest

docker-build:
	docker build -t research-lab-finder .

# Local sanity check before trusting the image on Render -- talks to the
# same local Postgres dev already uses via host.docker.internal, since the
# container's own localhost isn't the host's. Requires OPENAI_API_KEY etc
# in the environment or --env-file .env.
docker-run: docker-build
	docker run --rm -p 8000:8000 \
		-e DATABASE_URL="postgresql://$$(whoami)@host.docker.internal/$(DB_NAME)" \
		--env-file .env \
		research-lab-finder

# One-time move of the local database into Neon. Usage:
#   make restore-to-neon NEON_URL="postgresql://user:pass@ep-xxx.neon.tech/research_lab_finder?sslmode=require"
# Run `make backup` first regardless -- this doesn't touch the local DB, but
# a fresh dump is what actually gets loaded into Neon.
restore-to-neon:
	@if [ -z "$(NEON_URL)" ]; then echo "Usage: make restore-to-neon NEON_URL=<connection string>"; exit 1; fi
	pg_dump -d $(DB_NAME) --no-owner --no-privileges | psql "$(NEON_URL)"
