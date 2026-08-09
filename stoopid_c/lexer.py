from dataclasses import dataclass
from .errors import error


@dataclass
class Token:
    kind: str
    value: object
    line: int
    column: int


KEYWORDS = {
    "int", "float", "char", "bool", "string", "void", "result", "if", "else",
    "while", "for", "break", "continue", "return", "true", "false",
    "probably", "idk", "approval", "unless", "please_free", "seriously",
    "because", "owned", "borrowed", "mutable", "readonly", "nonnull",
    "nullable", "effects", "none", "as", "lend", "move", "mutate",
    "limit", "uninitialized", "pointer",
}
TWO = {"==", "!=", "<=", ">=", "&&", "||", "++", "--", "%%", "><", "<-"}
THREE = {"???", "!?!"}
SINGLE = set("+-*/%=<>&!;:,(){}[]@")


def lex(source):
    out, i, line, col = [], 0, 1, 1
    n = len(source)
    def advance(count=1):
        nonlocal i, line, col
        for _ in range(count):
            if source[i] == "\n": line, col = line + 1, 1
            else: col += 1
            i += 1
    while i < n:
        c = source[i]
        if c.isspace(): advance(); continue
        if source.startswith("//", i):
            while i < n and source[i] != "\n": advance()
            continue
        if source.startswith("/*", i):
            start = (line, col); advance(2)
            while i < n and not source.startswith("*/", i): advance()
            if i >= n: raise error("S002", "Unterminated comment.", token=Token("", "", *start))
            advance(2); continue
        start_line, start_col = line, col
        if c == '#':
            while i < n and source[i] != "\n": advance()
            continue
        if c.isalpha() or c == '_':
            start = i
            while i < n and (source[i].isalnum() or source[i] == '_'): advance()
            word = source[start:i]
            out.append(Token(word if word in KEYWORDS else "IDENT", word, start_line, start_col)); continue
        if c.isdigit():
            start = i
            while i < n and source[i].isdigit(): advance()
            if i < n and source[i] == '.' and i + 1 < n and source[i + 1].isdigit():
                advance()
                while i < n and source[i].isdigit(): advance()
                out.append(Token("NUMBER", float(source[start:i]), start_line, start_col))
            else: out.append(Token("NUMBER", int(source[start:i]), start_line, start_col))
            continue
        if c in ('"', "'"):
            quote, buf = c, []; advance()
            escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
            while i < n and source[i] != quote:
                if source[i] == "\n": raise error("S003", "Newline in string literal.", token=Token("", "", start_line, start_col))
                if source[i] == "\\":
                    advance()
                    if i >= n: break
                    buf.append(escapes.get(source[i], source[i])); advance()
                else: buf.append(source[i]); advance()
            if i >= n: raise error("S003", "Unterminated string literal.", token=Token("", "", start_line, start_col))
            advance(); value = "".join(buf)
            if quote == "'" and len(value) != 1: raise error("S005", "A char must contain exactly one character.", token=Token("", "", start_line, start_col))
            out.append(Token("CHAR" if quote == "'" else "STRING", value, start_line, start_col)); continue
        op3, op2 = source[i:i+3], source[i:i+2]
        if op3 in THREE: out.append(Token(op3, op3, line, col)); advance(3); continue
        if op2 in TWO: out.append(Token(op2, op2, line, col)); advance(2); continue
        if c in SINGLE: out.append(Token(c, c, line, col)); advance(); continue
        raise error("S004", f"Unexpected character {c!r}.", token=Token("", "", line, col))
    out.append(Token("EOF", "", line, col))
    return out
