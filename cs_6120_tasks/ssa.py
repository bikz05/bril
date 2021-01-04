import json
import sys
import argparse as ap
import copy
from cfg import *

def parse_args():
    parser = ap.ArgumentParser()
    parser.add_argument('-v', "--verbose", action="store_true")
    return vars(parser.parse_args())


def get_dominators(num_blocks, predecessors_map):
    dominators_map = {
        i: set(list(range(num_blocks)))
        for i in range(num_blocks)
    }
    while True:
        is_dom_changed = False
        for i in range(num_blocks):
            dominators_i = set([i])
            predecessors = predecessors_map[
                i] if i in predecessors_map else None
            if predecessors:
                dominators_i = dominators_i.union(
                    set.intersection(
                        *[dominators_map[j] for j in predecessors]))
            if dominators_i != dominators_map[i]:
                is_dom_changed = True
                dominators_map[i] = dominators_i
        if not is_dom_changed:
            break
    return dominators_map


# This is what I quicked coded up based on the data structures avaiable.
def get_dominator_frontier(num_blocks, dominators_map, successors_map):
    df_map = {}
    for i in range(num_blocks):
        dominators = dominators_map[i] if i in dominators_map else []
        successors = successors_map[i] if i in successors_map else []
        for successor in successors:
            successor_dominators = dominators_map[
                successor] if successor in dominators_map else []
            for dominator in dominators:
                if dominator not in successor_dominators or (
                        dominator in successor_dominators
                        and successor == dominator):
                    if dominator in df_map:
                        df_map[dominator].add(successor)
                    else:
                        df_map[dominator] = {successor}
    return df_map


# DFS. -- http://pages.cs.wisc.edu/~fischer/cs701.f08/lectures/Lecture19.4up.pdf
def get_dominator_tree(successors_map):
    idom = {}
    visited = set()
    to_visit = [0]
    while len(to_visit) > 0:
        i = to_visit.pop()
        if i in visited:
            continue
        successors = successors_map[i] if i in successors_map else []
        for successor in successors:
            if successor not in idom:
                idom[successor] = i
            if successor not in to_visit:
                to_visit.append(successor)
        visited.add(i)
    return idom


# https://www.cs.rice.edu/~keith/EMBED/dom.pdf (Page 9)
def get_dominator_frontier_cooper(num_blocks, dominators_map, predecessors_map,
                                  idom):
    df_map = {}
    for i in range(num_blocks):
        predecessors = predecessors_map[i] if i in predecessors_map else []
        # dominators_i = dominators_map[i] if i in dominators_map else []
        if len(predecessors) >= 2:
            for predecessor in predecessors:
                runner = predecessor
                while runner != idom[i]:
                    if runner in df_map:
                        df_map[runner].add(i)
                    else:
                        df_map[runner] = {i}
                    runner = idom[runner]
    return df_map


def get_definitions(blocks):
    defs_map = {}
    for i, block in enumerate(blocks):
        for instr in block:
            if "dest" in instr:
                dest = instr["dest"]
                if dest in defs_map:
                    defs_map[dest].append(i)
                else:
                    defs_map[dest] = [i]
    return defs_map


# https://www.ed.tus.ac.jp/j-mune/keio/m/ssa2.pdf
def insert_phi_node(blocks, df_map, predecessors_map, block_id_to_names):
    defs_map = get_definitions(blocks)
    blocks_with_phi_nodes = copy.copy(blocks)
    inserted_block_node = {}
    for var, def_map in defs_map.items():
        for block_id in def_map:
            if block_id in df_map:
                for i in df_map[block_id]:
                    if i not in inserted_block_node:
                        inserted_block_node[i] = set()
                    if var not in inserted_block_node[i]:
                        instr_labels = []
                        instr_args = []
                        if i in predecessors_map:
                            for j in predecessors_map[i]:
                                instr_labels.append(block_id_to_names[j])
                                instr_args.append(var)
                        # TODO: Add check if first instruction is label.
                        blocks_with_phi_nodes[i].insert(
                            1, {
                                'op': 'phi',
                                'dest': var,
                                'type': 'int',
                                'labels': instr_labels,
                                'args': instr_args
                            })
                        inserted_block_node[i].add(var)
                        # check this once.
                        if i not in def_map:
                            def_map.append(i)
    return blocks_with_phi_nodes


def reverse_dominator_tree(idom):
    idom_reversed = {}
    for key, value in idom.items():
        if value not in idom_reversed:
            idom_reversed[value] = set()
        idom_reversed[value].add(key)
    return idom_reversed


def rename(blocks, successors_map, block_id_to_names, idom_reversed,
           var_name_stack, name_suffix_map, block_id):
    block = blocks[block_id]
    to_pop_from_stack = set()
    for i, instr in enumerate(block):
        if "op" in instr and instr["op"] != "phi":
            args = instr["args"] if "args" in instr else []
            renamed_args = []
            for arg in args:
                if arg in var_name_stack:
                    renamed_args.append(var_name_stack[arg][-1])
                else:
                    renamed_args.append(arg)
            if args:
                instr["args"] = renamed_args
        dest = instr['dest'] if 'dest' in instr else None
        if dest:
            len_stack = len(
                var_name_stack[dest]) if dest in var_name_stack else 0
            if dest not in name_suffix_map:
                name_suffix_map[dest] = 0
            else:
                name_suffix_map[dest] += 1
            new_name = dest + "_" + str(name_suffix_map[dest])
            if dest not in var_name_stack:
                var_name_stack[dest] = []
            var_name_stack[dest].append(new_name)
            instr["dest"] = new_name
            to_pop_from_stack.add(dest)
    if block_id in successors_map:
        block_name = block_id_to_names[block_id]
        for successor in successors_map[block_id]:
            succ_block = blocks[successor]
            for instr in succ_block:
                if "op" in instr and instr["op"] == "phi":
                    pos = instr["labels"].index(block_name)
                    old_value = instr["args"][pos]
                    if old_value in var_name_stack:
                        instr["args"][pos] = var_name_stack[old_value][-1]
    if block_id in idom_reversed:
        for succ_block_id in idom_reversed[block_id]:
            blocks = rename(blocks, successors_map, block_id_to_names,
                            idom_reversed, var_name_stack, name_suffix_map,
                            succ_block_id)
    for var_name in to_pop_from_stack:
        var_name_stack[var_name].pop()
    return blocks


def rename_global(blocks, successors_map, block_id_to_names, idom):
    var_name_stack = {}
    name_suffix_map = {}
    blocks_with_phi_nodes = rename(blocks, successors_map, block_id_to_names,
                                   reverse_dominator_tree(idom),
                                   var_name_stack, name_suffix_map, 0)
    for block in blocks_with_phi_nodes:
        for instr in block:
            if 'op' in instr and instr['op'] == 'phi':
                if 'args' in instr and 'labels' in instr:
                    updated_args = []
                    updated_labels = []
                    for arg, label in zip(instr["args"], instr["labels"]):
                        if arg not in var_name_stack:
                            updated_args.append(arg)
                            updated_labels.append(label)
                    instr['args'] = updated_args
                    instr['labels'] = updated_labels
    return blocks_with_phi_nodes


def remove_phi_nodes(blocks, block_id_to_names):
    block_names_to_id = {value: key for key, value in block_id_to_names.items()}
    for block in blocks:
        new_block = []
        for instr in block:
            if 'op' in instr and instr['op'] in 'phi':
                if 'args' in instr and 'labels' in instr:
                    dest = instr['dest']
                    for arg, label in zip(instr["args"], instr["labels"]):
                        pred_block_id = block_names_to_id[label]
                        new_instr = {"op": "id", "dest": dest, "args": [arg], "type": "int"}
                        last_instr = blocks[pred_block_id][-1]
                        if 'op' in last_instr and last_instr['op'] in TERMINATORS:
                            blocks[pred_block_id].insert(-1, new_instr)
                        else:
                            blocks[pred_block_id].append(new_instr)
            else:
                new_block.append(instr)
        block = new_block
    return blocks

def main():
    args = parse_args()
    prog = json.load(sys.stdin)
    transformed = {"functions": []}
    for func in prog["functions"]:
        blocks = [x for x in form_blocks(func["instrs"])]
        cfg = form_cfg(blocks)
        predecessors_map = get_predecessors(cfg)
        successors_map = get_successors(cfg)
        block_id_to_names = {node.id: node.name for node in cfg}
        dominators_map = get_dominators(len(blocks), predecessors_map)
        df_map = get_dominator_frontier(len(blocks), dominators_map,
                                        successors_map)
        idom = get_dominator_tree(successors_map)
        blocks_with_phi_nodes = insert_phi_node(blocks, df_map,
                                                predecessors_map,
                                                block_id_to_names)
        blocks_with_phi_nodes = rename_global(blocks_with_phi_nodes, successors_map,
                                       block_id_to_names, idom)
        blocks_with_phi_nodes = remove_phi_nodes(blocks_with_phi_nodes, block_id_to_names)
        if args["verbose"]:
            print("predecessors_map")
            predecessors_map = get_predecessors(cfg)
            for node_id, predecessors in predecessors_map.items():
                print("{} : {}".format(
                    block_id_to_names[node_id],
                    [block_id_to_names[i] for i in predecessors]))
            print("successors_map")
            successors_map = get_successors(cfg)
            for node_id, successors in successors_map.items():
                print("{} : {}".format(
                    block_id_to_names[node_id],
                    [block_id_to_names[i] for i in successors]))
            print("Dominators")
            for i, dominators in dominators_map.items():
                print("{}: {}".format(
                    block_id_to_names[i],
                    ", ".join(sorted([block_id_to_names[j] for j in dominators]))))
            print("Dominator Frontier")
            for i, df in df_map.items():
                print("{}: {}".format(
                    block_id_to_names[i],
                    ", ".join(sorted([block_id_to_names[j] for j in df]))))
            df_map = get_dominator_frontier_cooper(len(blocks), dominators_map,
                                                   predecessors_map, idom)
            print("Dominator Frontier")
            for i, df in df_map.items():
                print("{}: {}".format(
                    block_id_to_names[i],
                    ", ".join(sorted([block_id_to_names[j] for j in df]))))
        transformed_func = {
            "name": func["name"],
            "instrs": [instr for block in blocks_with_phi_nodes for instr in block]
        }
        transformed["functions"].append(transformed_func)
    print(json.dumps(transformed))


if __name__ == "__main__":
    main()
