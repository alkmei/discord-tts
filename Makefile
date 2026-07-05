.PHONY: makemigrations migrate dev help clearmigrations

makemigrations:  # Generate migration files
	uv run python manage.py makemigrations

migrate:  # Apply migrations
	uv run python manage.py migrate

clearmigrations:  # Delete all migration files
	find apps -path '*/migrations/*.py' ! -name '__init__.py' -delete

dev:  # Start honcho with Procfile
	uv run honcho start

help:  # Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?# .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?# "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
