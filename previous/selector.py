"""Matching de árvores e programação dinâmica por nó e classe de resultado."""

import load_previous
from ast_nodes import CallExpr
from patterns import Args, Choice, Need, Pattern, SelectionTable, children


class Selector:
    """Selecione coberturas sem executar expressões ou emitir instruções."""

    def __init__(self, rules):
        self.rules = tuple(rules)

    def analyze(self, expr):
        """Calcule mínimos por nó/classe sem emitir instruções."""
        table = SelectionTable()

        def visit(node):
            for child in children(node):
                visit(child)
            for rule in self.rules:
                required = self._match(rule.pattern, node, table)
                if required is None:
                    continue
                cost = rule.cost + sum(
                    table.lookup(child, result).cost for child, result in required
                )
                previous = table.lookup(node, rule.result)
                if previous is None or cost < previous.cost:
                    table.put(node, rule.result, Choice(cost, rule, required))

        visit(expr)
        return table

    def _match(self, pattern, node, table):
        """Devolva subproblemas ordenados, ou None quando não houver cobertura."""
        if isinstance(pattern, Need):
            if table.lookup(node, pattern.result) is None:
                return None
            return ((node, pattern.result),)
        if not isinstance(pattern, Pattern):
            return None
        if pattern.kind is not None and not isinstance(node, pattern.kind):
            return None
        if pattern.operator is not None and getattr(node, "operator", None) != pattern.operator:
            return None
        if pattern.predicate is not None:
            if not pattern.predicate(node):
                return None
            if not pattern.children:
                return ()

        actual = children(node)
        expected = pattern.children
        if len(expected) == 1 and isinstance(expected[0], Args):
            if not isinstance(node, CallExpr):
                return None
            expected = (Need(expected[0].result),) * len(actual)
        if len(expected) != len(actual):
            return None
        required = []
        for subpattern, child in zip(expected, actual):
            match = self._match(subpattern, child, table)
            if match is None:
                return None
            required.extend(match)
        return tuple(required)
