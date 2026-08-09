import random
import time
from dataclasses import dataclass
from . import ast
from .errors import (StoopidError, error, ReturnSignal, BreakSignal,
                     ContinueSignal)


@dataclass
class Cell:
    type: str
    value: object
    ownership: str = "owned"
    mutable: bool = True
    nullable: bool = False
    moved: bool = False


@dataclass
class Pointer:
    target: object = None
    heap: object = None
    approved: bool = False
    freed: bool = False


@dataclass
class ResultValue:
    value: object = None
    message: str = ""
    inspected: bool = False


class Scope:
    def __init__(self, parent=None): self.parent, self.values = parent, {}
    def declare(self, name, cell): self.values[name] = cell
    def get(self, name):
        if name in self.values: return self.values[name]
        if self.parent: return self.parent.get(name)
        raise error("S017", f"Variable '{name}' does not exist.")


class Interpreter:
    def __init__(self, stdin=input, stdout=print):
        self.stdin, self.stdout = stdin, stdout
        self.global_scope = Scope(); self.scope = self.global_scope
        self.functions = {}; self.warnings = []; self.depth = 0; self.current_effects = set()

    def run(self, program, call_main=True):
        for fn in program.functions:
            if fn.name in self.functions: raise error("S014", f"Function '{fn.name}' was defined twice.")
            if not fn.normal and not self._has_approval(fn.body):
                raise error("S015", f"Function '{fn.name}' lacks approval().")
            self.functions[fn.name] = fn
        for stmt in program.statements: self.execute(stmt)
        result = self.call("main", []) if call_main and "main" in self.functions else None
        self.warnings.append(("S104", "Program completed successfully."))
        return result

    def _has_approval(self, node):
        if isinstance(node, ast.ExprStmt) and isinstance(node.expr, ast.Call) and node.expr.name == "approval": return True
        if isinstance(node, ast.Block): return any(self._has_approval(s) for s in node.statements)
        if isinstance(node, ast.If): return self._has_approval(node.then) or (node.otherwise is not None and self._has_approval(node.otherwise))
        return False

    def execute(self, node):
        if isinstance(node, ast.Block):
            old = self.scope; self.scope = Scope(old)
            try:
                try:
                    for stmt in node.statements: self.execute(stmt)
                except (ReturnSignal, BreakSignal, ContinueSignal):
                    self._check_results(self.scope)
                    raise
                else: self._check_results(self.scope)
            finally:
                self.scope = old
        elif isinstance(node, ast.VarDecl):
            if node.size is not None:
                size = self.eval(node.size)
                if not isinstance(size, int) or size < 0: raise error("A002", "Array size must be a non-negative integer.")
                if not isinstance(node.value, ast.Uninitialized): raise error("S051", "Array declarations must use the 'uninitialized' initializer.")
                value = [UNINITIALIZED] * (size + 1)
            else:
                if isinstance(node.value, ast.Uninitialized): raise error("S052", "Only arrays may use the 'uninitialized' initializer.")
                value = self.eval(node.value)
            value = self.coerce(node.type, value, node.pointer, exact=True)
            if value is None and not node.nullable: raise error("S053", f"Non-null variable '{node.name}' cannot contain null.")
            self.scope.declare(node.name, Cell(node.type + ("*" if node.pointer else ""), value, node.ownership, node.mutable, node.nullable))
            if node.pointer: self.warnings.append(("S102", f"Pointer '{node.name}' was declared."))
        elif isinstance(node, ast.ExprStmt): self.eval(node.expr)
        elif isinstance(node, ast.If):
            branch = node.then if self.truth(self.eval(node.condition)) else node.otherwise
            if branch is not None: self.execute(branch)
        elif isinstance(node, ast.While): self._loop(node.condition, None, node.body, node.limit)
        elif isinstance(node, ast.For):
            old = self.scope; self.scope = Scope(old)
            try:
                if node.init: self.execute(node.init)
                self._loop(node.condition, node.step, node.body, node.limit)
            finally: self.scope = old
        elif isinstance(node, ast.Return):
            value = self.eval(node.value) if node.value else None
            if self.value_type(value) != node.asserted_type: raise error("S054", f"Return assertion says {node.asserted_type}, value is {self.value_type(value)}.")
            raise ReturnSignal(value)
        elif isinstance(node, ast.Break): raise BreakSignal()
        elif isinstance(node, ast.Continue): raise ContinueSignal()

    def _loop(self, condition, step, body, limit):
        count = 0
        while self.truth(self.eval(condition)):
            try: self.execute(body)
            except ContinueSignal: pass
            except BreakSignal: break
            if step: self.eval(step)
            count += 1
            if count > limit: raise error("S105", f"Loop exceeded its declared limit of {limit} iterations.")
        self.warnings.append(("S103", "Loop terminated."))

    def _check_results(self, scope):
        for name, cell in scope.values.items():
            if isinstance(cell.value, ResultValue) and not cell.value.inspected:
                raise error("S072", f"Result variable '{name}' left scope without inspection.")

    def eval(self, node):
        if node is None: return None
        if isinstance(node, ast.Literal): return CharValue(node.value) if node.declared_type == "char" else node.value
        if isinstance(node, ast.Variable):
            cell = self.scope.get(node.name)
            if cell.moved: raise error("S055", f"Variable '{node.name}' was moved and cannot be used.")
            return cell.value
        if isinstance(node, ast.Uninitialized): return UNINITIALIZED
        if isinstance(node, ast.TypeAssert):
            value = self.eval(node.value); actual = self.value_type(value)
            if actual != node.type: raise error("S056", f"Type assertion requires {node.type}, got {actual}.")
            return value
        if isinstance(node, ast.Index): return self._index(node)
        if isinstance(node, ast.Unary):
            if node.op == "&": return Pointer(target=self.lvalue(node.value))
            if node.op == "*": return self._deref(self.eval(node.value)).value
            value = self.eval(node.value)
            if node.op in ("!", "!?!"): return not self.truth(value)
            if node.op == "-": return -value
            if node.op == "+": return +value
        if isinstance(node, ast.Binary): return self.binary(node)
        if isinstance(node, ast.Assign):
            cell = self.lvalue(node.target)
            if not cell.mutable: raise error("S057", "Cannot mutate a readonly value.")
            value = self.eval(node.value)
            cell.value = self.coerce(cell.type.rstrip("*"), value, cell.type.endswith("*"), exact=True); return cell.value
        if isinstance(node, ast.Postfix):
            cell = self.lvalue(node.target); old = cell.value; cell.value += 1 if node.op == "++" else -1; return old
        if isinstance(node, ast.Call):
            values = [None] * len(node.args)
            modes = [None] * len(node.args)
            for i in range(len(node.args) - 1, -1, -1):
                arg = node.args[i]; value = self.eval(arg.value)
                if self.value_type(value) != arg.asserted_type: raise error("S058", f"Argument assertion requires {arg.asserted_type}, got {self.value_type(value)}.")
                if arg.mode == "move":
                    if not isinstance(arg.value, ast.Variable): raise error("S059", "Only named variables can be moved.")
                    cell = self.scope.get(arg.value.name)
                    if cell.ownership != "owned": raise error("S060", f"Borrowed variable '{arg.value.name}' cannot be moved.")
                    cell.moved = True
                values[i], modes[i] = value, arg.mode
            return self.call(node.name, values, modes)
        raise error("S999", f"Cannot evaluate AST node {type(node).__name__}.")

    def lvalue(self, node):
        if isinstance(node, ast.Variable):
            cell = self.scope.get(node.name)
            if cell.moved: raise error("S055", f"Variable '{node.name}' was moved and cannot be used.")
            return cell
        if isinstance(node, ast.Index): return self._index(node, True)
        if isinstance(node, ast.Unary) and node.op == "*": return self._deref(self.eval(node.value))
        raise error("S018", "Assignment target is not assignable.")

    def _index(self, node, as_cell=False):
        value, idx = self.eval(node.value), self.eval(node.index)
        if not isinstance(idx, int): raise error("A003", "Index must be an integer.")
        if idx == 0: raise error("A001", "Index 0 is invalid; indexes begin at 1.")
        if idx < 1: raise error("A004", "Negative indexes are invalid.")
        if isinstance(value, str):
            if idx > len(value): raise error("A005", "String index is out of bounds.")
            if as_cell: raise error("S019", "Strings cannot be modified by index.")
            return CharValue(value[idx - 1])
        if isinstance(value, list):
            if idx >= len(value): raise error("A005", "Array index is out of bounds.")
            mutable = True
            typ = "int"
            if isinstance(node.value, ast.Variable):
                owner = self.scope.get(node.value.name); mutable = owner.mutable; typ = owner.type
            if value[idx] is UNINITIALIZED and not as_cell: raise error("A007", f"Array index {idx} has not been initialized.")
            return ArrayCell(value, idx, typ, mutable) if as_cell else value[idx]
        raise error("A006", "Value cannot be indexed.")

    def _deref(self, ptr):
        if not isinstance(ptr, Pointer) or ptr.freed: raise error("S069", "Invalid pointer operation.")
        if ptr.target: return ptr.target
        if ptr.heap is not None: return ArrayCell(ptr.heap, 1)
        raise error("S069", "Null pointer dereference.")

    def binary(self, node):
        left = self.eval(node.left)
        if node.op == "&&": return self.truth(left) and self.truth(self.eval(node.right))
        if node.op == "||": return self.truth(left) or self.truth(self.eval(node.right))
        right = self.eval(node.right); op = node.op
        if op in ("/", "%", "%%") and right == 0: raise error("S042", "Division by zero.")
        try:
            return {"+": lambda: left + right, "-": lambda: left - right, "*": lambda: left * right,
                    "/": lambda: left / right, "%": lambda: left % right,
                    "%%": lambda: abs(int(left)) % abs(int(right)), "==": lambda: left == right,
                    "!=": lambda: left != right, "<": lambda: left < right, "<=": lambda: left <= right,
                    ">": lambda: left > right, ">=": lambda: left >= right,
                    "><": lambda: left > right, "???": lambda: left == right or str(left) == str(right)}[op]()
        except (TypeError, ValueError): raise error("S020", f"Operator '{op}' does not support these operands.")

    BUILTIN_EFFECTS = {"print": "io", "println": "io", "input": "io", "malloc": "heap", "please_free": "heap", "free": "heap", "sleep": "time", "random": "random"}
    def call(self, name, args, modes=None):
        required = self.BUILTIN_EFFECTS.get(name)
        if required and self.depth and required not in self.current_effects: raise error("S061", f"Function effect '{required}' is required to call '{name}'.")
        builtin = getattr(self, "builtin_" + name, None)
        if builtin: return builtin(*args)
        if name not in self.functions: raise error("S404", f"Function '{name}' not found.")
        fn = self.functions[name]
        if len(args) != len(fn.params): raise error("S021", f"Function '{name}' expects {len(fn.params)} arguments, got {len(args)}.")
        if self.depth >= 64: raise error("S064", "Recursion limit of 64 reached.")
        caller_effects = self.current_effects
        missing = set(fn.effects) - caller_effects if self.depth else set()
        if missing: raise error("S062", f"Caller lacks effects required by '{name}': {', '.join(sorted(missing))}.")
        old = self.scope; self.scope = Scope(self.global_scope); self.depth += 1; self.current_effects = set(fn.effects)
        modes = modes or ["lend"] * len(args)
        for (typ, pname, pointer, ownership, mutable, nullable), value, mode in zip(fn.params, args, modes):
            required_mode = "move" if ownership == "owned" else "lend"
            if mode != required_mode: raise error("S063", f"Parameter '{pname}' requires argument mode '{required_mode}'.")
            self.scope.declare(pname, Cell(typ + ("*" if pointer else ""), self.coerce(typ, value, pointer, exact=True), ownership, mutable, nullable))
        try:
            try: self.execute(fn.body); result = None
            except ReturnSignal as signal: result = signal.value
            return self.coerce(fn.return_type, result) if fn.return_type != "void" else None
        finally: self.scope, self.depth, self.current_effects = old, self.depth - 1, caller_effects

    def default(self, typ): return {"int": 0, "float": 0.0, "char": "\0", "bool": False, "string": "", "void": None}[typ]
    def value_type(self, value):
        if value is None: return "void"
        if isinstance(value, bool) or value in ("probably", "idk"): return "bool"
        if isinstance(value, int): return "int"
        if isinstance(value, float): return "float"
        if isinstance(value, CharValue): return "char"
        if isinstance(value, str): return "string"
        if isinstance(value, Pointer): return "pointer"
        if isinstance(value, ResultValue): return "result"
        if isinstance(value, list): return "array"
        return type(value).__name__
    def coerce(self, typ, value, pointer=False, exact=False):
        if pointer:
            if isinstance(value, Pointer): return value
            raise error("S069", f"Cannot put {type(value).__name__} in a pointer.")
        if isinstance(value, list): return value
        if exact and self.value_type(value) != typ: raise error("S022", f"Expected exact type {typ}, got {self.value_type(value)}.")
        try:
            if typ == "int": return int(value)
            if typ == "float": return float(value)
            if typ == "string": return str(value)
            if typ == "char":
                if not isinstance(value, str) or len(value) != 1: raise ValueError()
                return value
            if typ == "bool": return value if value in (True, False, "probably", "idk") else self.truth(value)
            if typ == "result": return value
            return value
        except (TypeError, ValueError): raise error("S022", f"Cannot convert value to {typ}.")
    def truth(self, value): return value is True or value == "probably" or (isinstance(value, (int, float)) and value != 0) or (isinstance(value, str) and value not in ("", "idk"))
    def display(self, value):
        if value is True: return "true"
        if value is False: return "false"
        if isinstance(value, float): return f"{value:.6f}"
        if value is None: return "void"
        return str(value)

    def builtin_print(self, *args): self.stdout(" ".join(self.display(a) for a in args), end="")
    def builtin_println(self, *args): self.stdout(" ".join(self.display(a) for a in args))
    def builtin_input(self, prompt=""):
        try: return ResultValue(value=self.stdin(str(prompt)))
        except EOFError: return ResultValue(message="Input ended before a value arrived.")
    def builtin_length(self, value): return len(value) - 1 if isinstance(value, list) else len(value)
    def builtin_substring(self, value, start, end):
        if start == 0 or end == 0: raise error("A001", "String positions begin at 1.")
        return value[start - 1:end]
    def builtin_concat(self, a, b): return str(a) + str(b)
    def builtin_atoi(self, value):
        try: return ResultValue(value=int(value))
        except (TypeError, ValueError): return ResultValue(message=f"atoi cannot convert {value!r} to an integer.")
    def builtin_inspect(self, result):
        if not isinstance(result, ResultValue): raise error("S073", "inspect expects a result value.")
        result.inspected = True
        return result.message == ""
    def builtin_unwrap(self, result):
        if not isinstance(result, ResultValue): raise error("S074", "unwrap expects a result value.")
        if not result.inspected: raise error("S075", "A result must be inspected before it is unwrapped.")
        if result.message: raise error("S076", result.message)
        return result.value
    def builtin_sizeof(self, value): return len(value.encode("utf8")) + 7 if isinstance(value, str) else 8
    def builtin_random(self, low=0, high=100): return random.randint(int(low), int(high))
    def builtin_sleep(self, ms): time.sleep(float(ms) / 1000.0)
    def builtin_approval(self): return None
    def builtin_malloc(self, size):
        size = int(size)
        if size < 1: raise error("S070", "malloc size must be positive.")
        return Pointer(heap=[None] + [0] * size)
    def builtin_please_free(self, ptr):
        if not isinstance(ptr, Pointer) or ptr.freed: raise error("S069", "Cannot approve this pointer for freeing.")
        ptr.approved = True
    def builtin_free(self, ptr):
        if not isinstance(ptr, Pointer) or ptr.freed: raise error("S069", "Invalid free operation.")
        if not ptr.approved: raise error("S071", "free() requires please_free(ptr) first.")
        ptr.freed, ptr.heap, ptr.target = True, None, None


UNINITIALIZED = object()


class CharValue(str): pass


class ArrayCell:
    def __init__(self, data, index, typ="int", mutable=True): self.data, self.index, self.type, self.mutable = data, index, typ, mutable
    @property
    def value(self): return self.data[self.index]
    @value.setter
    def value(self, value): self.data[self.index] = value
