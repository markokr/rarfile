#! /bin/sh

JAVA_OPTIONS="-Dpython.path=`pwd`/.."
export JAVA_OPTIONS

plist="python3.7 python3.8 python3.9 python3.10 python3.11 python3.12 pypy3.9 pypy3.10"

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

