.DEFAULT_GOAL := all
poetry = poetry run

.PHONY: install
install:
	poetry install --with dev

.PHONY: lint
lint:
	$(poetry) ruff format
	$(poetry) ruff check --fix

.PHONY: sync
sync:
	poetry install --sync --with dev

.PHONY: all
all: lint