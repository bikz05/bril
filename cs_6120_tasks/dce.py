import json
import sys

# Usage
# function run_bril -a opt_name test_name run_opt; bril2json < $test_name  | if eval $run_opt; python3 ../$opt_name;
# else; cat; end | bril2txt | tee /tmp/bril_test.bril | bril2json | brili -p; cat /tmp/bril_test.bril; end
#
# function run_opt -a opt_name test_name; printf "OPT OFF:\n"; run_bril $opt_name $test_name false; printf "OPT ON:\n";
# run_bril $opt_name $test_name true; end
#
# // run from `(git_root)/my_examples/test`
# run_opt dce.py dce_1.bril
#
# Added test in `test folder` also.

def dce(instrs):
    while True:
        last_def = {}
        to_remove = set()
        for idx, instr in enumerate(instrs):
            if "args" in instr:
                for arg in instr["args"]:
                    if arg in last_def:
                        del last_def[arg]
            if "dest" in instr:
                if instr["dest"] in last_def:
                    to_remove.add(last_def[instr["dest"]])
                last_def[instr["dest"]] = idx
        to_remove = to_remove.union(set(last_def.values()))
        if len(to_remove) == 0:
            break
        instrs = [instr for idx, instr in enumerate(instrs) if idx not in to_remove]
    return instrs

def main(verbose=False):
    prog = json.load(sys.stdin)
    transformed = {"functions": []}
    for func in prog["functions"]:
        transformed_instrs = dce(func["instrs"])
        transformed_func = {"name": func["name"], "instrs": transformed_instrs}
        transformed["functions"].append(transformed_func)
    print(json.dumps(transformed))

if __name__ == "__main__":
    main(False)
