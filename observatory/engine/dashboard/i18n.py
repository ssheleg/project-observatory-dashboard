#!/usr/bin/env python3
"""The dashboard's languages: English by default, Russian by choice.

ONE CATALOG, TWO READERS. The builder renders the pages in the workspace's
locale (`interface.locale` in `config/settings.json`, English when unset), and
the page script re-renders them in the reader's own choice without a rebuild —
so both read the same `locales/<locale>.json`, and a string the builder and the
script disagree on cannot exist.

THE MESSAGE ID IS THE ENGLISH TEXT. English needs no catalog of its own except
for plural forms; a missing translation falls back to English, visibly and
never to an empty string. `{name}` placeholders are filled from arguments, and
an entry whose value is an object is a plural: it is selected by the `n`
argument under the language's plural rules (CLDR categories, the same ones
`Intl.PluralRules` answers in the browser).

Elements a page carries in its static HTML are marked for the script:
`data-t="<msgid>"` for the text, `data-t-args` for its arguments, and
`data-t-<attribute>` for a translated attribute. `localize_markup` fills the
static template in the build locale and leaves those marks behind.
"""
from __future__ import annotations
import html
import json
import re
from functools import lru_cache
from pathlib import Path

LOCALES = ("en", "ru")
DEFAULT_LOCALE = "en"
#: What the language switch shows for each locale — its own name, in itself.
LOCALE_NAMES = {"en": "English", "ru": "Русский"}
LOCALE_DIR = Path(__file__).with_name("locales")
#: Attributes whose value is reader-facing text and is therefore translated.
TRANSLATED_ATTRIBUTES = ("aria-label", "placeholder", "title")
_PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class LocaleError(ValueError):
    """A locale that is not one of `LOCALES`."""


def check_locale(value: object) -> str:
    if value not in LOCALES:
        raise LocaleError(f"Unsupported interface locale {value!r}; use one of: {', '.join(LOCALES)}")
    return value  # type: ignore[return-value]


def resolve_locale(settings: dict | None) -> str:
    """The workspace's locale, or English. An invalid value is refused by
    `configuration.load` before it gets here; this only reads a valid one."""
    value = ((settings or {}).get("interface") or {}).get("locale")
    return value if value in LOCALES else DEFAULT_LOCALE


@lru_cache(maxsize=None)
def catalog(locale: str) -> dict:
    check_locale(locale)
    file = LOCALE_DIR / f"{locale}.json"
    doc = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise LocaleError(f"{file.name} must be an object")
    return {k: v for k, v in doc.items() if not k.startswith("//")}


def catalogs() -> dict[str, dict]:
    """Every catalog, as the page script receives it."""
    return {locale: catalog(locale) for locale in LOCALES}


def plural_category(locale: str, n: float) -> str:
    """CLDR cardinal categories for the two supported languages."""
    if locale == "ru":
        if n != int(n):
            return "other"
        i = abs(int(n))
        if i % 10 == 1 and i % 100 != 11:
            return "one"
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def format_number(value: float | int, locale: str) -> str:
    """Grouped digits the way `Number.toLocaleString(locale)` writes them:
    a comma in English, a no-break space in Russian."""
    text = f"{value:,}"
    return text.replace(",", " ") if locale == "ru" else text


#: `context@@text`: one English text that two languages need to tell apart
#: ("not measured" of a domain is masculine in Russian, of a date neuter). The
#: context is part of the id and never shown; English shows the text after it.
CONTEXT_SEPARATOR = "@@"


def english(msgid: str) -> str:
    return msgid.rsplit(CONTEXT_SEPARATOR, 1)[-1]


def translate(msgid: str, locale: str = DEFAULT_LOCALE, **args: object) -> str:
    entry = catalog(locale).get(msgid)
    if entry is None and locale != DEFAULT_LOCALE:
        entry = catalog(DEFAULT_LOCALE).get(msgid)
    if isinstance(entry, dict):
        n = args.get("n")
        form = plural_category(locale, float(n)) if isinstance(n, (int, float)) else "other"
        entry = entry.get(form) or entry.get("other") or msgid
    text = entry if isinstance(entry, str) else english(msgid)

    def fill(m: re.Match) -> str:
        key = m.group(1)
        if key not in args:
            return m.group(0)
        v = args[key]
        return format_number(v, locale) if isinstance(v, int) and not isinstance(v, bool) else str(v)
    return _PLACEHOLDER.sub(fill, text)


class Translator:
    """`t("...")` bound to one locale, for the builder's own strings."""

    def __init__(self, locale: str = DEFAULT_LOCALE):
        self.locale = check_locale(locale)

    def __call__(self, msgid: str, **args: object) -> str:
        return translate(msgid, self.locale, **args)

    def mark(self, msgid: str, tag: str = "span", attrs: str = "", **args: object) -> str:
        """An element whose text the page script can re-translate."""
        data = f' data-t-args="{html.escape(json.dumps(args, ensure_ascii=False))}"' if args else ""
        return (f'<{tag}{attrs} data-t="{html.escape(msgid)}"{data}>'
                f"{html.escape(self(msgid, **args))}</{tag}>")

    def attr(self, name: str, msgid: str) -> str:
        """` name="…" data-t-name="msgid"`: a translated attribute."""
        return f' {name}="{html.escape(self(msgid))}" data-t-{name}="{html.escape(msgid)}"'


_MARKED = re.compile(r'(<([a-z0-9]+)\b[^>]*?)\sdata-t>(.*?)(</\2>)', re.S)
_ATTR = re.compile(r'\s(' + "|".join(TRANSLATED_ATTRIBUTES) + r')="([^"]*)"')


def localize_markup(markup: str, locale: str) -> str:
    """Translate the static template: every `data-t` element's text and every
    reader-facing attribute, keeping the English msgid beside it.

    The template writes `<b data-t>Findings</b>`; this returns the element
    with `data-t="Findings"` and its Russian text in Russian, and the same
    English text with its mark in English. Text containing markup is not a message and is
    refused, so the template cannot hide a child element inside a msgid."""
    t = Translator(locale)

    def text(m: re.Match) -> str:
        start, _tag, body, end = m.groups()
        msgid = " ".join(body.split())
        if "<" in msgid:
            raise LocaleError(f"data-t element holds markup: {msgid[:60]!r}")
        return f'{start} data-t="{html.escape(msgid)}">{html.escape(t(html.unescape(msgid)))}{end}'

    def attribute(m: re.Match) -> str:
        name, value = m.groups()
        msgid = html.unescape(value)
        if not msgid or msgid.startswith("__") or not any(c.isalpha() for c in msgid):
            return m.group(0)
        return f' {name}="{html.escape(t(msgid))}" data-t-{name}="{html.escape(msgid)}"'

    out = _MARKED.sub(text, markup)
    head, sep, body = out.partition("<body>")
    if not sep:
        return _ATTR.sub(attribute, out)
    # Attributes are translated in the body only: the head carries none a
    # reader sees, and its inline script must not be rewritten.
    script_free = re.split(r"(<script\b.*?</script>)", body, flags=re.S)
    body = "".join(part if part.startswith("<script") else _ATTR.sub(attribute, part)
                   for part in script_free)
    return head + sep + body


def msgids_in_source(text: str) -> set[str]:
    """Every literal `T("…")`/`t("…")` message id in a source text — the
    completeness check reads the code, not a hand-kept list."""
    ids = set()
    for m in re.finditer(r'\b[Tt]\(\s*(["\'])((?:\\.|(?!\1).)*)\1', text):
        ids.add(bytes(m.group(2), "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8"))
    for m in re.finditer(r'\bdata-t="([^"]+)"', text):
        ids.add(html.unescape(m.group(1)))
    return ids
