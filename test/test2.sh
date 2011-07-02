#! /bin/sh

cp ../rarfile.py .

#ulimit -n 16

plist="python2.4 python2.5 python2.6 python2.7 python3.1 python3.2 pypy jython"

for py in $plist; do
  if which $py > /dev/null; then
    echo "== $py =="
    $py ./testseek.py
    $py ./testio.py
    $py ./testcorrupt.py --quick
  fi
done

rm -f rarfile.py

