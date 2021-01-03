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
                    print(successor_dominators, dominators, successors)
                    print(successor, dominator)
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
def get_dominator_frontier_cooper(num_blocks, dominators_map, predecessors_map, idom):
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

# https://www.ed.tus.ac.jp/j-mune/keio/m/ssa2.pdf
def insert_phi_node(blocks, dominators, block_id_to_names):
    blocks_with_phi_nodes = copy(blocks)


def main():
    args = parse_args()
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        blocks = [x for x in form_blocks(func["instrs"])]
        cfg = form_cfg(blocks)
        for node in cfg:
            print(node)
        predecessors_map = get_predecessors(cfg)
        successors_map = get_successors(cfg)
        block_id_to_names = {node.id: node.name for node in cfg}
        if args["verbose"]:
            for idx, block in enumerate(blocks):
                print(idx, block)
            print("predecessors_map")
            predecessors_map = get_predecessors(cfg)
            for node_id, predecessors in predecessors_map.items():
                print("{} : {}".format(block_id_to_names[node_id], [block_id_to_names[i] for i in predecessors]))
            print("successors_map")
            successors_map = get_successors(cfg)
            for node_id, successors in successors_map.items():
                print("{} : {}".format(block_id_to_names[node_id], [block_id_to_names[i] for i in successors]))
        dominators_map = get_dominators(len(blocks), predecessors_map)
        print("Dominators")
        for i, dominators in dominators_map.items():
            print("{}: {}".format(
                block_id_to_names[i],
                ", ".join(sorted([block_id_to_names[j] for j in dominators]))))
        df_map = get_dominator_frontier(len(blocks), dominators_map,
                                        successors_map)
        print("Dominator Frontier")
        for i, df in df_map.items():
            print("{}: {}".format(
                block_id_to_names[i],
                ", ".join(sorted([block_id_to_names[j] for j in df]))))
        idom = get_dominator_tree(successors_map)
        df_map = get_dominator_frontier_cooper(len(blocks), dominators_map, predecessors_map, idom)
        print("Dominator Frontier")
        for i, df in df_map.items():
            print("{}: {}".format(
                block_id_to_names[i],
                ", ".join(sorted([block_id_to_names[j] for j in df]))))


if __name__ == "__main__":
    main()
