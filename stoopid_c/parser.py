from . import ast
from .errors import error

TYPES = {"int", "float", "char", "bool", "string", "void", "result"}


class Parser:
    def __init__(self, tokens): self.tokens, self.pos = tokens, 0
    @property
    def current(self): return self.tokens[self.pos]
    def at(self, *kinds): return self.current.kind in kinds
    def take(self): token = self.current; self.pos += 1; return token
    def match(self, *kinds):
        if self.at(*kinds): return self.take()
        return None
    def expect(self, kind, code="S006", message=None):
        if not self.at(kind):
            raise error("S001" if kind == ";" else code, message or f"Expected '{kind}'.", token=self.current)
        return self.take()

    def terminator(self):
        self.expect(";", message="Expected the first ';' in the mandatory ';;' terminator.")
        self.expect(";", message="Expected the second ';' in the mandatory ';;' terminator.")

    def parse(self):
        functions, statements = [], []
        while not self.at("EOF"):
            normal = False
            if self.match("@"):
                name = self.expect("IDENT")
                if name.value != "normal": raise error("S007", f"Unknown annotation @{name.value}.", token=name)
                normal = True
            if self.current.kind in TYPES and self._looks_like_function(): functions.append(self.function(normal))
            elif normal: raise error("S007", "@normal only applies to functions.", token=self.current)
            else: statements.append(self.statement())
        return ast.Program(functions, statements)

    def _looks_like_function(self):
        p = self.pos + 1
        if self.tokens[p].kind != self.current.kind: return False
        p += 1
        if self.tokens[p].kind == "*": p += 1
        return self.tokens[p].kind == "IDENT" and self.tokens[p + 1].kind == "("

    def function(self, normal=False):
        typ = self.take().kind; self.expect(typ, message=f"Function return type '{typ}' must be written twice."); self.match("*"); name = self.expect("IDENT")
        if "x" in name.value.lower(): raise error("S013", f"Function '{name.value}' contains the forbidden letter x.", token=name)
        self.expect("("); params = []
        if not self.at(")"):
            while True:
                ptype = self.take()
                if ptype.kind not in TYPES: raise error("S008", "Expected parameter type.", token=ptype)
                self.expect(ptype.kind, message=f"Parameter type '{ptype.kind}' must be written twice.")
                pointer = bool(self.match("*"))
                ownership = self.take()
                if ownership.kind not in ("owned", "borrowed"): raise error("S036", "Parameters require 'owned' or 'borrowed'.", token=ownership)
                mutability = self.take()
                if mutability.kind not in ("mutable", "readonly"): raise error("S037", "Parameters require 'mutable' or 'readonly'.", token=mutability)
                nullability = self.take()
                if nullability.kind not in ("nonnull", "nullable"): raise error("S038", "Parameters require 'nonnull' or 'nullable'.", token=nullability)
                pname = self.expect("IDENT")
                params.append((ptype.kind, pname.value, pointer, ownership.kind, mutability.kind == "mutable", nullability.kind == "nullable"))
                if not self.match(","): break
        self.expect(")"); self.expect("seriously", message="Expected 'seriously' after the function signature.")
        self.expect("effects", message="Every function requires an effects declaration."); self.expect("("); effects = []
        if self.match("none"): effects = []
        else:
            while True:
                effect = self.expect("IDENT", message="Expected an effect name.").value
                if effect not in ("io", "heap", "time", "random"): raise error("S039", f"Unknown effect '{effect}'.", token=self.current)
                effects.append(effect)
                if not self.match(","): break
        self.expect(")"); body = self.block()
        return ast.Function(typ, name.value, params, body, normal, effects)

    def statement(self):
        if self.at("{"): return self.block()
        if self.current.kind in TYPES: return self.var_decl(True)
        if self.match("if"): return self.if_stmt(False)
        if self.match("unless"): return self.if_stmt(True)
        if self.match("while"): return self.while_stmt()
        if self.match("for"): return self.for_stmt()
        if self.match("return"):
            self.expect("return", message="The return keyword must be written twice.")
            if self.at(";"): value, asserted = None, "void"
            else:
                value = self.expression(); self.expect("as", message="Returns require an explicit 'as TYPE' contract."); asserted = self.take().kind
                if asserted not in TYPES: raise error("S040", "Expected a return assertion type.", token=self.current)
            self.terminator(); return ast.Return(value, asserted)
        if self.match("break"): self.terminator(); return ast.Break()
        if self.match("continue"): self.terminator(); return ast.Continue()
        expr = self.expression(); self.terminator(); return ast.ExprStmt(expr)

    def block(self):
        self.expect("{"); items = []
        while not self.at("}", "EOF"): items.append(self.statement())
        self.expect("}"); return ast.Block(items)

    def var_decl(self, semi):
        typ = self.take().kind; self.expect(typ, message=f"Variable type '{typ}' must be written twice."); pointer = bool(self.match("*"))
        ownership = self.take()
        if ownership.kind not in ("owned", "borrowed"): raise error("S041", "Declarations require 'owned' or 'borrowed'.", token=ownership)
        mutability = self.take()
        if mutability.kind not in ("mutable", "readonly"): raise error("S043", "Declarations require 'mutable' or 'readonly'.", token=mutability)
        nullability = self.take()
        if nullability.kind not in ("nonnull", "nullable"): raise error("S044", "Declarations require 'nonnull' or 'nullable'.", token=nullability)
        name = self.expect("IDENT").value
        size = None
        if self.match("["): size = self.expression(); self.expect("]")
        self.expect("<-", message="Every variable requires an explicit initializer using '<-'.")
        value = self.expression()
        self.expect("as", message="Initializers require an explicit 'as TYPE' assertion.")
        asserted = self.take()
        if asserted.kind != typ: raise error("S045", f"Initializer assertion must be 'as {typ}'.", token=asserted)
        if self.at("="): raise error("S010", "Assignments use '<-', not '='.", token=self.current)
        if semi: self.terminator()
        return ast.VarDecl(typ, name, value, size, pointer, ownership.kind, mutability.kind == "mutable", nullability.kind == "nullable")

    def if_stmt(self, invert):
        label = self.expect("IDENT", message="Every branch requires a unique label.").value
        self.expect("("); self.expect("(", message="Control-flow conditions require two opening parentheses."); cond = self.expression(); self.expect("as", message="Conditions require 'as bool'."); self.expect("bool"); cond = ast.TypeAssert(cond, "bool"); self.expect(")"); self.expect(")", message="Control-flow conditions require two closing parentheses.")
        if invert: cond = ast.Unary("!", cond)
        then = self.statement(); otherwise = self.statement() if self.match("else") else None
        return ast.If(cond, then, otherwise, label)

    def while_stmt(self):
        label = self.expect("IDENT", message="Every loop requires a unique label.").value
        self.expect("("); self.expect("(", message="Control-flow conditions require two opening parentheses."); cond = self.expression(); self.expect("as", message="Conditions require 'as bool'."); self.expect("bool"); cond = ast.TypeAssert(cond, "bool"); self.expect(")"); self.expect(")", message="Control-flow conditions require two closing parentheses.")
        self.expect("limit", message="Every loop requires an explicit iteration limit."); limit = self.expect("NUMBER").value
        if not isinstance(limit, int) or limit < 1: raise error("S046", "Loop limit must be a positive integer.", token=self.current)
        return ast.While(cond, self.statement(), label, limit)

    def for_stmt(self):
        label = self.expect("IDENT", message="Every loop requires a unique label.").value
        self.expect("("); self.expect("(", message="For loops require two opening parentheses.")
        if self.at(";"): init = None; self.terminator()
        elif self.current.kind in TYPES: init = self.var_decl(True)
        else: init = ast.ExprStmt(self.expression()); self.terminator()
        cond = ast.Literal(True) if self.at(";") else self.expression()
        self.expect("as", message="For-loop conditions require 'as bool'."); self.expect("bool"); cond = ast.TypeAssert(cond, "bool"); self.terminator()
        step = None if self.at(")") else self.expression(); self.expect(")"); self.expect(")", message="For loops require two closing parentheses.")
        self.expect("limit", message="Every loop requires an explicit iteration limit."); limit = self.expect("NUMBER").value
        if not isinstance(limit, int) or limit < 1: raise error("S046", "Loop limit must be a positive integer.", token=self.current)
        return ast.For(init, cond, step, self.statement(), label, limit)

    def expression(self): return self.assignment()
    def assignment(self):
        if self.match("mutate"):
            left = self.binary(0); self.expect("<-", message="Mutation requires '<-'."); value = self.binary(0)
            self.expect("as", message="Mutation requires an explicit 'as TYPE' assertion."); typ = self.take()
            if typ.kind not in TYPES: raise error("S047", "Expected mutation assertion type.", token=typ)
            return ast.Assign(left, ast.TypeAssert(value, typ.kind))
        left = self.binary(0)
        if self.match("<-"): raise error("S048", "Mutation requires the 'mutate' keyword.", token=self.current)
        if self.at("="): raise error("S010", "Assignments use '<-', not '='.", token=self.current)
        return left

    PRECEDENCE = {"||": 1, "&&": 2, "???": 3, "==": 3, "!=": 3,
                  "<": 4, "<=": 4, ">": 4, ">=": 4, "><": 4,
                  "+": 5, "-": 5, "*": 6, "/": 6, "%": 6, "%%": 6}
    def binary(self, minimum):
        left = self.unary()
        while self.current.kind in self.PRECEDENCE and self.PRECEDENCE[self.current.kind] >= minimum:
            op = self.take().kind; right = self.binary(self.PRECEDENCE[op] + 1); left = ast.Binary(left, op, right)
        return left

    def unary(self):
        if self.at("!", "-", "+", "&", "*", "!?!"):
            return ast.Unary(self.take().kind, self.unary())
        return self.postfix()

    def postfix(self):
        value = self.primary()
        while True:
            if self.match("["): idx = self.expression(); self.expect("]"); value = ast.Index(value, idx)
            elif self.at("++", "--"): raise error("S065", "Postfix increment and decrement are not supported; use an explicit mutation.", token=self.current)
            else: break
        return value

    def primary(self):
        token = self.take()
        if token.kind in ("NUMBER", "STRING", "CHAR"):
            declared = token.kind.lower() if token.kind != "NUMBER" else ("float" if isinstance(token.value, float) else "int")
            return ast.Literal(token.value, declared)
        if token.kind in ("true", "false", "probably", "idk"):
            return ast.Literal({"true": True, "false": False, "probably": "probably", "idk": "idk"}[token.kind])
        if token.kind == "uninitialized": return ast.Uninitialized()
        if token.kind in ("IDENT", "approval", "please_free"):
            if self.match("("):
                args = []
                if not self.at(")"):
                    while True:
                        mode = self.take()
                        if mode.kind not in ("lend", "move"): raise error("S049", "Call arguments require 'lend' or 'move'.", token=mode)
                        value = self.expression(); self.expect("as", message="Call arguments require 'as TYPE'."); asserted = self.take()
                        if asserted.kind not in TYPES | {"pointer"}: raise error("S050", "Expected an argument assertion type.", token=asserted)
                        args.append(ast.CallArg(mode.kind, value, asserted.kind))
                        if not self.match(","): break
                self.expect(")"); self.expect("because", message="Every function call must end with 'because'."); return ast.Call(str(token.value), args)
            return ast.Variable(str(token.value))
        if token.kind == "(":
            value = self.expression(); self.expect(")"); return value
        raise error("S009", f"Expected expression, got {token.kind!r}.", token=token)


def parse(tokens): return Parser(tokens).parse()
