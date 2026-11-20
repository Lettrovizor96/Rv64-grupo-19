"""Construa os LRs globais da função a partir dos pontos de liveness."""

import ir


def build_live_ranges(cfg, points):
    instructions = cfg.function.instructions

    # Cada ponto existente participa de um componente, inclusive definições
    # mortas, que têm um ponto "after" próprio.
    parent = {}
    max_id = -1

    for index, instruction in enumerate(instructions):
        outputs = points.after[index] | ir.defs(instruction)
        for phase, values in (("before", points.before[index]), ("after", outputs)):
            for value in sorted(values, key=lambda reg: reg.id):
                key = (index, phase, value)
                parent[key] = key
                max_id = max(max_id, value.id)

    def find(item):
        root = item
        while parent[root] != root:
            root = parent[root]
        while item != root:
            next_item = parent[item]
            parent[item] = root
            item = next_item
        return root

    def union(left, right):
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    # Um valor vivo atravessa uma instrução sem mudança, exceto quando ela o
    # redefine. Outras arestas ainda podem unir os dois pontos em um laço.
    for index, instruction in enumerate(instructions):
        definitions = ir.defs(instruction)
        for value in points.before[index] & (points.after[index] - definitions):
            union((index, "before", value), (index, "after", value))

    # Continuação sequencial dentro de cada bloco.
    for block in cfg.blocks.values():
        for index in range(block.start, block.stop - 1):
            for value in points.after[index] & points.before[index + 1]:
                union((index, "after", value), (index + 1, "before", value))

    # Continuação entre blocos, incluindo arestas de laço e junções.
    for block in cfg.blocks.values():
        last = block.stop - 1
        for successor in block.successors:
            first = cfg.blocks[successor].start
            for value in points.after[last] & points.before[first]:
                union((last, "after", value), (first, "before", value))

    owner = cfg.function.function
    first_id = max_id + 1

    components = {}
    result = {}
    for key in parent:
        root = find(key)
        if root not in components:
            components[root] = ir.VReg(owner, first_id)
            first_id += 1
        result[key] = components[root]
    return result
