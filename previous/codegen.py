"""Geração da AST validada, com reconstrução das coberturas escolhidas por DP."""

import load_previous
import ast_nodes as A
import ir as I
from catalogue import catalogue
from patterns import REG, COND, EFFECT, signed_literal
from selector import Selector


class CodeGenerator:
    """Traduza comandos diretamente e expressões somente pela seleção."""

    def __init__(self):
        self.selector = Selector(catalogue())
        self.program = None
        self.context = None

    def generate(self, program):
        """Crie uma IR independente, sem modificar a AST ou repetir o frontend."""
        self.program = I.ProgramIR()
        self.context = None
        try:
            for function in program.functions:
                symbol = function.metadata["symbol"]
                function_ir = I.FunctionIR(symbol)
                self.program.functions.append(function_ir)
                self.context = I.Context(function_ir, self.program)
                for index, parameter in enumerate(function.parameters):
                    dst = self.context.variable(parameter.metadata["symbol"])
                    self.context.emit(I.Param(dst, index, origin=parameter.span))
                self.statement(function.body)
                if function.return_type is A.TypeName.VOID:
                    self.context.emit(I.Return(None, origin=function.span))
            return self.program
        finally:
            self.context = None

    @staticmethod
    def _error(node, message):
        span = node.span
        return ValueError(f"{message} em {span.start_line}:{span.start_column}")

    def expression(self, node, result_class, true_label=None, false_label=None):
        """Analise uma vez a raiz; reconstrua somente as escolhas necessárias."""
        table = self.selector.analyze(node)
        return self._reconstruct(node, result_class, table, true_label, false_label)

    def _reconstruct(self, node, result_class, table, true_label=None, false_label=None):
        choice = table.lookup(node, result_class)
        if choice is None:
            raise self._error(node, f"sem cobertura para {result_class.value}")
        if self.context is None:
            raise self._error(node, "expressão sem contexto de função")
        if result_class is COND and (true_label is None or false_label is None):
            raise self._error(node, "COND exige destinos verdadeiro e falso")
        ctx = self.context
        action = choice.rule.action

        def emit(instruction, *operands):
            ctx.emit(instruction(*operands, origin=node.span))

        def child(index, target_true=None, target_false=None):
            subnode, subkind = choice.subproblems[index]
            return self._reconstruct(subnode, subkind, table, target_true, target_false)

        # A emissão de condições dirige a reconstrução dos filhos. Não antecipar
        # todos os subproblemas: isso executaria o RHS lógico incondicionalmente.
        if action == "boolean_condition":
            emit(I.Jump, true_label if node.value else false_label)
            return None
        if action == "not_condition":
            child(0, false_label, true_label)
            return None
        if action in ("logical_condition", "logical_value"):
            if action == "logical_value":
                dst = ctx.temp()
                true_label, false_label, join = ctx.label(), ctx.label(), ctx.label()
            middle = ctx.label()
            if node.operator is A.BinaryOperator.LOGICAL_AND:
                child(0, middle, false_label)
            else:
                child(0, true_label, middle)
            ctx.emit(I.LabelInstr(middle))
            child(1, true_label, false_label)
            if action == "logical_value":
                ctx.emit(I.LabelInstr(true_label))
                emit(I.Li, dst, 1)
                emit(I.Jump, join)
                ctx.emit(I.LabelInstr(false_label))
                emit(I.Li, dst, 0)
                ctx.emit(I.LabelInstr(join))
                return dst
            return None

        # As demais ações são estritas: subproblemas em ordem dos Need/Args.
        operands = [child(index) for index in range(len(choice.subproblems))]
        if action == "variable":
            return ctx.variable(node.metadata["symbol"])
        if action == "immediate":
            return signed_literal(node)
        if action == "power":
            return signed_literal(node).bit_length() - 1
        if action == "variable_condition":
            emit(I.Bnez, ctx.variable(node.metadata["symbol"]), true_label)
            emit(I.Jump, false_label)
            return None
        if action in ("call_value", "call_effect", "call_condition"):
            dst = None if action == "call_effect" else ctx.temp()
            emit(I.Call, dst, node.metadata["symbol"], operands)
            if action == "call_condition":
                emit(I.Bnez, dst, true_label)
                emit(I.Jump, false_label)
                return None
            return dst
        if action == "comparison_condition":
            lhs, rhs = operands
            operator = node.operator
            if operator in (A.BinaryOperator.GREATER, A.BinaryOperator.LESS_EQUAL):
                lhs, rhs = rhs, lhs
            instruction = {
                A.BinaryOperator.LESS: I.Blt,
                A.BinaryOperator.GREATER: I.Blt,
                A.BinaryOperator.LESS_EQUAL: I.Bge,
                A.BinaryOperator.GREATER_EQUAL: I.Bge,
                A.BinaryOperator.EQUAL: I.Beq,
                A.BinaryOperator.NOT_EQUAL: I.Bne,
            }[operator]
            emit(instruction, lhs, rhs, true_label)
            emit(I.Jump, false_label)
            return None

        dst = ctx.temp()
        if action == "literal":
            emit(I.Li, dst, signed_literal(node))
        elif action == "boolean":
            emit(I.Li, dst, int(node.value))
        elif action in ("negate", "not_value"):
            emit(I.Neg if action == "negate" else I.Seqz, dst, operands[0])
        elif action == "arithmetic":
            instruction = {
                A.BinaryOperator.ADD: I.Add,
                A.BinaryOperator.SUBTRACT: I.Sub,
                A.BinaryOperator.MULTIPLY: I.Mul,
                A.BinaryOperator.DIVIDE: I.Div,
                A.BinaryOperator.REMAINDER: I.Rem,
            }[node.operator]
            emit(instruction, dst, *operands)
        elif action in ("add_right", "add_left", "shift_right", "shift_left"):
            src, immediate = operands if action.endswith("right") else operands[::-1]
            emit(I.Addi if action.startswith("add") else I.Slli, dst, src, immediate)
        elif action == "sub_immediate":
            emit(I.Addi, dst, operands[0], -signed_literal(node.right))
        elif action == "comparison_value":
            lhs, rhs = operands
            operator = node.operator
            if operator in (A.BinaryOperator.GREATER, A.BinaryOperator.LESS_EQUAL):
                lhs, rhs = rhs, lhs
            equality = operator in (A.BinaryOperator.EQUAL, A.BinaryOperator.NOT_EQUAL)
            emit(I.Xor if equality else I.Slt, dst, lhs, rhs)
            if operator in (A.BinaryOperator.LESS_EQUAL, A.BinaryOperator.GREATER_EQUAL,
                            A.BinaryOperator.EQUAL):
                emit(I.Seqz, dst, dst)
            elif operator is A.BinaryOperator.NOT_EQUAL:
                emit(I.Snez, dst, dst)
        else:
            raise self._error(node, f"ação desconhecida: {action}")
        return dst

    def statement(self, node):
        """Traduza comandos na ordem da fonte e mantenha labels locais."""
        ctx = self.context
        if ctx is None:
            raise self._error(node, "comando sem contexto de função")
        if isinstance(node, A.Block):
            for statement in node.statements:
                self.statement(statement)
        elif isinstance(node, A.VarDecl):
            if node.initializer is not None:
                value = self.expression(node.initializer, REG)
                ctx.emit(I.Move(ctx.variable(node.metadata["symbol"]), value, origin=node.span))
        elif isinstance(node, A.Assignment):
            value = self.expression(node.value, REG)
            ctx.emit(I.Move(ctx.variable(node.target.metadata["symbol"]), value, origin=node.span))
        elif isinstance(node, A.CallStmt):
            self.expression(node.call, EFFECT)
        elif isinstance(node, A.ReturnStmt):
            value = None if node.value is None else self.expression(node.value, REG)
            ctx.emit(I.Return(value, origin=node.span))
        elif isinstance(node, A.IfStmt):
            then_label, join = ctx.label(), ctx.label()
            else_label = join if node.else_block is None else ctx.label()
            self.expression(node.condition, COND, then_label, else_label)
            ctx.emit(I.LabelInstr(then_label))
            self.statement(node.then_block)
            if node.else_block is not None:
                ctx.emit(I.Jump(join, origin=node.span))
                ctx.emit(I.LabelInstr(else_label))
                self.statement(node.else_block)
            ctx.emit(I.LabelInstr(join))
        elif isinstance(node, A.WhileStmt):
            head, body, end = ctx.label(), ctx.label(), ctx.label()
            ctx.emit(I.LabelInstr(head))
            self.expression(node.condition, COND, body, end)
            ctx.emit(I.LabelInstr(body))
            self.statement(node.body)
            ctx.emit(I.Jump(head, origin=node.span))
            ctx.emit(I.LabelInstr(end))
        elif isinstance(node, A.PrintStmt):
            for item in node.items:
                if isinstance(item, A.StringLiteral):
                    ctx.emit(I.PrintString(ctx.string(item.value), origin=item.span))
                else:
                    value = self.expression(item, REG)
                    instruction = (I.PrintBool if item.metadata["type"] is A.TypeName.BOOL
                                   else I.PrintInt)
                    ctx.emit(instruction(value, origin=item.span))
            ctx.emit(I.PrintString(ctx.string("\n"), origin=node.span))
        else:
            raise self._error(node, f"comando desconhecido: {type(node).__name__}")
