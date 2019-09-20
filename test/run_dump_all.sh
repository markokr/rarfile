#! /bin/sh

JAVA_OPTIONS="-Dpython.path=`pwd`/.."
export JAVA_OPTIONS

plist="python3.6 python3.7 python3.8 pypy jython"

result=0
for py in $plist; do
  if which $py > /dev/null; then
    ./test/run_dump.sh "$py" "$py" || result=1
    echo ""
  else
    echo $py not available
    echo ""
  fi
done

