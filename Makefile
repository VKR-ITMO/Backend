ifeq ($(shell test -e '.env' && echo -n yes),yes)
	include .env
endif


APPLICATION_NAME = vkr_itmo
POSTGRES_CONTAINER = vkr_itmo_postgres
CODE = $(APPLICATION_NAME) tests


run:  ##@Application Run application server
	poetry run python -m $(APPLICATION_NAME)

db:
	docker compose up -d

open_db:  ##@Database Open database inside docker-image
	docker exec -it $(POSTGRES_CONTAINER) psql -d $(POSTGRES_DB) -U $(POSTGRES_USER)

migrate:  ##@Database Do all migrations in database
	cd $(APPLICATION_NAME)/db && alembic upgrade $(args)

.PHONY: format
format:
	ruff check --fix $(APPLICATION_NAME) tests
	ruff format $(APPLICATION_NAME) tests

.PHONY: lint
lint: format
	pylint $(APPLICATION_NAME) tests
	mypy $(APPLICATION_NAME) tests

.PHONY: type-check
type-check:
	mypy $(APPLICATION_NAME) tests

clean_db:
	alembic downgrade -1