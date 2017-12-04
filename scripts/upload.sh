#!/bin/bash

cwd=$(pwd)

cd $(dirname $0)

source "packaging.rc"

cd ..

if [ ! -f ${dist} ]; then
    echo "Package does not exist. Did you forget to build?"
    exit 1
fi;

twine upload ${dist}

cd ${cwd}
