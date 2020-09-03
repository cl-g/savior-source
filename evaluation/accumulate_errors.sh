#!/bin/bash
ROOT_DIR=/root/git/savior-source/tests/libxml2-target-libFuzzer/libxml2-2.9.7/target-obj-savior
CORPUS_DIR=$ROOT_DIR/corpus
SAVIOR_BINARY=$ROOT_DIR/savior-target
STDERR_LOG_DIR=$ROOT_DIR/evaluation_dir/stderr_logs

rm -rf $STDERR_LOG_DIR
mkdir -p $STDERR_LOG_DIR

# Replay all fuzzer test cases in the savior binary,
# and log all triggered bugs
for FULL_PATH in $CORPUS_DIR/*; do
	[ -e "$FULL_PATH" ] || continue
	FILE_NAME="${FULL_PATH##*/}"
     	echo "F: $FILE_NAME"
	$SAVIOR_BINARY < "$FULL_PATH" 2>&1 >/dev/null | grep "error" > "$STDERR_LOG_DIR/stderr-$FILE_NAME"
done

# Deduplicate the bugs
cat $STDERR_LOG_DIR/* > $STDERR_LOG_DIR/combined
python2 deduplicate_regex.py "$STDERR_LOG_DIR/combined" > $STDERR_LOG_DIR/unique_bugs

echo "All bugs found:"
cat $STDERR_LOG_DIR/unique_bugs
