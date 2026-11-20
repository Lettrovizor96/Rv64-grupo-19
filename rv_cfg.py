from backend_api import CFG, BasicBlock
import ir


BRANCH_TYPES = (ir.Beq, ir.Bne, ir.Blt, ir.Bge, ir.Beqz, ir.Bnez)


def build_cfg(function):
    instructions = function.instructions
    if not instructions:
        return CFG(function, {}, None)

    labels = {
        instruction.label: index
        for index, instruction in enumerate(instructions)
        if isinstance(instruction, ir.LabelInstr)
    }
    leaders = {0, *labels.values()}
    terminators = (ir.Jump, ir.Return, *BRANCH_TYPES)
    for index, instruction in enumerate(instructions):
        if isinstance(instruction, terminators) and index + 1 < len(instructions):
            leaders.add(index + 1)

    bounds = sorted(leaders) + [len(instructions)]
    blocks = {
        start: BasicBlock(start, stop)
        for start, stop in zip(bounds, bounds[1:])
    }
    for block in blocks.values():
        last = instructions[block.stop - 1]
        if isinstance(last, (ir.Jump, *BRANCH_TYPES)):
            block.successors.add(labels[last.target])
        if block.stop < len(instructions) and not isinstance(last, (ir.Jump, ir.Return)):
            block.successors.add(block.stop)

    for start, block in blocks.items():
        for successor in block.successors:
            blocks[successor].predecessors.add(start)
    return CFG(function, blocks, 0)
