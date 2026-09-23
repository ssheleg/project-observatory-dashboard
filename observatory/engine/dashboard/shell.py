#!/usr/bin/env python3
"""The dashboard's shell: which pages exist, how they are linked, what each carries.

One page of 1.3 MB with seven tabs was the whole surface until 2026-09-14, and
the operator's verdict was that it could not be used: alerts above navigation,
one `main` for seven subjects, nothing addressable, everything loaded for
anything (plan v2, M1; scenario S12). The split keeps ONE template and ONE
script — every page is the same HTML with a `PAGE` constant, a navigation bar
in place of the tab strip, and only the DATA that page renders — so nothing is
rendered twice by two code paths, and a fix to a renderer reaches every page.

`docs/projects-dashboard.html` stays as the full single page (the tests, the
smoke harness and the design checks read it), and `docs/dashboard/*.html` are
the pages a person opens. Both come from `build_dashboard.py` in one run.
"""
from __future__ import annotations
import json
import re

#: (name, title, kind). `table` pages render one of the tab renderers into
#: `#out`; the three others show the shell's own sections. Order is the nav
#: order: the overview first, then what needs a person most often.
PAGES: tuple[tuple[str, str, str], ...] = (
    ("index",    "Обзор",     "index"),
    ("findings", "Находки",   "findings"),
    ("projects", "Проекты",   "table"),
    ("domains",  "Домены",    "table"),
    ("heroku",   "Heroku",    "table"),
    ("creds",    "Ключи",     "table"),
    ("env",      "ENV",       "table"),
    ("mcp",      "MCP",       "table"),
    ("traffic",  "Трафик",    "table"),
    ("health",   "Здоровье",  "health"),
)
#: THE QUESTION EACH PAGE ANSWERS, in the reader's words (IS-01/IS-02; backlog
#: D-03). Nine pages shared one `<title>` and one `<h1>` until 2026-09-14: a
#: browser tab, a bookmark and the history could not tell them apart, and no
#: page said what it showed or over what scope. The sentence is the page's own
#: heading; the measurement stamp follows it on every page.
QUESTIONS: dict[str, str] = {
    "index":    "Что требует человека сегодня, и куда двинулся эстейт.",
    "findings": "Всё открытое на доске — по важности и по типу; заглушенное отдельно.",
    "projects": "Каждый проект эстейта: из чего состоит, что с ним происходило, кто его ведёт.",
    "domains":  "Каждое имя, которым эстейт владеет: чьё оно, отвечает ли, где смотреть.",
    "heroku":   "Где живёт прод, что он стоит, и с чем он сконфигурирован.",
    "creds":    "Каждый ключ: его дверь, состояние, кто им пользуется, для чего он.",
    "env":      "Что лежит в рабочих копиях по проектам, что общее, и что у прода.",
    "mcp":      "Какие MCP-серверы объявлены у агентов, и отвечают ли они.",
    "traffic":  "Сколько людей приходит в каждый продукт, и к какому проекту привязана каждая property.",
    "health":   "Смотрит ли обсерватория ещё, и что ждёт решения человека.",
}
TITLE_SUFFIX = "Обсерватория"
NAMES = tuple(p[0] for p in PAGES)
TABLE_PAGES = tuple(p[0] for p in PAGES if p[2] == "table")

#: What a lite project row keeps on pages that only look projects UP — the
#: domains page names a project, the creds page names an owner — but never
#: render the table. Everything else in a row is the projects page's business.
LITE_ROW_KEYS = ("id", "name", "anchor", "products", "tier", "lifecycle")


def nav_html(page: str, counts: dict[str, int | str]) -> str:
    """The top bar: brand, the nine pages with their badges, the theme control.

    Sticky and first in the document (S12; backlog D-05): on a long table the
    way out must not scroll away. The theme control is three buttons rather
    than a toggle because «система» is a real third state — it follows the OS
    and re-follows it — and a two-state switch would have to lie about one of
    the three.
    """
    items = []
    for name, title, _kind in PAGES:
        n = counts.get(name)
        badge = f' <span class="n">{n}</span>' if n not in (None, "") else ""
        cur = ' aria-current="page"' if name == page else ""
        items.append(f'<a class="pg" href="{name}.html"{cur}>{title}{badge}</a>')
    theme = ('<div class="theme" role="group" aria-label="Тема">'
             '<button type="button" data-mode="system" aria-pressed="false" title="как в системе">система</button>'
             '<button type="button" data-mode="light" aria-pressed="false">светлая</button>'
             '<button type="button" data-mode="dark" aria-pressed="false">тёмная</button></div>')
    return ('<div class="topbar" id="topbar">'
            f'<a class="brand" href="index.html">{TITLE_SUFFIX}</a>'
            '<nav class="pages" id="pages" aria-label="Разделы">' + "".join(items) + "</nav>"
            + theme + "</div>")


def counts_of(payload: dict) -> dict[str, int | str]:
    """The badge beside each page name — computed once, carried by every page,
    so a page that holds no rows of a kind still says how many exist."""
    f = payload.get("findings") or {}
    c = (f.get("counts") or {}) if f else {}
    open_findings = sum(v for k, v in c.items() if k in ("critical", "warning", "info"))
    heroku = payload.get("heroku") or {}
    mcp = payload.get("mcp") or {}
    env = payload.get("env") or {}
    creds = payload.get("creds") or {}
    # THE INDEX AND HEALTH BADGES ARE THE TWO NUMBERS A PERSON OPENS FOR (D-05):
    # what is critical, and what waits for them. Zero is shown as nothing — a
    # «0» beside «Обзор» is noise, an absent badge is calm.
    health = payload.get("health") or {}
    return {
        "index": c.get("critical") or "",
        "health": health.get("proposed") or "",
        "findings": open_findings or "",
        "projects": len(payload.get("rows") or []),
        "domains": len({d["name"] for d in payload.get("domains") or []}
                       | {z["name"] for z in payload.get("zones") or []}),
        "heroku": len(heroku.get("apps") or []) if heroku else "",
        "creds": len(creds.get("credentials") or []) if creds else "",
        "env": ((env.get("totals") or {}).get("secrets") if env else "") or "",
        "mcp": (mcp.get("totals") or {}).get("distinct_servers", "") if mcp else "",
        "traffic": ((payload.get("google") or {}).get("totals") or {}).get("properties", "") or "",
    }


def _observer(health: dict) -> str:
    """The three states the health row spells apart, in three words: -1 is off
    (a choice, not a fault), a fresh receipt is alive, an old one is silence."""
    age = health.get("server_age_s")
    if not isinstance(age, (int, float)):
        return "наблюдатель не измерен"
    if age == -1:
        return "наблюдатель не запущен"
    if age < 90:
        return "наблюдатель жив"
    return f"наблюдатель молчит {int(age // 60)} мин"


def _traffic_line(payload: dict) -> str:
    """Users over thirty days, and how much of it nothing claims — because the
    second number is the one that decides whether the first can be trusted."""
    g = payload.get("google") or {}
    tt = g.get("totals") or {}
    if not g:
        return "аналитика не сканировалась"
    users = tt.get("users_30d") or 0
    loose = tt.get("users_30d_unclaimed") or 0
    return (f"{users:,}".replace(",", " ") + " польз./30 дн"
            + (f" · {loose:,}".replace(",", " ") + " без проекта" if loose else ""))


def cards_html(payload: dict, counts: dict) -> str:
    """The index page's module cards: one sentence each, the number, the link."""
    stats = payload.get("stats") or {}
    health = payload.get("health") or {}
    lines = {
        "projects": f"{counts['projects']} проектов · "
                    f"{stats.get('проектов в работе, 7 дн', 0)} в работе за неделю",
        "findings": f"{counts['findings'] or 0} открытых",
        "domains": f"{counts['domains']} имён · зон Cloudflare {len(payload.get('zones') or [])}",
        "heroku": f"{counts['heroku'] or 0} приложений",
        "creds": f"{counts['creds'] or 0} записей",
        "env": f"{counts['env'] or 0} секретных переменных",
        "mcp": f"{counts['mcp'] or 0} серверов",
        "traffic": _traffic_line(payload),
        # TWO NUMBERS, because one of them is the reason to open the page: the
        # observer's state, and how many rows are waiting for a person (S4/F9).
        "health": (_observer(health) + f" · ждут решения {health.get('proposed', 0)}"),
    }
    cards = []
    for name, title, _kind in PAGES:
        if name == "index":
            continue
        cards.append(f'<a class="card mod" href="{name}.html"><b>{title}</b>'
                     f'<span class="anchor">{lines.get(name, "")}</span></a>')
    return '<section class="mods" id="mods" aria-label="Разделы">' + "".join(cards) + "</section>"


def slice_for(page: str, payload: dict) -> dict:
    """Everything small, and only the HEAVY document a page renders.

    The first cut kept only what each page draws and every page but two threw
    at load: the script reads `D.dups`, `D.events` and friends unconditionally
    before any renderer runs. So the slice is the whole payload minus the
    heavy parts — full project rows on the projects page only (lite rows
    elsewhere, for lookups), and each provider document only on its page.
    """
    # `google` is the whole property inventory and belongs to its own page;
    # `traffic` is the per-project summary — a number and a link or two — and is
    # small enough to ride everywhere, which is what the projects column and the
    # project panel read.
    heavy = {"env": "env", "heroku": "heroku", "creds": "creds", "mcp": "mcp",
             "google": "traffic"}
    out = dict(payload)
    # WHAT PRODUCTION HOLDS is read by exactly the two pages that can say
    # something about it: the Heroku row and the ENV row.
    if page not in ("heroku", "env"):
        out["remote"] = None
    # The per-project key map feeds the project PANEL, which opens on the
    # projects page alone; 319 rows of names rode onto every page and pushed the
    # index to 133 KB before this line.
    if page != "projects":
        out["keys"] = None
    if page != "projects":
        out["rows"] = [{k: r.get(k) for k in LITE_ROW_KEYS} for r in payload.get("rows") or []]
    for key, owner in heavy.items():
        if page != owner:
            out[key] = None
    if page != "domains":
        out["zones"] = None
        out["domains"] = []
    if page not in ("index", "findings"):
        out["findings"] = None
    if page != "health":
        out["queue"] = []
        # `health.wallet` is 85 KB of provider and model listings that only the
        # health page draws; every other page reads the wallet's scalars.
        h = dict(payload.get("health") or {})
        w = h.get("wallet")
        if isinstance(w, dict):
            h["wallet"] = {k: v for k, v in w.items() if not isinstance(v, (list, dict))}
            h["wallet"]["_on_health_page"] = True
        out["health"] = h
    if page == "index" and payload.get("findings"):
        # THE INDEX SHOWS WHAT NEEDS A PERSON NOW (S12): the counts, the
        # criticals, and a link to the rest. The findings page carries all.
        f = dict(payload["findings"])
        items = f.get("items") or []
        f["items"] = [{**x, "detail": ""} for x in items
                      if x.get("severity") == "critical"]
        f["folded_by_type"] = {}
        f["elsewhere"] = len(items) - len(f["items"])
        out["findings"] = f
    return out


#: Where the split pages keep the style and the script they all share. The
#: single page keeps both inline — it is read by `design` and `smoke` as one
#: file, and a self-contained page is the thing those checks check.
ASSET_CSS = "app.css"
ASSET_JS = "app.js"
#: The line in the template after which everything is shared. Above it live
#: `PAGE`, `TABLE_PAGES` and `D` — the three things that differ per page.
SHARED_FROM = "// __SHARED_BELOW__"


def split_template(template: str) -> tuple[str, str, str]:
    """(page template, the shared CSS, the shared JS).

    WHY THE SPLIT. Inlined, the style and the script are 114 KB of the 154 KB
    a page weighs, and nine pages carried nine copies — re-parsed on every
    navigation, which is the cost the split was supposed to remove. As two
    sibling files they are fetched once and served from cache thereafter, and
    an index that holds only its own data drops to ~45 KB (plan v2, T-02 DoD).
    Both are classic (non-module) subresources next to the page, so `file://`
    loads them like any browser loads a stylesheet — no fetch, no CORS.
    """
    o, c = template.index("<style>"), template.index("</style>")
    css = template[o + len("<style>"):c]
    page = (template[:o] + f'<link rel="stylesheet" href="{ASSET_CSS}">'
            + template[c + len("</style>"):])
    o = page.rindex("<script>") + len("<script>")
    c = page.rindex("</script>")
    body = page[o:c]
    cut = body.index(SHARED_FROM)
    page = (page[:o] + body[:cut] + '</script>\n'
            + f'<script src="{ASSET_JS}"></script>'
            + page[c + len("</script>"):])
    return page, css, body[cut:]


def page_html(template: str, page: str, payload: dict) -> str:
    counts = counts_of(payload)
    data = json.dumps(slice_for(page, payload), ensure_ascii=False)
    title = dict((n, tt) for n, tt, _k in PAGES)[page]
    # D-20: the single page's tab strip is dead markup on a split
    # page — CSS hid it, the DOM still carried six buttons and six counters, and
    # `drawTab` wrote into them on every render. Stripped at build; the script
    # asks before writing a counter (`setN`), so the single page keeps its strip.
    template = re.sub(r'<nav class="tabs"[^>]*>.*?</nav>\s*', "", template, count=1, flags=re.S)
    return (template.replace("__PAGE__", page)
            .replace("__TITLE__", f"{title} — {TITLE_SUFFIX}")
            .replace("__H1__", title)
            .replace("__SUB__", QUESTIONS.get(page, ""))
            .replace("__NAV__", nav_html(page, counts))
            .replace("__CARDS__", cards_html(payload, counts) if page == "index" else "")
            .replace("__DATA__", data.replace("</", "<\\/")))
