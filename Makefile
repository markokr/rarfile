
VER := $(shell python3 setup.py --version)
TGZ = dist/rarfile-$(VER).tar.gz

prefix = /usr/local

all:
	pyflakes3 rarfile.py
	tox -e lint
	tox -e py38-cryptography

install:
	python setup.py install --prefix=$(prefix)

sdist: clean $(TGZ)

clean:
	rm -rf __pycache__ build dist .tox
	rm -f *.pyc MANIFEST *.orig *.rej *.html *.class test/*.pyc
	rm -rf doc/_build doc/_static doc/_templates doc/html
	rm -rf .coverage cover*
	rm -rf *.egg-info
	rm -f test/files/*.rar.[pjt]* *.diffs

toxclean: clean
	rm -rf .tox

$(TGZ):
	rm -f dist/*
	python3 setup.py sdist

upload: $(TGZ)
	twine upload $(TGZ)

ack:
	for fn in test/files/*.py27; do \
		cp $$fn `echo $$fn | sed 's/py27/exp/'` || exit 1; \
	done

