"""Masks customer personal information in anything Guardian returns or stores (APP 11).

Audit evidence and probe dossiers quote the agent's own words, which can carry TFNs, Medicare and card numbers,
bank details, contact details and dates of birth. Detection always runs on the raw text; only the output is redacted,
so a PII finding still fires while the copy an insurer stores holds typed placeholders instead of the identifier.

    GUARDIAN_REDACT         "1" (default) masks; "0" disables, for internal debugging only.
    GUARDIAN_REDACT_NAMES   person-name masking; inherits GUARDIAN_REDACT, "0" turns off names only.

Patterns are stricter than the PRV-01 detection patterns: cards must pass Luhn, 9-digit numbers must pass the TFN
checksum unless labelled, and Medicare numbers must pass the check digit unless labelled. Dollar amounts, clause
references, claim numbers and dates in obligations are left alone.

Names are masked with precision first and no ML: a capitalised name after a cue ("customer", "Mr", "my name is") is
always masked, and an unlabelled "First Last" is masked only when the first token is a bundled common given name and
the pair is not a known non-person term (regulator, instrument, insurer, place, product). Ambiguous words such as
Mark, Will or Grace are not in the given-name list, so they mask only when a cue precedes them.
"""

import os
import re
from functools import lru_cache
from pathlib import Path
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


def names_redaction_enabled() -> bool:
    default = "1" if redaction_enabled() else "0"
    return os.environ.get("GUARDIAN_REDACT_NAMES", default).strip().lower() not in ("0", "false", "off", "no")


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


# ---------------------------------------------------------------------------------------------------------------
# Person names
# ---------------------------------------------------------------------------------------------------------------

_GIVEN_NAMES_FILE = Path(__file__).parent / "data" / "given_names.txt"


@lru_cache(maxsize=1)
def _given_names() -> FrozenSet[str]:
    try:
        lines = _GIVEN_NAMES_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(l.strip().lower() for l in lines if l.strip() and not l.startswith("#"))


# One capitalised name token: O'Brien, McDonald, Smith-Jones, Anne, or an initial such as "J.".
_TOK = r"(?:[A-Z]['\u2019][A-Z][a-z]+|Mc[A-Z][a-z]+(?:-[A-Z][a-z]+)*|[A-Z][a-z]+(?:-[A-Z][a-z]+)*|[A-Z]\.)"
_TOK_RE = re.compile(_TOK)
_SEQ = _TOK + r"(?:[ ]" + _TOK + r"){0,3}"

# Words that are capitalised in ordinary insurance prose and are never (part of) a person name.
_NON_NAME_WORDS: FrozenSet[str] = frozenset(w.lower() for w in """
The This That These Those Our Your Their His Her Its My We You They It He She There Here What When Where Which Who Why
How And But Or If As At By For From In Of On To With Is Are Was Were Be Not No Yes Please Thanks Thank Sorry Hello Hi
Dear Regards Sincerely Kind Best Good Great Welcome Sure Certainly Unfortunately Happy Glad Afraid Unable Currently
Service Services Support Team Teams Number Numbers Details Detail Data Information Name Names Account Accounts Portal
Satisfaction Experience Benefits Benefit Policy Policies Claim Claims Cover Coverage Insurance Insurer Insurers Group
Limited Ltd Pty Australia Australian Bank Life Health Care Code Act Acts Regulations Regulation Rules Rule Standard
Standards Authority Commission Court Tribunal Ombudsman Scheme Department Fund Financial Park Street Road Hospital
Clinic Centre Center University College School Council Association Society Union Network Plan Plans Plus Line
Assessor Officer Manager Department Desk Helpdesk Representative Adviser Advisor Consultant Agent Agents Assistant
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August
September October November December News Notice Notices Period Date Dates Form Forms Process Review Reviews Complaint
Complaints Dispute Disputes Decision Decisions Letter Letters Email Phone Address Contact Status Update Updates
Payment Payments Premium Premiums Excess Limit Limits Exclusion Exclusions Condition Conditions Terms Schedule
Disclosure Statement Statements Product Products Document Documents Guide Guides Summary Section Part Schedule
Medical Travel Home Motor Car Contents Building Buildings Business Commercial Personal Private Public National
Federal State Territory Government Industry Management Risk Compliance Operations Customer Customers Member Members
Sir Madam Medicare Centrelink Suncorp Allianz Medibank Bupa Nib Qbe Aami Youi Cgu Hcf Hbf Ahm Tower Budget Woolworths Coles
Policyholder Policyholders Claimant Claimants Insured Beneficiary Applicant Patient Driver Name Hardship Fair Unfair
Conduct Practice Practices Principle Principles Duty Obligation Obligations General Special Standard Super Wealth
""".split())

# Whole phrases that look like "Given Surname" or a name after a cue but are not people.
_NON_PERSON_PHRASES: FrozenSet[str] = frozenset(p.lower() for p in """
New South Wales|South Australia|Western Australia|Northern Territory|Australian Capital Territory|Good News|Good News
Claims Team|Gold Coast|Sunshine Coast|Port Macquarie|Alice Springs|Mount Isa|Coffs Harbour|Great Barrier Reef
Sunshine Guardian|Insurance Contracts Act|General Insurance Code|Privacy Act|Corporations Act|Competition Act
Hunter Valley|Blue Mountains|Snowy Mountains|Murray Darling|Victoria Park|Kings Cross|Bondi Beach
""".replace("\n", "|").split("|") if p.strip())

_CUE_WORDS = (
    r"policy ?holders?|customers?|members?|claimants?|insureds?|beneficiar(?:y|ies)|applicants?|patients?|drivers?"
    r"|name is|name's|name:|full name:?|my name's|(?:account|policy) holder|(?:first|last|sur)name:?"
)
# Weaker cues: a single capitalised word after them is a name only when it is a known given name, because
# "regarding Medicare" or "called Sydney" must survive.
_STRICT_CUE_WORDS = (
    r"named|called|dear|on behalf of|spoke (?:to|with)|speaking (?:to|with)|regarding|attention:?|attn:?|caller:?|hi|hello|hey|thanks|thank you"
)
# Cue (case-insensitive) then a case-sensitive capitalised sequence.
_LABELLED = re.compile(r"((?i:\b(?:" + _CUE_WORDS + r")[:,]?)[ ]+)(" + _SEQ + r")")
_LABELLED_STRICT = re.compile(r"((?i:\b(?:" + _STRICT_CUE_WORDS + r")[:,]?)[ ]+)(" + _SEQ + r")")
_TITLED = re.compile(r"\b((?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Professor)\.?[ ]+)(" + _SEQ + r")")
_IM = re.compile(r"((?i:\b(?:I'm|I\u2019m|I am))[ ]+)(" + _SEQ + r")")
_POSSESSIVE_CLAIM = re.compile(
    r"\b(" + _TOK + r")(['\u2019]s)(?= (?:claim|policy|account|case|file|application|premium|cover|medical|"
    r"diagnosis|treatment|payout|settlement|details|record|address|number|surgery|injury|accident)\b)")
_UNLABELLED = re.compile(r"(?<![\w@'\u2019-])(" + _SEQ + r")(?![\w@])")


def _leading_name(seq: str, need_given_or_surname: bool = False) -> int:
    """Length (in chars) of the leading run of `seq` that reads as a person name, or 0 when it does not."""
    toks = list(_TOK_RE.finditer(seq))
    keep = []
    for m in toks:
        t = m.group(0)
        if t.lower() in _NON_NAME_WORDS:
            break
        keep.append(m)
    if not keep:
        return 0
    if need_given_or_surname and len(keep) < 2 and keep[0].group(0).lower() not in _given_names():
        return 0
    phrase = " ".join(m.group(0) for m in keep).lower()
    if any(phrase == p or phrase.startswith(p + " ") for p in _NON_PERSON_PHRASES):
        return 0
    return keep[-1].end()


def _mask_after_cue(m: Match[str], strict: bool = False) -> str:
    n = _leading_name(m.group(2), need_given_or_surname=strict)
    if not n:
        return m.group(0)
    return m.group(1) + "[NAME]" + m.group(2)[n:]


def _mask_unlabelled(m: Match[str]) -> str:
    seq = m.group(1)
    toks = list(_TOK_RE.finditer(seq))
    # A run longer than the 3 tokens of a plausible name is a heading or product string: leave it.
    if len(toks) < 2 or len(toks) > 3:
        return seq
    first = toks[0].group(0)
    if first.lower() not in _given_names():
        return seq
    if any(t.group(0).lower() in _NON_NAME_WORDS for t in toks[1:]):
        return seq
    if any(len(t.group(0)) == 1 for t in toks[1:2]):  # "Jane J" with no real surname
        return seq
    phrase = seq.lower()
    if any(phrase == p or phrase.startswith(p + " ") for p in _NON_PERSON_PHRASES):
        return seq
    return "[NAME]"


def redact_names(text: str) -> str:
    """Mask person names: cue-labelled ones always, unlabelled "Given Surname" pairs by given-name list."""
    text = _LABELLED.sub(_mask_after_cue, text)
    text = _LABELLED_STRICT.sub(lambda m: _mask_after_cue(m, strict=True), text)
    text = _TITLED.sub(_mask_after_cue, text)
    text = _IM.sub(lambda m: _mask_after_cue(m, strict=True), text)
    text = _POSSESSIVE_CLAIM.sub(
        lambda m: "[NAME]" + m.group(2) if m.group(1).lower() in _given_names() else m.group(0), text)
    return _UNLABELLED.sub(_mask_unlabelled, text)


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
    if names_redaction_enabled():
        text = redact_names(text)
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
