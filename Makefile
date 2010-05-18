
prefix = /usr/local

all:
	python setup.py build

install:
	python setup.py install --prefix=$(prefix)

tgz:
	python setup.py sdist

clean:
	rm -rf *.pyc build dist MANIFEST *.orig *.rej *.html

docs:
	asciidoc README
	rm -f html/*
	epydoc --no-private --no-sourcecode -n rarfile --no-frames -v rarfile

lint:
	pylint -e rarfile.py

