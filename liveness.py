from backend_api import Liveness, InstructionLiveness
import ir

def solve_liveness(cfg):
    uses = {}
    definitions = {}
    for start, block in cfg.blocks.items():
        block_use = set()
        block_def = set()
        for instruction in cfg.function.instructions[block.start:block.stop]:
            block_use.update(ir.uses(instruction) - block_def)
            block_def.update(ir.defs(instruction))
        uses[start] = block_use
        definitions[start] = block_def

    live_in = {start: set() for start in cfg.blocks}
    live_out = {start: set() for start in cfg.blocks}
    changed = True
    while changed:
        changed = False
        for start in reversed(cfg.blocks):
            block = cfg.blocks[start]
            out = set().union(*(live_in[successor] for successor in block.successors))
            incoming = uses[start] | (out - definitions[start])
            if out != live_out[start] or incoming != live_in[start]:
                live_out[start] = out
                live_in[start] = incoming
                changed = True
    return Liveness(live_in, live_out)


def solve_instruction_liveness(cfg, liveness):
    """Retorne os conjuntos antes e depois de cada instrução."""
    before = {}
    after = {}
    instructions = cfg.function.instructions
    for start, block in cfg.blocks.items():
        live = set(liveness.live_out[start])
        for index in range(block.stop - 1, block.start - 1, -1):
            after[index] = set(live)
            instruction = instructions[index]
            live = ir.uses(instruction) | (live - ir.defs(instruction))
            before[index] = set(live)
    return InstructionLiveness(before, after)
