"""Construa o grafo de interferência entre live ranges."""

import ir

def build_interference(cfg, points, ranges):
    graph = {live_range: set() for live_range in ranges.values()}

    def connect(left, right):
        if left != right:
            graph[left].add(right)
            graph[right].add(left)

    # Valores vivos no começo do bloco de entrada precisam de cores distintas.
    if cfg.entry is not None:
        entry_index = cfg.blocks[cfg.entry].start
        incoming = [ranges[entry_index, "before", value]
                    for value in points.before[entry_index]]
        for position, left in enumerate(incoming):
            for right in incoming[position + 1:]:
                connect(left, right)

    for index, instruction in enumerate(cfg.function.instructions):
        definitions = ir.defs(instruction)
        if not definitions:
            continue
        live_after = [ranges[index, "after", value]
                      for value in points.after[index]]
        for defined in definitions:
            output_range = ranges[index, "after", defined]
            excluded = None
            if isinstance(instruction, ir.Move):
                excluded = ranges.get((index, "before", instruction.src))
            for other in live_after:
                if other != excluded:
                    connect(output_range, other)

    return graph
