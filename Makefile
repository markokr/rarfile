
prefix = /usr/local

web = mkz@shell.berlios.de:/home/groups/rarfile/htdocs

htmls = README.html FAQ.html NEWS.html

all:
	python setup.py build

install:
	python setup.py install --prefix=$(prefix)

tgz:
	python setup.py sdist

clean:
	rm -rf *.pyc build dist MANIFEST *.orig *.rej *.html


%.html: %
	rst2html $< $@

docs: $(htmls)
	rm -f html/*
	epydoc --no-private --no-sourcecode -n rarfile --no-frames -v rarfile

lint:
	pylint -E rarfile.py

upload: docs
	rsync -avz html/* $(web)/doc/
	rsync -avz README.html $(web)/index.html
	rsync -avz NEWS.html FAQ.html $(web)/

