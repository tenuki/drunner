#!/bin/bash
set -e -o pipefail
cd $INPUT_TARGET

echo actual path: $(pwd)
echo ls: $(ls)
echo cargo.toml?  $(ls Cargo.toml)

echo actual path: $(pwd) >> $OUTPUT_NAME
echo ls: $(ls) >> $OUTPUT_NAME
echo cargo.toml?  $(ls Cargo.toml) >> $OUTPUT_NAME
chmod a+rwx $OUTPUT_NAME