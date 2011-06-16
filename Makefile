
prefix = /usr/local

web = mkz@shell.berlios.de:/home/groups/rarfile/htdocs

htmls = README.html FAQ.html NEWS.html

all:
	python setup.py build

install:
	python setup.py install --prefix=$(prefix)

tgz: clean
	python setup.py sdist

clean:
	rm -rf __pycache__ build dist
	rm -f *.pyc MANIFEST *.orig *.rej *.html *.class
	make -C test clean


%.html: %
	rst2html $< $@

docs: $(htmls)
	rm -f html/*
	epydoc --simple-term --no-private --no-sourcecode -n rarfile --no-frames -v rarfile

lint:
	pylint -E rarfile.py

upload: docs
	rsync -avz html/* $(web)/doc/
	rsync -avz README.html $(web)/index.html
	rsync -avz NEWS.html FAQ.html $(web)/

