.PHONY: backup migrate test

DB_NAME := research_lab_finder
BACKUP_DIR := database/backups

backup:
	mkdir -p $(BACKUP_DIR)
	pg_dump -d $(DB_NAME) -f "$(BACKUP_DIR)/$(DB_NAME)_$$(date +%Y%m%d_%H%M%S).sql"

migrate:
	python -m database.migrate

test:
	python -m pytest
