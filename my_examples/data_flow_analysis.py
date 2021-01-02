import json
import sys
import argparse as ap
import copy
from mycfg import *

TERMINATORS = ("jmp", "br", "ret")


def parse_args():
    parser = ap.ArgumentParser()
    analysis_names = ["defined_variables"]
    parser.add_argument('-a',
                        "--analysis",
                        choices=analysis_names,
                        default=analysis_names[0])
    parser.add_argument('-v', "--verbose", action="store_true")
    return vars(parser.parse_args())


def get_analysis_function(analysis_name):
    if analysis_name == "defined_variables":
        return analysis_defined_variables
    raise RuntimeError("{} function not found".format(analysis_name))


def worklist_algorithm(in_block, out_block, blocks, predecessors_map,
                       successors_map, merge_func, transfer_func):
    worklist = {idx for idx in range(len(blocks))}
    while worklist:
        block_id = worklist.pop()
        out_predecessors = [
            out_block[idx] for idx in predecessors_map[block_id]
            if idx in out_block
        ] if block_id in predecessors_map else []
        in_block[block_id] = merge_func(out_predecessors)
        out_b_updated = transfer_func(blocks[block_id], in_block[block_id])
        if block_id not in out_block or out_b_updated != out_block[block_id]:
            out_block[block_id] = out_b_updated
            if block_id in successors_map:
                worklist = worklist.union(successors_map[block_id])
    return in_block, out_block


def analysis_defined_variables(blocks, predecessors_map, successors_map,
                                  block_id_to_names):
    def merge_func(out_predecessors):
        return set().union(*out_predecessors)

    def transfer_func(block, in_block):
        definitions = {instr['dest'] for instr in block if 'dest' in instr}
        # kill = {}
        return set().union(in_block, definitions)

    in_block = {}
    out_block = {}
    in_block, out_block = worklist_algorithm(in_block, out_block, blocks,
                                             predecessors_map, successors_map,
                                             merge_func, transfer_func)
    for block_id in range(len(blocks)):
        block_name = block_id_to_names[block_id]
        print("{}:".format(block_name))
        print("\tin:  {}".format(
            ", ".join(sorted(list(in_block[block_id]))) if block_id in in_block
            and len(in_block[block_id]) > 0 else "\u2205"))
        print("\tout: {}".format(
            ", ".join(sorted(list(out_block[block_id]))) if block_id in
            out_block and len(out_block[block_id]) > 0 else "\u2205"))


def main():
    args = parse_args()
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        blocks = [x for x in form_blocks(func["instrs"])]
        cfg = form_cfg(blocks)
        predecessors_map = get_predecessors(cfg)
        successors_map = {}
        for node in cfg:
            if node.child_block_ids:
                successors_map[node.id] = set(node.child_block_ids)
        if args["verbose"]:
            for idx, block in enumerate(blocks):
                print(idx, block)
        block_id_to_names = {node.id: node.name for node in cfg}
        get_analysis_function(args["analysis"])(blocks, predecessors_map,
                                                successors_map,
                                                block_id_to_names)


if __name__ == "__main__":
    main()
