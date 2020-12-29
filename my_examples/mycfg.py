import json
import sys

TERMINATORS = ("jmp", "br", "ret")

# :!bril2json < test/interp/jmp.bril | python3 my_examples/mycfg.py
def form_blocks(body):
    block = []
    for instr in body:
        if "op" in instr and instr["op"] in TERMINATORS:
            block.append(instr)
            yield block
            block = []
        elif "label" in instr:
            if len(block) > 0:
                yield block
            block = [instr]
        else:
            block.append(instr)
    if len(block) > 0:
        yield block

class Node:
    def __init__(self, block, block_id, child_block_ids):
        self.block = block
        self.id = block_id
        self.child_block_ids = child_block_ids
    def __str__(self):
        return "block_id {}, block: {}, child_block_ids {}".format(self.id, self.child_block_ids, self.block)

def form_cfg(blocks):
    ids_map = {}
    for idx, block in enumerate(blocks):
        if "label" in block[0]:
            ids_map[block[0]["label"]] = idx
    cfg = []
    for idx, block in enumerate(blocks):
        if "op" in block[-1] and block[-1]["op"] in TERMINATORS:
            if "labels" in block[-1]:
                child_block_ids = [ids_map[label] for label in block[-1]["labels"]]
            else:
                child_block_ids = None
            cfg.append(Node(block, idx, child_block_ids))
        else: # Enter next block
            cfg.append(Node(block, idx, [idx + 1 if idx + 1 < len(blocks) else None]))
    return cfg

def mycfg():
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        blocks = [x for x in form_blocks(func["instrs"])]
        func_name = func["name"] if "name" in func else "noname_function"
        print("--- FUNCTION {} --- ".format(func_name))
        print("blocks")
        for idx, block in enumerate(blocks):
            print(idx, block)
        cfg = form_cfg(blocks)
        print("cfg")
        for node in cfg:
            print(node)

if __name__ == "__main__":
    mycfg()
