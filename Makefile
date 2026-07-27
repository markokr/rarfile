
PYTHON ?= 3.10
CRYPTO ?= cryptography
RARFILE_REQUIRE_EXTENSION ?= 1
PYTHONS = 3.10 3.11 3.12 3.13 3.14 3.14t pypy3.11

ifneq ($(CRYPTO),)
CRYPTO_FLAG = --extra $(CRYPTO)
TESTTAG = $(PYTHON)-$(CRYPTO)
else
CRYPTO_FLAG =
TESTTAG = $(PYTHON)
endif

NEWS = doc/news.rst

VERSION = $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/rarfile/__init__.py)
RXVERSION = $(shell echo '$(VERSION)' | sed 's/\./[.]/g')
TAG = v$(VERSION)

ALL_SOURCES = $(wildcard setup.py pyproject.toml src/rarfile/*.py src/crypto/*.[ch])
BUILD_TAG = .venv/build.tag

INDENT = indent

.PHONY: test-venv test-all remove-tag
.PHONY: all test lint docs clean ack prepare release shownote unrelease

all: lint docs test

test-venv: remove-tag
	uv venv --python $(PYTHON) --clear
	RARFILE_REQUIRE_EXTENSION=$(RARFILE_REQUIRE_EXTENSION) \
	uv sync --no-dev --group test $(CRYPTO_FLAG) --reinstall-package rarfile
	uv run --no-sync pytest -n auto --cov=rarfile --cov-report=term --cov-report=html:cover/$(TESTTAG)
	uv run --no-sync bash test/run_dump.sh python "$(TESTTAG)"

test-all: remove-tag
	for py in $(PYTHONS); do \
		for crypto in "" pycryptodome cryptography; do \
			$(MAKE) test-venv PYTHON=$$py CRYPTO=$$crypto; \
		done; \
	done

remove-tag:
	@rm -f $(BUILD_TAG)

$(BUILD_TAG): $(ALL_SOURCES)
	RARFILE_REQUIRE_EXTENSION=1 \
	uv sync --reinstall-package rarfile
	uv run python3 -c 'import rarfile._crypto'
	touch $@

test: $(BUILD_TAG)
	uv run pytest -n auto --cov=rarfile --cov-report=term --cov-report=html:cover/$(TESTTAG)
	uv run bash test/run_dump.sh python "$(TESTTAG)"

lint: $(BUILD_TAG)
	uv run ruff check src test
	uv run pylint rarfile dumprar.py test

docs: $(BUILD_TAG)
	uv run sphinx-build -q -W -b html doc doc/_build

fmt:
	uv run ruff check --fix src
	uv run autopep8 -i *.py src/**/*.py test/*.py
	uv run isort *.py src/**/*.py test/*.py

cfmt:
	$(INDENT) src/*/*.[ch]

clean:
	rm -rf __pycache__ build dist
	rm -f *.pyc MANIFEST *.orig *.rej *.html *.class test/*.pyc
	rm -rf doc/_build doc/_static doc/_templates doc/html
	rm -rf .coverage cover*
	rm -rf src/*.egg-info
	rm -f test/files/*.rar.[0-9]* test/files/*.rar.pypy* *.diffs
	rm -rf tmp
	rm -rf src/rarfile/__pycache__
	rm -f src/rarfile/*.so src/rarfile/*.pyd
	rm -f .coverage.*
	rm -rf .venv .tox .ruff_cache __pycache__ .pytest_cache
	rm -f src/crypto/*.[ch]~

ack:
	for fn in test/files/*.rar.$(TESTTAG); do \
		cp $$fn `echo $$fn | sed 's/[.]rar[.].*/.rar.exp/'` || exit 1; \
	done

prepare:
	@echo "Checking version - $(VERSION)"
	@grep -qE '^\w+ $(RXVERSION)\b' $(NEWS) \
	|| { echo "Version '$(VERSION)' not in $(NEWS)"; exit 1; }
	@echo "Checking git repo"
	@git diff --stat --exit-code || { echo "ERROR: Unclean repo"; exit 1; }

release: prepare
	git tag $(TAG)
	git push github $(TAG):$(TAG)

shownote:
	awk -v VER="$(VERSION)" -f doc/note.awk $(NEWS) \
	| pandoc -f rst -t gfm --wrap=none

unrelease:
	git push github :$(TAG)
	git tag -d $(TAG)
