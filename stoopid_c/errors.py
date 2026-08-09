class StoopidError(Exception):
    def __init__(self, code, message, detail="", line=None, column=None):
        self.code, self.message, self.detail = code, message, detail
        self.line, self.column = line, column
        super().__init__(message)

    def __str__(self):
        where = f" at {self.line}:{self.column}" if self.line is not None else ""
        extra = f"\n{self.detail}" if self.detail else ""
        return f"STOOPID ERROR {self.code}{where}:\n{self.message}{extra}"


class ReturnSignal(Exception):
    def __init__(self, value): self.value = value


class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass


def error(code, message, detail="", token=None):
    return StoopidError(code, message, detail,
                        getattr(token, "line", None), getattr(token, "column", None))
