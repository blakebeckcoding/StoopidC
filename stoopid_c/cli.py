import argparse
import sys
from pathlib import Path
from . import __version__
from .engine import compile_source, run_source
from .errors import StoopidError
from .formatter import format_source
from .runtime import Interpreter


def warnings(interpreter):
    for code, message in interpreter.warnings: print(f"warning {code}:\n{message}", file=sys.stderr)


def run_file(path, check=False):
    source = Path(path).read_text(encoding="utf8")
    if check:
        program = compile_source(source)
        vm = Interpreter(); vm.run(program, call_main=False)
        print(f"{path}: valid")
    else:
        result, vm = run_source(source); warnings(vm)
        return int(result) if isinstance(result, int) and not isinstance(result, bool) else 0
    return 0


def repl():
    print(f"Stoopid C REPL v{__version__}\nType 'help' for help. Ctrl-D to exit.")
    vm = Interpreter(); vm.functions = {}
    while True:
        try: line = input(">>> ")
        except (EOFError, KeyboardInterrupt): print(); return 0
        if line.strip() in ("quit", "exit"): return 0
        if line.strip() == "help": print("Enter a declaration, statement, or expression using the full SC ceremony."); continue
        if not line.strip(): continue
        try:
            source = line if line.rstrip().endswith((";", "}")) else line + ";"
            program = compile_source(source)
            if program.functions:
                vm.run(program, call_main=False); print("function accepted")
            elif program.statements:
                stmt = program.statements[0]
                from . import ast
                if isinstance(stmt, ast.ExprStmt):
                    value = vm.eval(stmt.expr)
                    if value is not None: print(vm.display(value))
                else: vm.execute(stmt)
        except StoopidError as exc: print(exc, file=sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"run", "check", "repl", "fmt"}
    if argv and not argv[0].startswith("-") and argv[0] not in commands:
        argv.insert(0, "run")
    parser = argparse.ArgumentParser(prog="stoopid", description="Run Stoopid C programs.")
    parser.add_argument("--version", action="version", version=f"Stoopid C {__version__}")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="run a .sc file"); run.add_argument("file")
    check = sub.add_parser("check", help="parse and validate a file"); check.add_argument("file")
    sub.add_parser("repl", help="start the interactive shell")
    fmt = sub.add_parser("fmt", help="format a source file"); fmt.add_argument("file"); fmt.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "run": return run_file(args.file)
        if args.command == "check": return run_file(args.file, True)
        if args.command == "repl": return repl()
        if args.command == "fmt":
            path = Path(args.file); old = path.read_text(encoding="utf8"); new = format_source(old)
            if args.check: return 0 if old == new else 1
            path.write_text(new, encoding="utf8"); return 0
        parser.print_help(); return 0
    except (StoopidError, OSError) as exc:
        print(exc, file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
