"""Coloração de grafo por simplificação e seleção reversa."""

from backend_api import REGISTERS


def allocate(graph, registers=REGISTERS, *, trace=None):
    pool = tuple(registers)
    residual = {vertex: set(neighbors) for vertex, neighbors in graph.items()}
    stack = []
    k = len(pool)

    while residual:
        low_degree = next(
            (vertex for vertex, neighbors in residual.items()
             if len(neighbors) < k),
            None,
        )
        potential_spill = low_degree is None
        vertex = low_degree if low_degree is not None else next(iter(residual))
        if trace is not None:
            trace.append((vertex, potential_spill))
        stack.append(vertex)
        for neighbor in residual[vertex]:
            residual[neighbor].discard(vertex)
        del residual[vertex]

    allocation = {}
    for vertex in reversed(stack):
        unavailable = {allocation[neighbor] for neighbor in graph[vertex]
                       if neighbor in allocation and allocation[neighbor] is not None}
        color = next((register for register in pool if register not in unavailable), None)
        allocation[vertex] = color
    return allocation
