VENV := .venv
ARTIFACTORY_URL := https://artifactory.riotinto.com/artifactory/api/pypi/riotinto-pypi

PYTHON := poetry run python
TOUCH := $(PYTHON) -c 'import sys; from pathlib import Path; Path(sys.argv[1]).touch()'

poetry.lock: pyproject.toml
	poetry lock

# Build venv with both conda and python deps.
$(VENV): environment.yml
	@echo Installing Conda environment
	@conda env update --prefix $@ --prune --file $^
	@echo Installing Poetry environment
	@pip install -U pkginfo
	@poetry install
	@$(TOUCH) $@

# Convenience target to build venv
.PHONY: setup
setup: $(VENV)

.PHONY: check
check: $(VENV)
	@echo Checking Poetry lock: Running poetry check --lock
	@poetry check --lock
	@echo Linting code: Running pre-commit
	@poetry run pre-commit run -a

.PHONY: test
test: $(VENV)
	@echo Testing code: Running pytest
	@poetry run coverage run -p -m pytest

.PHONY: coverage
coverage: $(VENV)
	@echo Testing covarage: Running coverage
	@poetry run coverage combine
	@poetry run coverage html --skip-covered --skip-empty
	@poetry run coverage report

.PHONY: docs
docs: $(VENV)
	@echo Building docs: Running sphinx-build
	@poetry run sphinx-build -W -d build/doctrees docs build/html

.PHONY: build
build:
	@echo Creating wheel file
	@poetry build

.PHONY: publish
publish:
	@echo Publishing: Dry run
	@poetry config repositories.artifactory $(ARTIFACTORY_URL)
	@poetry publish --repository artifactory --username $(ARTIFACTORY_USERNAME) --password $(ARTIFACTORY_PASSWORD) --dry-run
	@echo "Publishing."
	@poetry publish --repository artifactory --username $(ARTIFACTORY_USERNAME) --password $(ARTIFACTORY_PASSWORD)

.PHONY: clean
clean:
	@echo Cleaning ignored files
	@git clean -Xfd

.DEFAULT_GOAL := test
