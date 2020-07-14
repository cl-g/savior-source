import os
import sys
import ConfigParser
import subprocess
import multiprocessing
import utils
import logging
import signal
import shutil
import time
from ConfigParser import NoOptionError

def get_libFuzzer(config, target):
    """libFuzzer fuzzer specific initialization code"""
    return libFuzzer(config, target)

def fuzzer_info(s):
    print utils.bcolors.HEADER+"[libFuzzer-Info]"+utils.bcolors.ENDC," {0}".format(s)

class libFuzzer:
    def __init__(self, config, target):
        print("init called")
        self.test_id_candidates = {}
        self.config = config
        self.target = target # passed via '-t' to moriarty.py
        self.get_libfuzzer_config()
        print("init finish")


    def __repr__(self):
        return "Fuzzer: libFuzzer"

    def get_fuzzer_cov_file(self):
        return self.combine_cov_file

    def get_fuzzer_san_file(self):
        return self.combine_san_file

    def get_libfuzzer_config(self):
        config = ConfigParser.ConfigParser()
        config.read(self.config)
        if "libFuzzer" not in config.sections():
            print "Config file read error"
            sys.exit()
        if "auxiliary info" not in config.sections():
            print "Config file read error"
            sys.exit()

        self.binary = config.get("libFuzzer", "bin")
        self.corpus_dir = config.get("libFuzzer", "corpus_dir").replace("@target", self.target)
        print("SET corpusdir to: " + self.binary)

        self.cov_suffix_dir = config.get("libFuzzer", "cov_suffix_dir").replace("@target", self.target)
        self.jobs = config.get("libFuzzer", "jobs")

        try:
            self.dictionary = config.get("libFuzzer", "use_dict").replace("@target", self.target)
        except Exception:
            self.dictionary = None

        try:
            self.combine_cov_file = config.get("auxiliary info", "cov_edge_file").replace("@target", self.target)
        except NoOptionError:
            self.combine_cov_file = os.path.join(self.target,".afl_coverage_combination")

        try:
            self.combine_san_file = config.get("auxiliary info", "bug_edge_file").replace("@target", self.target)
        except NoOptionError:
            self.combine_san_file = os.path.join(self.target,".savior_sanitizer_combination")
        
    def run(self):
        logger = multiprocessing.log_to_stderr()
        logger.setLevel(logging.INFO)
        libfuzzer_args = []
        libfuzzer_args.append(self.binary) # binary instrumented with libFuzzer
        libfuzzer_args.append(self.corpus_dir) # corpus directory
        libfuzzer_args.append("-cov_suffix_dir=" + self.cov_suffix_dir) # dir with suffixed test cases to enable pre_filter()
        libfuzzer_args.append("-reload=1") # Reload in_dir to pick up new test cases from KLEE
        libfuzzer_args.append("-jobs="+self.jobs) # is > 1 required for reload to work?
        libfuzzer_args.append("-max_len="+str(1024*1024)) # 1 mb
        libfuzzer_args.append("-verbosity=2")
        if self.dictionary is not None:
		    libfuzzer_args.append("-dict="+self.dictionary)

        try_num = 10000
        os.environ["UBSAN_OPTIONS"] = "log_path=" + self.target + "/ubsan-violations"
        while try_num > 0:
            p = multiprocessing.Process(target=utils.exec_async, args=[libfuzzer_args], kwargs={})
            print "Starting libFuzzer:", " ".join(libfuzzer_args)
            p.start()
            time.sleep(3)
            try_num -= 1
            if p.is_alive():
                break
        print "libFuzzer started."
        
    def terminate_callback(self):
        """called when SIGINT and SIGTERM"""
        # self.cleanup_synced_klee_instances(self.out_dir)
        pass
    def periodic_callback(self):
        """place holder"""
        pass
    """REMOVE all klee_instances under sync_dir"""
    def cleanup_synced_klee_instances(self, sync_dir):
	    pass
