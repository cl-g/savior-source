#!/bin/bash
ROOT_DIR=/root/git/savior-source/tests/sqlite3-savior-libFuzzer/sqlite3-2/build/obj-savior-bigger
CORPUS_DIR=$ROOT_DIR/corpus
#this is actually the libfuzzer binary
SAVIOR_BINARY=$ROOT_DIR/savior-sqlite3
STDERR_LOG_DIR=$ROOT_DIR/evaluation_dir/stderr_logs

rm -rf $STDERR_LOG_DIR
mkdir -p $STDERR_LOG_DIR

# Replay all fuzzer test cases in the savior binary,
# and log all triggered bugs
for FULL_PATH in $CORPUS_DIR/*; do
	[ -e "$FULL_PATH" ] || continue
	FILE_NAME="${FULL_PATH##*/}"
     	echo "F: $FILE_NAME"
     	echo "P: $FULL_PATH"
	if [ -f "${FULL_PATH}" ] ; then #must be file, not dir
		# Uncomment savior binary/fuzzer, depending on if we want to reproduce the violations triggered in the fuzzer or savior build.
		# libFuzzer's UBSAN is newer, and by default fsanitize=integer covers more cases (e.g. implicit casts).
		#savior binary:
		$SAVIOR_BINARY < $FULL_PATH 2>&1 >/dev/null | grep "error" > "$STDERR_LOG_DIR/stderr-$FILE_NAME"
		#fuzzer:
		#/root/git/savior-source/tests/libpcap_paper_libFuzzer/build/fuzz_pcap $FULL_PATH 2>&1 >/dev/null | grep "error" > "$STDERR_LOG_DIR/stderr-$FILE_NAME"
	fi
done

# Deduplicate the bugs
#cat $STDERR_LOG_DIR/* > $STDERR_LOG_DIR/combined
find $STDERR_LOG_DIR -type f -name "*" -exec cat '{}' ';' > $STDERR_LOG_DIR/combined
python2 deduplicate_regex.py "$STDERR_LOG_DIR/combined" > $STDERR_LOG_DIR/unique_bugs

echo "All bugs found:"
cat $STDERR_LOG_DIR/unique_bugs
