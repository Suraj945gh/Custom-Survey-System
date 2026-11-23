"""Read `show-if` rules such as  q2=Yes AND (q7=Samsung OR q8>=4).

The rule becomes a small tree so the validator can check every part of it and the
survey engine (step 4) can work out whether it is true for a respondent's answers.

    AND binds tighter than OR, like in maths:  a OR b AND c  means  a OR (b AND c).
    Brackets change the order.
    Operators: =  !=  >  >=  <  <=   (the last four only make sense for numbers).
    Values may contain spaces:  q4=Other city AND q5=Yes
    A value that contains brackets needs quotes:  q6='Other (specify)'
    AND / OR must be written in capitals, so a value like "Salt and pepper" still works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Union

ORDER_OPERATORS = {">", ">=", "<", "<="}


class ConditionError(ValueError):
    """The rule text could not be read. The message says why, in plain words."""


@dataclass(frozen=True)
class Compare:
    """One test, e.g. q2 = Yes."""

    qid: str
    op: str
    value: str


@dataclass(frozen=True)
class AllOf:
    """Every part must be true (AND)."""

    items: tuple["Node", ...]


@dataclass(frozen=True)
class AnyOf:
    """At least one part must be true (OR)."""

    items: tuple["Node", ...]


Node = Union[Compare, AllOf, AnyOf]

# One token at a time: a bracket, AND / OR, or a whole comparison like q4=Other city.
_JOIN = r"(?:AND|OR)(?=[\s(]|$)"
_TOKEN = re.compile(
    rf"""
    \s*(?:
        (?P<lpar>\() |
        (?P<rpar>\)) |
        (?P<join>{_JOIN}) |
        (?P<qid>[A-Za-z][\w-]*)\s*(?P<op>!=|>=|<=|=|>|<)\s*
        (?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^()]*?))
        (?=\s+{_JOIN}|\s*\)|\s*$)
    )
    """,
    re.VERBOSE,
)
# "q2=Yes and q7=Samsung": a lower-case join hiding inside a value.
_LOWER_JOIN = re.compile(r"\s(and|or)\s+[A-Za-z][\w-]*\s*(!=|>=|<=|=|>|<)")
# "q2=Yes q3=No": a second test with no AND / OR in between.
_HIDDEN_TEST = re.compile(r"\s[A-Za-z][\w-]*\s*(!=|>=|<=|=|>|<)")


def _tokenize(text: str) -> list[object]:
    tokens: list[object] = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            rest = text[pos:].strip()
            if re.match(r"[A-Za-z][\w-]*\s*$", rest) or re.match(r"[A-Za-z][\w-]*\s+[^=!<>]", rest):
                raise ConditionError(f"'{rest.split()[0]}' needs a comparison, like {rest.split()[0]}=Yes.")
            raise ConditionError(f"Could not understand '{rest[:25]}'.")
        if m.group("lpar"):
            tokens.append("(")
        elif m.group("rpar"):
            tokens.append(")")
        elif m.group("join"):
            tokens.append(m.group("join"))
        else:
            quoted = m.group("dq") if m.group("dq") is not None else m.group("sq")
            value = quoted if quoted is not None else (m.group("bare") or "").strip()
            if quoted is None and _LOWER_JOIN.search(" " + value):
                raise ConditionError("Write AND / OR in capital letters.")
            if quoted is None and _HIDDEN_TEST.search(" " + value):
                raise ConditionError("Two tests need AND or OR between them.")
            if not value:
                raise ConditionError(f"'{m.group('qid')}{m.group('op')}' is missing a value.")
            tokens.append(Compare(m.group("qid"), m.group("op"), value))
        pos = m.end()
    return tokens


class _Parser:
    """Recursive descent:  expr = term (OR term)* ;  term = factor (AND factor)* ;
    factor = '(' expr ')' | comparison."""

    def __init__(self, tokens: list[object]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> object:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> object:
        tok = self.peek()
        self.pos += 1
        return tok

    def expr(self) -> Node:
        items = [self.term()]
        while self.peek() == "OR":
            self.take()
            items.append(self.term())
        return items[0] if len(items) == 1 else AnyOf(tuple(items))

    def term(self) -> Node:
        items = [self.factor()]
        while self.peek() == "AND":
            self.take()
            items.append(self.factor())
        return items[0] if len(items) == 1 else AllOf(tuple(items))

    def factor(self) -> Node:
        tok = self.take()
        if isinstance(tok, Compare):
            return tok
        if tok == "(":
            node = self.expr()
            if self.take() != ")":
                raise ConditionError("A '(' is never closed with ')'.")
            return node
        if tok is None:
            raise ConditionError("The rule ends too early; something is missing after AND / OR.")
        raise ConditionError(f"Unexpected '{tok}'.")


def parse_condition(text: str) -> Node:
    """Turn rule text into a tree. Raises ConditionError with a readable message."""
    tokens = _tokenize(text or "")
    if not tokens:
        raise ConditionError("The rule is empty.")
    parser = _Parser(tokens)
    node = parser.expr()
    if parser.peek() is not None:
        extra = parser.peek()
        if extra == ")":
            raise ConditionError("There is a ')' without a matching '('.")
        raise ConditionError("Two tests need AND or OR between them.")
    return node


def comparisons(node: Node) -> Iterator[Compare]:
    """Every single test inside a rule, left to right."""
    if isinstance(node, Compare):
        yield node
    else:
        for item in node.items:
            yield from comparisons(item)
