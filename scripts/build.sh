#!/bin/bash

cwd=$(pwd)

cd $(dirname $0)

source "packaging.rc"

cd ..

if [ -f ${dist} ]; then
    echo "Package already exists. Did you forget to increase version number?"
    exit 1
fi;

python3 setup.py sdist

cd ${cwd}
