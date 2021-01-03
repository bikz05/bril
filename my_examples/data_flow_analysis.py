import json
import sys
import argparse as ap
import copy
from mycfg import *

# bril2json < df_1.bril   | python3 ../data_flow_analysis.py -a live

def parse_args():
    parser = ap.ArgumentParser()
    analysis_names = ["defined", "live"]
    parser.add_argument('-a',
                        "--analysis",
                        choices=analysis_names,
                        default=analysis_names[0])
    parser.add_argument('-v', "--verbose", action="store_true")
    return vars(parser.parse_args())


def get_analysis_function(analysis_name):
    if analysis_name == "defined":
        return analysis_defined_variables
    elif analysis_name == "live":
        return analysis_live_variables
    raise RuntimeError("{} function not found".format(analysis_name))


def worklist_algorithm(in_block, out_block, blocks, predecessors_map,
                       successors_map, merge_func, transfer_func):
    worklist = {idx for idx in range(len(blocks))}
    while worklist:
        block_id = worklist.pop()
        predecessors = [
            out_block[idx] for idx in predecessors_map[block_id]
            if idx in out_block
        ] if block_id in predecessors_map else []
        in_block[block_id] = merge_func(predecessors)
        out_state = transfer_func(blocks[block_id], in_block[block_id])
        if block_id not in out_block or out_state != out_block[block_id]:
            out_block[block_id] = out_state
            if block_id in successors_map:
                worklist = worklist.union(successors_map[block_id])
    return in_block, out_block


def pretty_print_data_flow(num_blocks, block_id_to_names, in_block, out_block):
    for block_id in range(num_blocks):
        block_name = block_id_to_names[block_id]
        print("{}:".format(block_name))
        print("\tin:  {}".format(
            ", ".join(sorted(list(in_block[block_id]))) if block_id in in_block
            and len(in_block[block_id]) > 0 else "\u2205"))
        print("\tout: {}".format(
            ", ".join(sorted(list(out_block[block_id]))) if block_id in
            out_block and len(out_block[block_id]) > 0 else "\u2205"))


def analysis_defined_variables(blocks, predecessors_map, successors_map):
    def merge_func(predecessors):
        return set().union(*predecessors)

    def transfer_func(block, in_state):
        definitions = {instr['dest'] for instr in block if 'dest' in instr}
        # kill = {}
        return set().union(in_state, definitions)

    in_block = {}
    out_block = {}
    in_block, out_block = worklist_algorithm(in_block, out_block, blocks,
                                             predecessors_map, successors_map,
                                             merge_func, transfer_func)
    return in_block, out_block


def analysis_live_variables(blocks, predecessors_map, successors_map):
    def merge_func(successors):
        return set().union(*successors)

    def transfer_func(block, out_state):
        kill = set()
        killed_at = {}
        for idx, instr in enumerate(block):
            if 'dest' in instr:
                dest = instr['dest']
                kill.add(dest)
                killed_at[dest] = min(idx, killed_at[dest]) if dest in killed_at else idx

        gen = set()
        for idx, instr in enumerate(block):
            if "args" in instr:
                for arg in instr["args"]:
                    if arg in killed_at and killed_at[arg] < idx:
                        continue
                    gen.add(arg)
        return set().union(gen, out_state - kill)

    in_block = {}
    out_block = {}
    # In analysis is backward, we reverse successors_map and predecessors_map.
    out_block, in_block = worklist_algorithm(out_block, in_block, blocks,
                                             successors_map, predecessors_map,
                                             merge_func, transfer_func)
    return in_block, out_block


def main():
    args = parse_args()
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        blocks = [x for x in form_blocks(func["instrs"])]
        cfg = form_cfg(blocks)
        predecessors_map = get_predecessors(cfg)
        successors_map = get_successors(cfg)
        if args["verbose"]:
            for idx, block in enumerate(blocks):
                print(idx, block)
        block_id_to_names = {node.id: node.name for node in cfg}
        in_block, out_block = get_analysis_function(args["analysis"])(
            blocks, predecessors_map, successors_map)
        pretty_print_data_flow(len(blocks), block_id_to_names, in_block,
                               out_block)


if __name__ == "__main__":
    main()
