from . import ast
from .errors import error


class Checker:
    def __init__(self): self.scopes = [set()]; self.loop_depth = 0; self.function = None; self.labels = set()
    def check(self, program):
        names = set()
        for fn in program.functions:
            if fn.name in names: raise error("S014", f"Function '{fn.name}' was defined twice.")
            names.add(fn.name); self.function = fn; self.labels = set(); self.scopes.append(set())
            if len(fn.effects) != len(set(fn.effects)): raise error("S077", f"Function '{fn.name}' repeats an effect.")
            for typ, name, *_ in fn.params:
                if name in self.scopes[-1]: raise error("S031", f"Duplicate parameter '{name}'.")
                self.scopes[-1].add(name)
            self.visit(fn.body); self.scopes.pop(); self.function = None
        for stmt in program.statements: self.visit(stmt)
        return program

    def visit(self, node):
        if isinstance(node, ast.Block):
            self.scopes.append(set())
            for item in node.statements: self.visit(item)
            self.scopes.pop()
        elif isinstance(node, ast.VarDecl):
            if node.type == "void": raise error("S032", f"Variable '{node.name}' cannot be void.")
            if node.name in self.scopes[-1]: raise error("S033", f"Variable '{node.name}' is already declared in this scope.")
            self.scopes[-1].add(node.name)
        elif isinstance(node, (ast.While, ast.For)):
            self._label(node.label)
            self.loop_depth += 1
            if isinstance(node, ast.For) and node.init: self.visit(node.init)
            self.visit(node.body); self.loop_depth -= 1
        elif isinstance(node, ast.If):
            self._label(node.label)
            self.visit(node.then)
            if node.otherwise: self.visit(node.otherwise)
        elif isinstance(node, (ast.Break, ast.Continue)) and not self.loop_depth:
            raise error("S034", f"{type(node).__name__.lower()} used outside a loop.")
        elif isinstance(node, ast.Return) and self.function is None:
            raise error("S035", "return used outside a function.")

    def _label(self, label):
        if label in self.labels: raise error("S078", f"Control-flow label '{label}' is already used in this function.")
        self.labels.add(label)


def check(program): return Checker().check(program)
