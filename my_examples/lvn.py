import json
import sys
from collections import namedtuple
from enum import Enum
from dce import dce

# Usage
# function run_bril -a opt_name test_name run_opt; bril2json < $test_name  | if eval $run_opt; python3 ../$opt_name;
# else; cat; end | bril2txt | tee /tmp/bril_test.bril | bril2json | brili -p; cat /tmp/bril_test.bril; end
#
# function run_opt -a opt_name test_name; printf "OPT OFF:\n"; run_bril $opt_name $test_name false; printf "OPT ON:\n";
# run_bril $opt_name $test_name true; end
#
# // run from `(git_root)/my_examples/test`
# run_opt lvn.py lvn_1.bril
#
# Added test in `test folder` also.


class Ops:
    ARITHMETIC = ["add", "mul", "sub", "div"]


LvnTableValue = namedtuple("LvnTableValue",
                           ['idx', 'op', 'dest', 'args_table_idx', 'value'])


class LvnBaseValue:
    pass


class LvnIdValue(LvnBaseValue):
    def __init__(self, op, var):
        self.op = op
        self.var = var

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.op == other.op and self.var == other.var
        return False

    def __hash__(self):
        return hash(self.var) ^ hash(self.op)

    def __str__(self):
        return "op {}, var {}".format(self.op, self.var)


class LvnConstValue(LvnBaseValue):
    def __init__(self, op, value):
        self.op = op
        self.value = value

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.op == other.op and self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value) ^ hash(self.op)

    def __str__(self):
        return "op {}, value {}".format(self.op, self.value)


class LvnOpValue(LvnBaseValue):
    def __init__(self, op, args_table_idx):
        self.op = op
        self.args_table_idx = args_table_idx

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.op == other.op and self.args_table_idx == other.args_table_idx
        return False

    def __hash__(self):
        return hash(len(self.args_table_idx)) ^ hash(self.op)

    def __str__(self):
        return "op {}, args_table_idx {}".format(self.op, self.args_table_idx)


class LvnTableEntry:
    def __init__(self, idx, value, dest):
        self.value = value
        self.idx = idx
        self.dest = dest

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.value == other.value
        if isinstance(other, LvnBaseValue):
            return self.value == other
        return False

    def __hash__(self):
        return hash(self.value)

    def __str__(self):
        return "idx {} dest {} {}".format(self.idx, self.dest, self.value)


def is_overwritten(instrs, instr_idx):
    dest = instrs[instr_idx]["dest"]
    for instr in instrs[instr_idx + 1:]:
        if "dest" in instr and instr["dest"] == dest:
            return True
    return False


def perform_arth(val_1, val_2, op):
    if op == "add":
        return val_1 + val_2
    elif op == "sub":
        return val_1 - val_2
    elif op == "mul":
        return val_1 * val_2
    elif op == "div":
        return val_1 / val_2
    raise RuntimeError("{} not supported.", op)


def lvn(verbose=False):
    prog = json.load(sys.stdin)
    transformed = {"functions": []}
    for func in prog["functions"]:
        instrs = func["instrs"]
        transformed_instrs = [func["instrs"], []]
        ### LVN (start)
        instr_idx = False
        change = True
        while change:
            change = False
            table = []
            var2num = {}  # mapping from variable name to index to table.
            for idx, instr in enumerate(transformed_instrs[instr_idx]):
                if "dest" in instr:
                    dest = instr["dest"]
                    arg_indices = []
                    args_names = []
                    if "args" in instr:
                        for arg in instr["args"]:
                            arg_indices.append(var2num[arg])
                            args_names.append(table[var2num[arg]].dest)
                    const_value = None
                    if "value" in instr:
                        const_value = instr["value"]
                    if "op" in instr:
                        value = None
                        if instr["op"] == "const":
                            value = LvnConstValue(instr["op"], const_value)
                        elif instr["op"] == "id":
                            # Copy propagation
                            arg_index = arg_indices[0]
                            while True:
                                if isinstance(table[arg_index].value,
                                              LvnIdValue):
                                    arg_index = table[arg_index].value.var
                                else:
                                    break
                            if isinstance(table[arg_index].value,
                                          LvnConstValue):
                                value = table[arg_index].value
                                instr = {
                                    "dest": instr["dest"],
                                    "op": "const",
                                    "value": value.value,
                                    "type": "int"
                                }
                            else:
                                value = LvnIdValue(instr["op"], arg_index)
                            # instr["dest"] = table[arg_indices[0]].dest
                        elif instr["op"] in Ops.ARITHMETIC:
                            if instr["op"] in ["add", "mul"]:
                                # CSE exploiting commutativity
                                arg_indices = sorted(arg_indices)
                            value_1 = table[arg_indices[0]].value
                            value_2 = table[arg_indices[1]].value
                            if isinstance(value_1,
                                          LvnConstValue) and isinstance(
                                              value_2, LvnConstValue):
                                val = perform_arth(value_1.value,
                                                   value_2.value, instr["op"])
                                instr = {
                                    "dest": instr["dest"],
                                    "op": "const",
                                    "value": val,
                                    "type": "int"
                                }
                                value = LvnConstValue(instr["op"], val)
                            else:
                                value = LvnConstValue(instr["op"], arg_indices)
                        assert (value)
                    # print(instr)
                    # print(value)
                    for table_entry in table:
                        changed = True
                        if table_entry == value:
                            num = table_entry.idx
                            # print(table_entry.dest)
                            instr["dest"] = table_entry.dest
                            break
                    else:
                        num = len(table)
                        if is_overwritten(transformed_instrs[instr_idx], idx):
                            # Assuming the prefix `lvn_` is not in a variable name.
                            instr["dest"] = "lvn_" + str(idx)
                        table.append(LvnTableEntry(num, value, instr["dest"]))
                        # print("Adding {}.".format(instr))
                        transformed_instrs[not instr_idx].append(instr)
                    var2num[dest] = num
                    if "args" in instr:
                        instr["args"] = args_names
                else:
                    if "args" in instr:
                        args_names = []
                        for arg in instr["args"]:
                            args_names.append(table[var2num[arg]].dest if arg
                                              in var2num else arg)
                        instr["args"] = args_names
                    transformed_instrs[not instr_idx].append(instr)
            instr_idx = not instr_idx
        transformed_instrs[instr_idx] = dce(transformed_instrs[instr_idx])
        # print("-- TABLE --")
        # for entry in table:
        #     print(entry)
        ## LVN (end)
        transformed_func = {
            "name": func["name"],
            "instrs": transformed_instrs[instr_idx]
        }
        transformed["functions"].append(transformed_func)
    print(json.dumps(transformed))


if __name__ == "__main__":
    lvn(False)
