"""Run server-owned cases against a bounded subset of Python collection code."""

import ast
from copy import deepcopy
from dataclasses import dataclass
import re
from textwrap import dedent

from .models import Judgment, Mode, Observation, Turn


_FUNCTION = "deduplicate_events"
_FENCE = re.compile(r"^```(?:python|py)?[ \t]*\n(.*?)^```[ \t]*$", re.I | re.M | re.S)
_STARTER = re.compile(r"\b(?:viết|triển khai|write|implement)\b[^.!?\n]*\bdeduplicate_events\s*\(\s*events\s*\)")
_FIRST_RECORD = re.compile(r"(?:xuất hiện đầu tiên|giữ (?:lại )?bản ghi đầu tiên|first (?:occurrence|record|event))")
_ORIGINAL_ORDER = re.compile(r"(?:thứ tự (?:ban đầu|gốc|xuất hiện)|original order|insertion order|input order)")
_CASES = (
    ([], []),
    ([{"event_id": "B", "value": 10}, {"event_id": "A", "value": 20}], [0, 1]),
    ([{"event_id": "B", "value": 10}, {"event_id": "A", "value": 20},
      {"event_id": "B", "value": 30}, {"event_id": "C", "value": 40}, {"event_id": "A", "value": 50}], [0, 1, 3]),
)
_MAX_SOURCE = 4096
_MAX_AST_NODES = 160
_MAX_STEPS = 800
_BUILTINS = {"dict": dict, "list": list, "set": set}
_COLLECTION_METHODS = {
    list: {"append": list.append},
    set: {"add": set.add},
    dict: {"get": dict.get, "setdefault": dict.setdefault, "values": dict.values},
}


class _UnsupportedCode(Exception):
    pass


class _Return(Exception):
    def __init__(self, value: object):
        self.value = value


@dataclass(frozen=True)
class CodingCheck:
    line_range: tuple[int, int]
    total: int
    passed: int

    def failure_judgment(self, turn: Turn) -> Judgment:
        return Judgment(feedback="", observations=[Observation(
            criterion_id=turn.question.criterion_ids[0], response_line_range=self.line_range,
            observation="CONTRADICTS", performance="BELOW",
            rationale=(f"Hàm không đạt {self.total - self.passed}/{self.total} ca đối chứng. "
                       "Kết quả phải giữ bản ghi xuất hiện đầu tiên của mỗi event_id theo thứ tự đầu vào."),
        )])


def check_coding_answer(turn: Turn, interaction_mode: str) -> CodingCheck | None:
    """A mismatch can disprove correctness. No result means use the regular Judge."""
    text = turn.question.text.casefold()
    if (interaction_mode != "TEXT" or turn.mode != Mode.CODING or len(turn.question.criterion_ids) != 1
            or not re.search(r"\bevent_id\b", text) or not _STARTER.search(text)
            or not _FIRST_RECORD.search(text) or not _ORIGINAL_ORDER.search(text)):
        return None
    try:
        function, line_range = _function_from_answer(turn.answer or "")
        passed = sum(_run_case(function, rows) == [rows[index] for index in first] for rows, first in _CASES)
    except (_UnsupportedCode, SyntaxError, TypeError, ValueError, KeyError, IndexError, RecursionError):
        return None
    return CodingCheck(line_range, len(_CASES), passed)


def _function_from_answer(answer: str) -> tuple[ast.FunctionDef, tuple[int, int]]:
    if len(answer) > _MAX_SOURCE:
        raise _UnsupportedCode
    answer = answer.replace("\r\n", "\n").replace("\r", "\n")
    code, start = _code_block(answer)
    tree = ast.parse(dedent(code))
    if len(tree.body) != 1 or sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        raise _UnsupportedCode
    function = tree.body[0]
    if not isinstance(function, ast.FunctionDef) or function.name != _FUNCTION or function.decorator_list:
        raise _UnsupportedCode
    args = function.args
    if len(args.posonlyargs + args.args) != 1 or args.vararg or args.kwonlyargs or args.kwarg or args.defaults:
        raise _UnsupportedCode
    return function, (start + function.lineno, start + function.end_lineno)


def _code_block(answer: str) -> tuple[str, int]:
    blocks = list(_FENCE.finditer(answer))
    if len(blocks) == 1:
        return blocks[0][1], answer.count("\n", 0, blocks[0].start(1))
    if blocks:
        raise _UnsupportedCode
    # Plain-text interviews often put a short explanation after the submitted function.
    prose = re.search(r"(?m)^\s*\n(?:Em|Tôi|Mình|I|This) [^\n]+", answer)
    if prose and not re.search(r"(?m)^(?:def |```)", answer[prose.end():]):
        return answer[:prose.start()], 0
    return answer, 0


def _run_case(function: ast.FunctionDef, rows: list[dict]) -> object:
    parameter, = function.args.posonlyargs + function.args.args
    runner = _CollectionCode({parameter.arg: deepcopy(rows)})
    try:
        runner.block(function.body)
    except _Return as result:
        return result.value
    return None


class _CollectionCode:
    """Interpret local collection operations. Candidate AST never becomes Python bytecode."""

    def __init__(self, variables: dict[str, object], budget: list[int] | None = None):
        self.variables = variables
        self.budget = [_MAX_STEPS] if budget is None else budget

    def tick(self) -> None:
        self.budget[0] -= 1
        if self.budget[0] < 0:
            raise _UnsupportedCode

    def block(self, statements: list[ast.stmt]) -> None:
        for node in statements:
            self.tick()
            match node:
                case ast.Assign(targets=[target], value=value):
                    self.assign(target, self.expression(value))
                case ast.Return(value=value):
                    raise _Return(self.expression(value) if value is not None else None)
                case ast.Expr(value=value):
                    self.expression(value)
                case ast.If(test=test, body=body, orelse=other):
                    self.block(body if self.expression(test) else other)
                case ast.For(target=ast.Name(id=name), iter=source, body=body, orelse=[]):
                    for value in self.expression(source):
                        self.tick()
                        self.variables[name] = value
                        self.block(body)
                case _:
                    raise _UnsupportedCode

    def assign(self, target: ast.expr, value: object) -> None:
        match target:
            case ast.Name(id=name):
                self.variables[name] = value
            case ast.Subscript(value=owner, slice=key):
                collection = self.expression(owner)
                if type(collection) is not dict:
                    raise _UnsupportedCode
                collection[self.expression(key)] = value
            case _:
                raise _UnsupportedCode

    def expression(self, node: ast.expr) -> object:
        self.tick()
        match node:
            case ast.Name(id=name):
                return self.variables[name]
            case ast.Constant(value=value) if type(value) in {str, int, bool, type(None)}:
                return value
            case ast.List(elts=items):
                return [self.expression(item) for item in items]
            case ast.Dict(keys=[], values=[]):
                return {}
            case ast.Subscript(value=owner, slice=key):
                return self.expression(owner)[self.expression(key)]
            case ast.UnaryOp(op=ast.Not(), operand=value):
                return not self.expression(value)
            case ast.Compare(left=value, ops=[op], comparators=[other]):
                return self.compare(op, self.expression(value), self.expression(other))
            case ast.Call(keywords=[]):
                return self.call(node)
            case ast.DictComp(generators=[generator]):
                return self.dict_comprehension(node, generator)
            case _:
                raise _UnsupportedCode

    @staticmethod
    def compare(op: ast.cmpop, left: object, right: object) -> bool:
        match op:
            case ast.In():
                return left in right
            case ast.NotIn():
                return left not in right
            case ast.Eq():
                return left == right
            case _:
                raise _UnsupportedCode

    def call(self, node: ast.Call) -> object:
        match node.func:
            case ast.Name(id=name) if name not in self.variables and name in _BUILTINS:
                function = _BUILTINS[name]
                return function(*(self.expression(argument) for argument in node.args))
            case ast.Attribute(value=owner, attr=name):
                collection = self.expression(owner)
                method = _COLLECTION_METHODS.get(type(collection), {}).get(name)
                if method is not None:
                    return method(collection, *(self.expression(argument) for argument in node.args))
        raise _UnsupportedCode

    def dict_comprehension(self, node: ast.DictComp, generator: ast.comprehension) -> dict:
        if generator.is_async or not isinstance(generator.target, ast.Name):
            raise _UnsupportedCode
        scope = _CollectionCode(self.variables.copy(), self.budget)
        result = {}
        for value in self.expression(generator.iter):
            self.tick()
            scope.variables[generator.target.id] = value
            if all(scope.expression(condition) for condition in generator.ifs):
                key = scope.expression(node.key)
                result[key] = scope.expression(node.value)
        return result
