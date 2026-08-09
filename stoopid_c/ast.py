from dataclasses import dataclass, field
from typing import Any, List, Optional

@dataclass
class Program: functions: List[Any]; statements: List[Any]
@dataclass
class Function: return_type: str; name: str; params: List[Any]; body: Any; normal: bool = False; effects: List[str] = field(default_factory=list)
@dataclass
class Block: statements: List[Any]
@dataclass
class VarDecl: type: str; name: str; value: Any = None; size: Any = None; pointer: bool = False; ownership: str = "owned"; mutable: bool = False; nullable: bool = False
@dataclass
class ExprStmt: expr: Any
@dataclass
class If: condition: Any; then: Any; otherwise: Any = None; label: str = ""
@dataclass
class While: condition: Any; body: Any; label: str = ""; limit: int = 0
@dataclass
class For: init: Any; condition: Any; step: Any; body: Any; label: str = ""; limit: int = 0
@dataclass
class Return: value: Any = None; asserted_type: str = "void"
@dataclass
class Break: pass
@dataclass
class Continue: pass
@dataclass
class Literal: value: Any; declared_type: str = ""
@dataclass
class Variable: name: str
@dataclass
class Unary: op: str; value: Any
@dataclass
class Binary: left: Any; op: str; right: Any
@dataclass
class Assign: target: Any; value: Any
@dataclass
class CallArg: mode: str; value: Any; asserted_type: str
@dataclass
class Call: name: str; args: List[Any]
@dataclass
class Index: value: Any; index: Any
@dataclass
class Postfix: target: Any; op: str
@dataclass
class TypeAssert: value: Any; type: str
@dataclass
class Uninitialized: pass
