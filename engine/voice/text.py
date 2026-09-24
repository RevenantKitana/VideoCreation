"""
Spoken-form normalisation for Vietnamese narration.

The checker (align.py) listens for letters, so every written word must be turned into
what a speaker actually says: "1" -> "một", "25" -> "hai mươi lăm", "K" -> "ca".
Captions, though, show the words as written. So `tokens()` returns both: each written
word with the spoken tokens it expands to, and timings map back through that.
"""

from __future__ import annotations

import re
import unicodedata

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

# How single Latin letters are read aloud in a Vietnamese maths class. Scoring is
# lenient on these (see align.py): teachers vary ("y" = "i" / "y dài").
LETTERS = {
    "a": "a", "b": "bê", "c": "xê", "d": "đê", "e": "e", "f": "ép", "g": "giê",
    "h": "hát", "i": "i", "j": "gi", "k": "ca", "l": "lờ", "m": "mờ", "n": "nờ",
    "o": "o", "p": "pê", "q": "quy", "r": "rờ", "s": "ét", "t": "tê", "u": "u",
    "v": "vê", "w": "vê kép", "x": "ích", "y": "i", "z": "dét",
}

# Characters a narration line must never contain: the voice cannot say them.
UNSPEAKABLE = re.compile(r"[$\\^_=<>{}\[\]|~*/'`\"+]")


def _below_100(n: int) -> list[str]:
    if n < 10:
        return [DIGITS[n]]
    tens, unit = divmod(n, 10)
    out = ["mười"] if tens == 1 else [DIGITS[tens], "mươi"]
    if unit == 0:
        return out
    if unit == 1 and tens > 1:
        return out + ["mốt"]
    if unit == 5:
        return out + ["lăm"]
    if unit == 4 and tens > 1:
        return out + ["tư"]
    return out + [DIGITS[unit]]


def number_words(n: int) -> list[str]:
    if n < 100:
        return _below_100(n)
    if n < 1000:
        h, rest = divmod(n, 100)
        out = [DIGITS[h], "trăm"]
        if rest == 0:
            return out
        if rest < 10:
            return out + ["lẻ", DIGITS[rest]]
        return out + _below_100(rest)
    if n < 1_000_000:
        k, rest = divmod(n, 1000)
        out = number_words(k) + ["nghìn"]
        if rest == 0:
            return out
        if rest < 100:
            return out + ["không", "trăm"] + (["lẻ", DIGITS[rest]] if rest < 10 else _below_100(rest))
        return out + number_words(rest)
    return [DIGITS[int(d)] for d in str(n)]  # long numbers: read digit by digit


def spoken(word: str) -> list[str]:
    """One written word -> the spoken tokens a listener should hear."""
    w = unicodedata.normalize("NFC", word.lower())
    m = re.fullmatch(r"(\d+)(?:[.,](\d+))?", w)
    if m:
        out = number_words(int(m.group(1)))
        if m.group(2):  # Vietnamese decimal comma: 2,5 -> "hai phẩy năm"
            out += ["phẩy"] + [DIGITS[int(d)] for d in m.group(2)]
        return out
    if len(w) == 1 and w in LETTERS:
        return LETTERS[w].split()
    return [w]


EN_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def en_number(n: int) -> list[str]:
    if n < 20:
        return [EN_ONES[n]]
    if n < 100:
        t, u = divmod(n, 10)
        return [EN_TENS[t]] + ([EN_ONES[u]] if u else [])
    if n < 1000:
        h, r = divmod(n, 100)
        return [EN_ONES[h], "hundred"] + (en_number(r) if r else [])
    if n < 1_000_000:
        k, r = divmod(n, 1000)
        return en_number(k) + ["thousand"] + (en_number(r) if r else [])
    return [EN_ONES[int(d)] for d in str(n)]


def spoken_en(word: str) -> list[str]:
    w = word.lower().replace("’", "'")
    m = re.fullmatch(r"(\d+)(?:\.(\d+))?", w)
    if m:
        out = en_number(int(m.group(1)))
        if m.group(2):
            out += ["point"] + [EN_ONES[int(d)] for d in m.group(2)]
        return out
    m = re.fullmatch(r"(\d+):(\d\d)", w)  # 7:50 -> seven fifty
    if m:
        return en_number(int(m.group(1))) + (en_number(int(m.group(2))) if int(m.group(2)) else ["o'clock"])
    return [w]


def tokens(text: str, lang: str = "vi") -> list[tuple[str, list[str]]]:
    """[(written_word, [spoken tokens...]), ...] in reading order."""
    text = unicodedata.normalize("NFC", text)
    out = []
    pattern = r"[\w'’:]+(?:[.,]\d+)?[.,:;!?…)]*|[(]" if lang == "en" else r"[\w]+(?:[.,]\d+)?[.,:;!?…)]*|[(]"
    for word in re.findall(pattern, text):
        clean = re.sub(r"^[(]+|[.,:;!?…)]+$", "", word)
        if not clean:
            continue
        out.append((word, spoken_en(clean) if lang == "en" else spoken(clean)))
    return out


def lint(say: str, lang: str = "vi") -> list[str]:
    """Problems that would make a line unspeakable or unscorable."""
    problems = []
    bad = sorted(set(UNSPEAKABLE.findall(say)) - ({"'"} if lang == "en" else set()))
    if bad:
        problems.append(
            f"has symbols the voice cannot read ({' '.join(bad)}): write them as words, "
            "e.g. y' -> 'y phẩy', -1 -> 'trừ 1', x^2 -> 'x bình phương'"
        )
    if len(say) > 220:
        problems.append(f"is {len(say)} characters; split it (max ~220, about 15 seconds)")
    if not say.strip():
        problems.append("is empty")
    return problems
