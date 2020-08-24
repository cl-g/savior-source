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
        self.test_id_candidates = {}
        self.config = config
        self.target = target # passed via '-t' to moriarty.py
        self.get_libfuzzer_config()

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
            print("Config file read error")
            sys.exit()
        if "auxiliary info" not in config.sections():
            print("Config file read error")
            sys.exit()

        self.binary = config.get("libFuzzer", "bin")
        self.corpus_dir = config.get("libFuzzer", "corpus_dir").replace("@target", self.target)
        self.cov_suffix_dir = config.get("libFuzzer", "cov_suffix_dir").replace("@target", self.target)
        self.jobs = config.get("libFuzzer", "jobs")

        try:
            self.max_len = config.get("libFuzzer", "max_len")
        except Exception:
            self.max_len = None
        
        # If positive, indicates the maximum total time in seconds to run the fuzzer. If 0 (the default), run indefinitely.
        # --> used to conduct experiments for a fixed amount of time
        try:
            self.max_total_time = config.get("libFuzzer", "max_total_time")
        except Exception:
            self.max_total_time = None
            
        try:
            self.dictionary = config.get("libFuzzer", "use_dict").replace("@target", self.target)
        except Exception:
            self.dictionary = None
        
        try:
            self.seed = config.get("libFuzzer", "seed").replace("@target", self.target)
        except Exception:
            self.seed = None

        try:
            self.combine_cov_file = config.get("auxiliary info", "cov_edge_file").replace("@target", self.target)
        except NoOptionError:
            self.combine_cov_file = os.path.join(self.target, ".afl_coverage_combination")

        try:
            self.combine_san_file = config.get("auxiliary info", "bug_edge_file").replace("@target", self.target)
        except NoOptionError:
            self.combine_san_file = os.path.join(self.target, ".savior_sanitizer_combination")
        
    def run(self):
        logger = multiprocessing.log_to_stderr()
        logger.setLevel(logging.INFO)
        libfuzzer_args = []
        libfuzzer_args.append(self.binary) # binary instrumented with libFuzzer
        libfuzzer_args.append(self.corpus_dir) # corpus directory
        libfuzzer_args.append("-cov_suffix_dir=" + self.cov_suffix_dir) # dir with suffixed test cases to enable pre_filter()
        libfuzzer_args.append("-reload=1") # Reload in_dir to pick up new test cases from KLEE
        libfuzzer_args.append("-jobs="+self.jobs)
        #libfuzzer_args.append("-verbosity=2")

        if self.max_len is not None:
            libfuzzer_args.append("-max_len="+self.max_len)
        else:
            print("Warning: max_len is not specified. libFuzzer will try to infer the maximum input length from the corpus.")
        
        if self.max_total_time is not None:
            libfuzzer_args.append("-max_total_time="+self.max_total_time)
        else:
            print("Warning: max_total_time is not set. libFuzzer will run indefinitely.")
        
        if self.seed is not None:
            libfuzzer_args.append("-seed="+self.seed)
        else:
            print("Warning: seed is not set. libFuzzer will choose a random seed.")

        if self.dictionary is not None:
		    libfuzzer_args.append("-dict="+self.dictionary)

        try_num = 10000
        #The line below removes ubsan violation output from main .log files -> we need this for evalscript though.
        #os.environ["UBSAN_OPTIONS"] = "log_path=" + self.target + "/ubsan-violations"
        while try_num > 0:
            self.p = multiprocessing.Process(target=utils.exec_async, args=[libfuzzer_args], kwargs={})
            print "Starting libFuzzer:", " ".join(libfuzzer_args)
            self.p.start()
            time.sleep(3)
            try_num -= 1
            if self.p.is_alive():
                break
        print "libFuzzer started."
        
    def terminate_callback(self):
        """called when SIGINT and SIGTERM"""
        # self.cleanup_synced_klee_instances(self.out_dir)
        pass
    def periodic_callback(self):
        # If libFuzzer terminated (due to time limit reached), savior will be shut down.
        if not self.p.is_alive():
            return False
        return True


    """REMOVE all klee_instances under sync_dir"""
    def cleanup_synced_klee_instances(self, sync_dir):
	    pass