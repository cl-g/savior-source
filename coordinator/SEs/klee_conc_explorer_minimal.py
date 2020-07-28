import ConfigParser
from ConfigParser import NoOptionError
import multiprocessing
import subprocess
import os
import sys
import utils
import signal
from utils import bcolors


def se_info(s):
    print bcolors.HEADER+"[KleeConc-Info]"+bcolors.ENDC," {0}".format(s)

class ConcExplorer:
    def __init__(self, config, target):
        self.jobs = {}
        self.started_jobs = set()
        self.config = config
        self.target = target
        self.get_config()
        utils.mkdir_force(self.seed_dir)
        self.pid_ctr = 0
        se_info("Concolic Explorer using searcher[{0}]".format(''.join(self.get_search_heuristics())))

    def get_config(self):
        config = ConfigParser.ConfigParser()
        config.read(self.config)
        self.bin = config.get("klee conc_explorer", "bin")
        self.converter = config.get("klee conc_explorer","converter")
        self.seed_dir = config.get("klee conc_explorer", "klee_seed_dir").replace("@target", self.target)
        self.search_heuristics = "None"
        #self.search_heuristics = config.get("klee conc_explorer", "search_heuristic").split(":")
        self.target_bc = config.get("moriarty", "target_bc").replace("@target", self.target).split()[0]
        self.options = config.get("moriarty", "target_bc").replace("@target", self.target).split()[1:]
        self.klee_err_dir = config.get("klee conc_explorer", "error_dir").replace("@target", self.target)

        try:
            self.max_time_per_seed = config.get("klee conc_explorer", "max_time_per_seed")
        except Exception:
            # by default no time limit per seed.
            self.max_time_per_seed = '0'

        try:
            self.max_output = config.get("klee conc_explorer", "max_interesting_output")
        except Exception:
            self.max_output = None

        try:
            self.max_mem = config.get("klee conc_explorer", "max_memory")
        except Exception:
            self.max_mem = str(1024*1024*1024) # 1gb

        try:
	        self.max_loop_bounds = config.get("klee conc_explorer", "max_loop_bounds")
        except Exception:
	        self.max_loop_bounds = None

        self.bitmodel = config.get("moriarty", "bitmodel")
        self.input_type = config.get("moriarty", "inputtype")
        self.sync_dir_base = config.get("moriarty", "sync_dir").replace("@target", self.target)
        
        '''
        if "AFLUnCovSearcher" in self.get_search_heuristics():
            try:
                self.fuzzer_cov_file = config.get("auxiliary info", "cov_edge_file").replace("@target", self.target)
            except NoOptionError:
                self.fuzzer_cov_file = os.path.join(self.target,".afl_coverage_combination")
        
        #handling cxx options
        try:
            self.klee_ctor_stub = True if config.get("klee conc_explorer", "klee_ctor_stub") == '1' else False
        except Exception:
            self.klee_ctor_stub = False

        try:
            self.klee_uclibcxx = True if config.get("klee conc_explorer", "klee_uclibcxx") == '1' else False
        except Exception:
            self.klee_uclibcxx = False
        '''

    def __repr__(self):
        return "SE Engine: KLEE Concolic Explorer (minimal)"


    def get_search_heuristics(self):
        """return a list of search heuristics"""
        return self.search_heuristics

    def exceed_mem_limit(self):
        pass

    def alive(self):
        alive = False
        multiprocessing.active_children()
        for pid in [self.jobs[x]['real_pid'] for x in self.jobs]:
            try:
                os.kill(pid, 0)
                print "conc_explorer pid: {0} is alive".format(pid)
                alive = True
            except Exception:
                print "conc_explorer pid: {0} not alive".format(pid)

        return alive

    def run(self, input_id_map_list, cov_file):
        """
            -create seed-out-dir
            For each input,
                -convert ktest move to seed-out-dir
            -create sync dir
            -build cmd
            -create new process job
        """
        assert(len(input_id_map_list) == 1) # 1 KLEE per seed

        pid = self.get_new_pid()
        klee_seed_dir = self.seed_dir + "/klee_instance_conc_"+str(pid)
        utils.mkdir_force(klee_seed_dir)
        input_counter = 0
        max_input_size = 0

        se_info("{0} activated. input list : {1}".format(self, [x['input'] for x in  input_id_map_list]))
        se_info("{0} activated. input score : {1}".format(self, [x['score'] for x in  input_id_map_list]))
        try:
            se_info("{0} activated. input size: {1}".format(self, [x['size'] for x in  input_id_map_list]))
        except Exception:
            pass
        for input_id_map in input_id_map_list:
            #--generate klee seed ktest
            # print input_id_map
            afl_input = input_id_map['input']
            if max_input_size < os.path.getsize(afl_input):
                max_input_size = os.path.getsize(afl_input)
            klee_seed = klee_seed_dir+"/"+str(input_counter).zfill(6)+".ktest"
            # print "before calling converter"
            self.call_converter("a2k", afl_input, klee_seed, self.bitmodel, self.input_type)
            input_counter += 1
            if not os.path.exists(klee_seed):
                print "no seed" + klee_seed
                continue


	    #--create sync_dir for new klee instance
        # Do not add ' +"/queue"', because AFAIK libfuzzer reload-dir() only looks for seeds in tld + tld+1. so /klee_instance/a.xml is ok, but /klee/instance/queue/a.xml is not found.
	    new_sync_dir = self.sync_dir_base+"/klee_instance_conc_"+str(pid).zfill(6) #+"/queue"
	    utils.mkdir_force(new_sync_dir)
	
	    #--build klee instance cmd
	    edge_ids = [x for x in input_id_map['interesting_edges']]
	    klee_cmd = self.build_cmd(klee_seed, new_sync_dir, max_input_size, afl_input) # was klee_seed, but as the directory only contains 1 seed atm, pass seed.
	    print ' '.join(klee_cmd)

	    #--construct process meta data, add to jobs list
	    kw = {'mock_eof':True, 'mem_cap': self.max_mem, 'use_shell':True}
	    p = multiprocessing.Process(target=utils.exec_async, args=[klee_cmd], kwargs=kw)
	    p.daemon = True
	    task_st = {}
	    task_st['instance'] = p
	    task_st['sync_dir'] = new_sync_dir
	    task_st['seed'] = klee_seed
	    task_st['cmd'] = klee_cmd
	    #if "AFLUnCovSearcher" in self.get_search_heuristics():
	    #    task_st['afl_cov'] = self.fuzzer_cov_file
	    self.jobs[pid] = task_st

        for pid, task in self.jobs.iteritems():
            try:
                if pid not in self.started_jobs:
                    task['instance'].start()
                    task['real_pid'] = task['instance'].pid
                    # print "starting klee process: ", task['real_pid']
                    self.started_jobs.add(pid)
                else:
                    se_info("WTF the process {0} is already started".format(pid))
            except Exception:
                pass



    def stop(self):
        """
        Terminate all jobs,
        you could have more fine-grained control by extending this function
        """
        se_info("{0} deactivated".format(self))
        for pid, task in self.jobs.iteritems():
            se_info("Terminting klee instance: {0} {1} real pid:{2}".format(pid, task['instance'], task['real_pid']))
            utils.terminate_proc_tree(task['real_pid'])
        #reset jobs queue
        self.jobs = {}
        # self.started_jobs= set()


    def build_cmd(self, ktest_seed_dir, sync_dir, max_len, afl_input):
        """
        each afl_testcase will have a list of branch ids,
        we use these info to construct the command for
        starting a new klee instance

        by default:
         use klee's own searching algo
         if specified afl_uncov in config, use AFLUnCovSearcher
        """
        klee_out_uncov = "--klee-covered-branchid-outfile="
        #sanitizer_searcher_flag = "--edge-sanitizer-heuristic"
        #remove_uninterested_edge_flag = "-remove-unprioritized-states"

        '''
        if self.klee_uclibcxx == True:
            klee_libc = "--libc=uclibcxx"
        else:
            klee_libc = "--libc=uclibc"

        if self.klee_ctor_stub == True:
            klee_ctor_stub="--disable-inject-ctor-and-dtor=false"
        else:
            klee_ctor_stub="--disable-inject-ctor-and-dtor=true"
        '''

        # ~/git/klee-server/klee-musthave/build/bin/klee --libc=uclibc --posix-runtime -sync-dir=/root/git/klee-server/RUN/syncdir -disable-ubsan-check=true --named-seed-matching --max-solver-time=5 -seed-time=150 -only-replay-seeds -only-seed -allow-seed-extension -allow-seed-truncation -allocate-determ=true -solver-backend=z3 --seed-file=libz.ktest /root/git/savior-source/tests/libz-savior-libfuzzer/zlib/build/obj-savior/savior-libz.dma.bc --sym-stdin 1000
        cmd = [self.bin,
                         "--libc=uclibc",
                         "--posix-runtime",
                         "--sync-dir="+sync_dir,
                         "--solver-backend=z3",
                         "--max-solver-time=5",
                         "-disable-ubsan-check=true",
                         "--named-seed-matching",
                         "-seed-time=150",
                         "-only-replay-seeds",
                         "-only-seed",
                         "-allow-seed-extension",
                         "-allow-seed-truncation",
                         "--max-memory=0",
                         "--seed-file="+ktest_seed_dir, # this is actually a single file for now
                         self.target_bc]

        new_options = list(self.options)
        for _ in xrange(len(new_options)):
            if new_options[_] == "INPUT_FILE":
                new_options[_] = "A"
        cmd.extend(new_options)
        if self.input_type == "stdin":
                cmd.append("--sym-stdin")
                cmd.append(str(max_len))
        else:
            if not "INPUT_FILE" in self.options:
                cmd.append("A")
            cmd.append("--sym-files")
            cmd.append("1")
            cmd.append(str(max_len))
        return cmd

    def get_new_pid(self):
        self.pid_ctr += 1
        return self.pid_ctr

    def call_converter(self, mode, afl_input, ktest, bitmodel, inputtype):
        """
        SEs directly invoke the converter to
        convert between the afl/klee file formats
        as the SE input format is specific to target SE engine
        """
        args = []
        args.append(self.converter)
        args.append("--mode="+ mode)
        args.append("--afl-name="+afl_input)
        args.append("--ktest-name="+ktest)
        args.append("--bitmodel="+bitmodel)
        args.append("--inputmode="+inputtype)
        subprocess.Popen(args).wait()

    def terminate_callback(self):
        """called when SIGINT and SIGTERM"""
        se_info("packing klee error cases into [{0}]".format(self.klee_err_dir))
        utils.pack_klee_errors(self.target, self.klee_err_dir)

    def periodic_callback(self):
        """called every 1 hour"""
        se_info("packing klee error cases into [{0}]".format(self.klee_err_dir))
        utils.pack_klee_errors(self.target, self.klee_err_dir)
