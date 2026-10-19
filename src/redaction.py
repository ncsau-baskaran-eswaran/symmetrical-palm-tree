"""Masks customer personal information in anything Guardian returns or stores (APP 11).

Audit evidence and probe dossiers quote the agent's own words, which can carry TFNs, Medicare and card numbers,
bank details, contact details and dates of birth. Detection always runs on the raw text; only the output is redacted,
so a PII finding still fires while the copy an insurer stores holds typed placeholders instead of the identifier.

    GUARDIAN_REDACT   "1" (default) masks; "0" disables, for internal debugging only.

Patterns are stricter than the PRV-01 detection patterns: cards must pass Luhn, 9-digit numbers must pass the TFN
checksum unless labelled, and Medicare numbers must pass the check digit unless labelled. Dollar amounts, clause
references, claim numbers and dates in obligations are left alone.
"""

import os
import re
from typing import Any, Callable, FrozenSet, Match

# Keys whose string values carry customer or agent text. Nothing else (citations, clauses, categories,
# obligations, due dates) is ever touched.
CUSTOMER_TEXT_KEYS: FrozenSet[str] = frozenset({
    "evidence", "agent_response", "user_prompt", "adversarial_prompt", "target_response", "response",
    "response_text", "prompt", "judge_reason", "markdown_report", "board_dossier_markdown",
})

_NOT_WORD = r"(?<![\w$.,/-])"  # not inside a longer token, an amount, a claim number or a hash


def redaction_enabled() -> bool:
    return os.environ.get("GUARDIAN_REDACT", "1").strip().lower() not in ("0", "false", "off", "no")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def _tfn_ok(number: str) -> bool:
    if len(number) != 9:
        return False
    return sum(int(d) * w for d, w in zip(number, (1, 4, 3, 7, 5, 8, 6, 9, 10))) % 11 == 0


def _medicare_ok(number: str) -> bool:
    if len(number) not in (10, 11) or number[0] not in "23456":
        return False
    return sum(int(d) * w for d, w in zip(number[:8], (1, 3, 7, 9, 1, 3, 7, 9))) % 10 == int(number[8])


# Labelled forms are masked without a checksum: the label is the evidence that the number is an identifier.
_TFN_LABELLED = re.compile(r"(\b(?:tfn|tax file number)\b[^\d\n]{0,30})(\d(?:[ -]?\d){7,10})(?!\d)", re.I)
_MEDICARE_LABELLED = re.compile(r"(\bmedicare\b(?: card)?(?: number| no\.?)?[^\d\n]{0,15})(\d(?:[ -]?\d){8,10})(?!\d)", re.I)
_BSB_ACCOUNT = re.compile(
    r"(?<![\w$.,/-])\d{3}-\d{3}(?:[ ,]+(?:account|acct|a/c)(?: number| no\.?)?[: ]*|\s+)\d{6,9}(?!\d)", re.I)
_ACCOUNT_LABELLED = re.compile(r"(\b(?:account|acct)(?: number| no\.?)[: ]*)(\d{6,10})(?!\d)", re.I)
_CARD = re.compile(_NOT_WORD + r"\d(?:[ -]?\d){12,18}(?![\w-]|\.\d)")
_MEDICARE = re.compile(_NOT_WORD + r"[2-6]\d{3}[ -]?\d{5}[ -]?\d(?:[ -]?\d)?(?![\w-]|\.\d)")
_TFN = re.compile(_NOT_WORD + r"\d{3}[ -]?\d{3}[ -]?\d{3}(?![\w-]|\.\d|%)")
_EMAIL = re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.I)
_PHONE = re.compile(
    _NOT_WORD + r"(?:(?:\+61|0)[ -]?4\d{2}[ -]?\d{3}[ -]?\d{3}"
    r"|(?:\+61[ -]?|\(?0)[2378]\)?[ -]?\d{4}[ -]?\d{4})(?![\w-]|\.\d)")
_STREET_TYPES = (
    "st|street|rd|road|cres|crescent|ct|court|ave|avenue|pl|place|dr|drive|way|lane|ln|blvd|boulevard|"
    "pde|parade|tce|terrace|hwy|highway|cl|close"
)
_NOT_ADDRESS_WORD = r"(?!(?:days?|months?|years?|weeks?|hours?|business|working|calendar|per|of|the|and|to|in)\b)"
_ADDRESS = re.compile(
    r"\b(?:\d{1,3}/)?\d{1,4}[a-z]? " + _NOT_ADDRESS_WORD + r"[a-z]+(?: " + _NOT_ADDRESS_WORD + r"[a-z]+)? (?:"
    + _STREET_TYPES + r")\b", re.I)
_DATE = (
    r"(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}(?:st|nd|rd|th)? (?:of )?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*,? ?\d{2,4})"
)
_DOB = re.compile(r"(\b(?:dob|d\.o\.b\.?|date of birth|born(?: on)?)\b[:\s]*)" + _DATE, re.I)


def _checked(placeholder: str, ok: Callable[[str], bool]) -> Callable[[Match[str]], str]:
    def repl(m: Match[str]) -> str:
        return placeholder if ok(_digits(m.group(0))) else m.group(0)
    return repl


def redact(text: Any) -> Any:
    """Return `text` with Australian personal identifiers replaced by typed placeholders."""
    if not isinstance(text, str) or not text or not redaction_enabled():
        return text
    text = _TFN_LABELLED.sub(lambda m: m.group(1) + "[TFN]", text)
    text = _MEDICARE_LABELLED.sub(lambda m: m.group(1) + "[MEDICARE]", text)
    text = _BSB_ACCOUNT.sub("[BSB-ACCOUNT]", text)
    text = _ACCOUNT_LABELLED.sub(lambda m: m.group(1) + "[BSB-ACCOUNT]", text)
    text = _CARD.sub(_checked("[CARD]", lambda d: 13 <= len(d) <= 19 and _luhn_ok(d)), text)
    text = _MEDICARE.sub(_checked("[MEDICARE]", _medicare_ok), text)
    text = _TFN.sub(_checked("[TFN]", _tfn_ok), text)
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    text = _ADDRESS.sub("[ADDRESS]", text)
    text = _DOB.sub(lambda m: m.group(1) + "[DOB]", text)
    return text


def redact_obj(obj: Any) -> Any:
    """Return a copy of `obj` with string values redacted under the customer-text keys only."""
    if not redaction_enabled():
        return obj
    return _walk(obj)


def _walk(obj: Any, redact_here: bool = False) -> Any:
    if isinstance(obj, dict):
        return {k: _walk(v, k in CUSTOMER_TEXT_KEYS) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v, redact_here) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_walk(v, redact_here) for v in obj)
    if redact_here and isinstance(obj, str):
        return redact(obj)
    return obj
