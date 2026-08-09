import io
import unittest
from pathlib import Path
from unittest.mock import patch

from stoopid_c.cli import main
from stoopid_c.engine import compile_source, preprocess, run_source
from stoopid_c.errors import StoopidError
from stoopid_c.formatter import format_source
from stoopid_c.lexer import lex


def program(body, effects="none"):
    return f"@normal int int main() seriously effects({effects}) {{{body}}}"


def execute(body, effects="none", inputs=None):
    output = io.StringIO(); values = iter(inputs or [])
    def stdin(_=""): return next(values)
    def stdout(*args, **kwargs): print(*args, file=output, **kwargs)
    result, vm = run_source(program(body, effects), stdin, stdout)
    return result, output.getvalue(), vm


class LexerTests(unittest.TestCase):
    def test_literals_and_hostile_tokens(self):
        tokens = lex('int int owned mutable nonnull n <- 12 as int;;')
        kinds = [token.kind for token in tokens]
        for kind in ("owned", "mutable", "nonnull", "<-", "as"): self.assertIn(kind, kinds)

    def test_bad_character(self):
        with self.assertRaisesRegex(StoopidError, "S004"): lex("$")


class FrontEndTests(unittest.TestCase):
    def test_function_ast_records_contracts(self):
        source = "int int add(int int borrowed readonly nonnull a) seriously effects(io) {approval() because;;return return a as int;;}"
        fn = compile_source(source).functions[0]
        self.assertEqual(fn.effects, ["io"]); self.assertEqual(fn.params[0][3:], ("borrowed", False, False))

    def test_old_conveniences_are_rejected(self):
        invalid = [
            "int x = 1;", "int int x <- 1;;",
            "int int owned mutable nonnull x <- 1;;",
            "@normal int int main() {return return 0 as int;;}",
            "@normal int int main() seriously effects(none) {return 0 as int;;}",
            "@normal int int main() seriously effects(none) {return return 0 as int;}",
            "@normal int int main() seriously effects(io) {println(lend 1 as int);;return return 0 as int;;}",
            "@normal int int main() seriously effects(none) {if ((true as bool)) {return return 0 as int;;}}",
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(StoopidError): compile_source(source)

    def test_forbidden_name_and_semantics(self):
        with self.assertRaisesRegex(StoopidError, "S013"):
            compile_source("@normal int int extra() seriously effects(none) {return return 0 as int;;}")
        with self.assertRaisesRegex(StoopidError, "S034"): compile_source("break;;")
        duplicate_labels = program("if same ((true as bool)) {} if same ((false as bool)) {} return return 0 as int;;")
        with self.assertRaisesRegex(StoopidError, "S078"): compile_source(duplicate_labels)

    def test_preprocessor(self):
        source = preprocess("#include <stoopid.h>\n#define N 9\nint int owned readonly nonnull a <- N as int;;")
        self.assertIn("9", source)


class TypeAndOwnershipTests(unittest.TestCase):
    def test_exact_types(self):
        with self.assertRaisesRegex(StoopidError, "S022"):
            execute("float float owned readonly nonnull n <- 1 as float;;return return 0 as int;;")

    def test_readonly_mutation(self):
        with self.assertRaisesRegex(StoopidError, "S057"):
            execute("int int owned readonly nonnull n <- 1 as int;;mutate n <- 2 as int;;return return 0 as int;;")

    def test_argument_assertion(self):
        with self.assertRaisesRegex(StoopidError, "S058"):
            execute('println(lend "text" as int) because;;return return 0 as int;;', "io")

    def test_owned_parameter_requires_move_and_invalidates_source(self):
        prefix = "int int take(string string owned readonly nonnull s) seriously effects(none) {approval() because;;return return length(lend s as string) because as int;;}"
        body = 'string string owned readonly nonnull s <- "abc" as string;;take(move s as string) because;;return return length(lend s as string) because as int;;'
        with self.assertRaisesRegex(StoopidError, "S055"): run_source(prefix + program(body))

    def test_borrowed_parameter_requires_lend(self):
        prefix = "int int take(int int borrowed readonly nonnull n) seriously effects(none) {approval() because;;return return n as int;;}"
        body = "int int owned readonly nonnull n <- 1 as int;;return return take(move n as int) because as int;;"
        with self.assertRaisesRegex(StoopidError, "S063"): run_source(prefix + program(body))


class RuntimeTests(unittest.TestCase):
    def test_arithmetic_and_display(self):
        result, out, _ = execute("int int owned readonly nonnull a <- 7 as int;;float float owned readonly nonnull b <- 2.5 as float;;println(lend a*2 as int,lend b as float) because;;return return a+1 as int;;", "io")
        self.assertEqual((result, out), (8, "14 2.500000\n"))

    def test_labeled_bounded_control_flow(self):
        body = "int int owned mutable nonnull n <- 0 as int;;while counting ((n < 3 as bool)) limit 3 {mutate n <- n+1 as int;;}return return n as int;;"
        self.assertEqual(execute(body)[0], 3)
        with self.assertRaisesRegex(StoopidError, "S105"):
            execute("while endless ((true as bool)) limit 2 {}return return 0 as int;;")

    def test_function_and_recursion(self):
        fact = "int int fact(int int borrowed readonly nonnull n) seriously effects(none) {approval() because;;if base ((n<=1 as bool)){return return 1 as int;;}return return n*fact(lend n-1 as int) because as int;;}"
        self.assertEqual(run_source(fact + program("return return fact(lend 5 as int) because as int;;"))[0], 120)

    def test_array_requires_initialization(self):
        declaration = "int int owned mutable nonnull a[2] <- uninitialized as int;;"
        with self.assertRaisesRegex(StoopidError, "A007"): execute(declaration + "return return a[1] as int;;")
        self.assertEqual(execute(declaration + "mutate a[1] <- 9 as int;;return return a[1] as int;;")[0], 9)
        with self.assertRaisesRegex(StoopidError, "A001"): execute(declaration + "return return a[0] as int;;")

    def test_strings_are_one_based(self):
        body = 'string string owned readonly nonnull s <- "hello" as string;;println(lend s[1] as char,lend substring(lend s as string,lend 2 as int,lend 4 as int) because as string) because;;return return 0 as int;;'
        self.assertEqual(execute(body, "io")[1], "h ell\n")

    def test_pointer_and_heap_contract(self):
        body = "int int owned mutable nonnull n <- 4 as int;;int int *owned mutable nonnull p <- &n as int;;mutate *p <- 8 as int;;return return n as int;;"
        self.assertEqual(execute(body)[0], 8)
        bad = "int int *owned mutable nonnull p <- malloc(lend 2 as int) because as int;;free(lend p as pointer) because;;return return 0 as int;;"
        with self.assertRaisesRegex(StoopidError, "S071"): execute(bad, "heap")

    def test_effect_contract(self):
        with self.assertRaisesRegex(StoopidError, "S061"):
            execute('println(lend "no" as string) because;;return return 0 as int;;')

    def test_results_require_inspection_and_ordered_unwrap(self):
        ignored = 'result result owned mutable nonnull r <- atoi(lend "3" as string) because as result;;return return 0 as int;;'
        with self.assertRaisesRegex(StoopidError, "S072"): execute(ignored)
        early = 'result result owned mutable nonnull r <- atoi(lend "3" as string) because as result;;int int owned readonly nonnull n <- unwrap(lend r as result) because as int;;return return n as int;;'
        with self.assertRaisesRegex(StoopidError, "S075"): execute(early)
        handled = 'result result owned mutable nonnull r <- atoi(lend "3" as string) because as result;;bool bool owned readonly nonnull ok <- inspect(lend r as result) because as bool;;int int owned readonly nonnull n <- unwrap(lend r as result) because as int;;return return n as int;;'
        self.assertEqual(execute(handled)[0], 3)

    def test_stupid_operators(self):
        body = 'if comparison (("2" ??? 2 as bool)){return return 7 %% 4 as int;;}return return 0 as int;;'
        self.assertEqual(execute(body)[0], 3)

    def test_division_by_zero(self):
        with self.assertRaisesRegex(StoopidError, "S042"): execute("return return 1/0 as int;;")


class ToolTests(unittest.TestCase):
    def test_formatter_is_idempotent_and_executable(self):
        source = program("int int owned readonly nonnull x <- 1 as int;;return return x as int;;")
        once = format_source(source)
        self.assertEqual(format_source(once), once); self.assertEqual(run_source(once)[0], 1)

    def test_cli_run_and_check(self):
        hello = str(Path(__file__).parents[1] / "examples" / "hello.sc")
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(main(["run", hello]), 0); self.assertIn("Hello", stdout.getvalue())
        with patch("sys.stdout", new_callable=io.StringIO): self.assertEqual(main(["check", hello]), 0)

    def test_repl_expression(self):
        with patch("builtins.input", side_effect=["2 + 3;;", "exit"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(main(["repl"]), 0); self.assertIn("5", out.getvalue())


if __name__ == "__main__": unittest.main()
