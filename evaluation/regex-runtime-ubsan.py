import sys
import re

# Idea:
# jdarith.c:308:53: runtime error: left shift of negative value -5
# jdarith.c:308:53: runtime error: left shift of negative value -7
# Same bug, but uniq cannot deduplicate this.
# We take the first word after "runtime error: " to differentiate between different bug categories on the same line.
def main():
	assert len(sys.argv) == 2, "argc"
	f = open(sys.argv[1], 'r')
	lines = f.readlines() 
	s = set()
	pattern = re.compile("^(.*\.c):(\d+):(\d+):\sruntime error:\s(\w+).*$")
	for l in lines:
		m = pattern.search(l)
		if m:
			s.add((m.group(1), m.group(2), m.group(3), m.group(4)))

	sorted_by_line = sorted(s, key=lambda tup: tup[1])
        print("Set: " + "\n".join([str(m) for m in sorted_by_line]))
        #print("Set: " + "\n".join([str(m) for m in s]))
	print("Size of set: {}".format(len(s)))
			

if __name__ == "__main__":
	main()
