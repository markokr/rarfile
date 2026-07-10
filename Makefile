
PYTHON ?= 3.10
CRYPTO ?= cryptography
PYTHONS = 3.10 3.11 3.12 3.13 3.14 3.14t pypy3.10 pypy3.11

ifneq ($(CRYPTO),)
CRYPTO_FLAG = --extra $(CRYPTO)
TESTTAG = $(PYTHON)-$(CRYPTO)
else
CRYPTO_FLAG =
TESTTAG = $(PYTHON)
endif

# build with Py_LIMITED_API (abi3) on CPython >= 3.11, skip 3.10, pypy and free-threaded builds (no stable ABI there yet)
ifneq ($(filter $(PYTHON),3.10 $(filter pypy% %t,$(PYTHON))),)
ABI3_ENV =
else
ABI3_ENV = ABI3=1
endif

NEWS = doc/news.rst

VERSION = $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/rarfile/__init__.py)
RXVERSION = $(shell echo '$(VERSION)' | sed 's/\./[.]/g')
TAG = v$(VERSION)

.PHONY: all test test-all lint docs clean ack prepare release shownote unrelease

all: lint docs test

test:
	uv venv --python $(PYTHON) --clear
	$(ABI3_ENV) uv sync --group test $(CRYPTO_FLAG) --reinstall-package rarfile
	uv run --no-sync pytest -n auto --cov=rarfile --cov-report=term --cov-report=html:cover/$(TESTTAG)
	uv run --no-sync bash test/run_dump.sh python "$(TESTTAG)"

test-all:
	for py in $(PYTHONS); do \
		for crypto in "" pycryptodome cryptography; do \
			$(MAKE) test PYTHON=$$py CRYPTO=$$crypto; \
		done; \
	done

lint:
	uv venv --python $(PYTHON) --clear
	uv sync --group lint --group test
	uv run --no-sync pyflakes src
	uv run --no-sync pylint rarfile dumprar.py test

docs:
	uv venv --python $(PYTHON) --clear
	uv sync --group docs --reinstall-package rarfile
	uv run --no-sync sphinx-build -q -W -b html doc doc/_build

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
	rm -f uv.lock

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
