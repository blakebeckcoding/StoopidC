from .lexer import lex


def format_source(source):
    directives = [line.strip() for line in source.splitlines() if line.lstrip().startswith("#")]
    tokens = lex(source)
    out, line, indent = [], "", 0
    def flush():
        nonlocal line
        if line.strip(): out.append("    " * indent + line.strip())
        line = ""
    no_space_before = {";", ",", ")", "]", "("}
    for token in tokens[:-1]:
        k, v = token.kind, token.value
        if k == "{":
            if line and not line.endswith(" "): line += " "
            line += "{"; flush(); indent += 1
        elif k == "}":
            flush(); indent = max(0, indent - 1); out.append("    " * indent + "}")
        elif k == ";":
            line += ";"
            if line.endswith(";;"): flush()
        elif k == ",": line += ", "
        else:
            if k == "STRING": text = '"' + str(v).replace('"', '\\"') + '"'
            elif k == "CHAR": text = "'" + str(v) + "'"
            elif k in ("true", "false", "probably", "idk"): text = k
            else: text = str(v)
            if line and not line.endswith((" ", "(", "[", "@")) and k not in no_space_before and k not in (")", "]"): line += " "
            line += text
    flush()
    body = "\n".join(out) + "\n"
    return ("\n".join(directives) + "\n\n" if directives else "") + body
