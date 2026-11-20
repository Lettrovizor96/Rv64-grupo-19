"""Catálogo obrigatório da etapa 6, com custos próprios e ações de emissão."""

import load_previous
from ast_nodes import (
    BinaryExpr, BinaryOperator as B, BoolLiteral, CallExpr, IdentifierExpr,
    TypeName, UnaryExpr, UnaryOperator as U,
)
from patterns import (
    Args, COND, EFFECT, IMM12, POW2, REG, Need, Pattern, Rule,
    imm12, neg_imm12, pow2, signed_literal,
)


def _signed(node):
    return signed_literal(node) is not None


def _boolean(node):
    return node.metadata.get("type") is TypeName.BOOL


def _value_call(node):
    return node.metadata.get("type") in (TypeName.INT, TypeName.BOOL)


def catalogue():
    """Codifique o catálogo do enunciado com Rule e Pattern."""
    rules = [
        Rule("literal", REG, Pattern(predicate=_signed), 1, "literal"),
        Rule("boolean", REG, Pattern(BoolLiteral), 1, "boolean"),
        Rule("variable", REG, Pattern(IdentifierExpr), 0, "variable"),
        Rule("immediate", IMM12, Pattern(predicate=imm12), 0, "immediate"),
        Rule("power", POW2, Pattern(predicate=pow2), 0, "power"),
        Rule("negate", REG, Pattern(UnaryExpr, U.NEGATE, (Need(REG),)), 1, "negate"),
    ]
    for operator in (B.ADD, B.SUBTRACT, B.MULTIPLY, B.DIVIDE, B.REMAINDER):
        rules.append(Rule(
            "arithmetic_" + operator.name.lower(), REG,
            Pattern(BinaryExpr, operator, (Need(REG), Need(REG))), 1, "arithmetic",
        ))
    for operator, auxiliary, right, left in (
        (B.ADD, IMM12, "add_right", "add_left"),
        (B.MULTIPLY, POW2, "shift_right", "shift_left"),
    ):
        rules.extend([
            Rule(right, REG, Pattern(BinaryExpr, operator, (Need(REG), Need(auxiliary))), 1, right),
            Rule(left, REG, Pattern(BinaryExpr, operator, (Need(auxiliary), Need(REG))), 1, left),
        ])
    rules.append(Rule(
        "sub_immediate", REG,
        Pattern(BinaryExpr, B.SUBTRACT, (Need(REG), Pattern(predicate=neg_imm12))),
        1, "sub_immediate",
    ))
    for operator in (B.LESS, B.GREATER, B.LESS_EQUAL, B.GREATER_EQUAL, B.EQUAL, B.NOT_EQUAL):
        pattern = Pattern(BinaryExpr, operator, (Need(REG), Need(REG)))
        cost = 1 if operator in (B.LESS, B.GREATER) else 2
        rules.extend([
            Rule("value_" + operator.name.lower(), REG, pattern, cost, "comparison_value"),
            Rule("condition_" + operator.name.lower(), COND, pattern, 2, "comparison_condition"),
        ])
    rules.extend([
        Rule("not_value", REG, Pattern(UnaryExpr, U.NOT, (Need(REG),)), 1, "not_value"),
        Rule("not_condition", COND, Pattern(UnaryExpr, U.NOT, (Need(COND),)), 0, "not_condition"),
    ])
    for operator in (B.LOGICAL_AND, B.LOGICAL_OR):
        pattern = Pattern(BinaryExpr, operator, (Need(COND), Need(COND)))
        rules.extend([
            Rule("value_" + operator.name.lower(), REG, pattern, 3, "logical_value"),
            Rule("condition_" + operator.name.lower(), COND, pattern, 0, "logical_condition"),
        ])
    rules.extend([
        Rule("boolean_condition", COND, Pattern(BoolLiteral), 1, "boolean_condition"),
        Rule("variable_condition", COND, Pattern(IdentifierExpr, predicate=_boolean), 2, "variable_condition"),
        Rule("call_value", REG, Pattern(CallExpr, children=(Args(REG),), predicate=_value_call), 1, "call_value"),
        Rule("call_effect", EFFECT, Pattern(CallExpr, children=(Args(REG),)), 1, "call_effect"),
        Rule("call_condition", COND, Pattern(CallExpr, children=(Args(REG),), predicate=_boolean), 3, "call_condition"),
    ])
    return rules
