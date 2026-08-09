import re
from .lexer import lex
from .parser import parse
from .runtime import Interpreter
from .semantic import check


def preprocess(source):
    defines = {}
    lines = []
    for line in source.splitlines():
        match = re.match(r"\s*#define\s+([A-Za-z_]\w*)\s+(.+?)\s*$", line)
        if match:
            defines[match.group(1)] = match.group(2)
        elif re.match(r"\s*#include\s+[<\"]stoopid\.h[>\"]\s*$", line):
            pass
        elif line.lstrip().startswith("#"):
            from .errors import error
            raise error("S030", f"Unsupported preprocessor directive: {line.strip()}")
        else: lines.append(line)
    result = "\n".join(lines)
    for name, value in defines.items(): result = re.sub(rf"\b{re.escape(name)}\b", value, result)
    return result


def compile_source(source): return check(parse(lex(preprocess(source))))


def run_source(source, stdin=input, stdout=print, call_main=True):
    interpreter = Interpreter(stdin=stdin, stdout=stdout)
    result = interpreter.run(compile_source(source), call_main=call_main)
    return result, interpreter
