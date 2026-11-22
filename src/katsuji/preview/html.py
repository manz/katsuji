"""The preview's HTML: the page, and the fragments htmx swaps into it."""

import base64
from collections.abc import Sequence
from dataclasses import asdict
from html import escape
from urllib.parse import quote

from katsuji.preview import Row, Scene, View

SCALE = 3  # the sheet's pixels drawn this many screen pixels wide
BADGES = (("faults", "!", "fault"), ("dangles", "⤶", "dangle"), ("carried", "…", "carried"), ("tails", "¬", "tail"))

STYLE = """
body { margin: 0; display: grid; grid-template-columns: 26rem 1fr; height: 100vh; font: 14px system-ui;
       background: #15151c; color: #ddd; }
nav { overflow-y: auto; border-right: 1px solid #333; padding: .5rem; }
nav input[type=search] { width: 100%; box-sizing: border-box; margin-bottom: .3rem; }
nav details { margin-left: .6rem; }
nav summary { cursor: pointer; padding: .1rem 0; display: flex; gap: .4rem; }
nav summary .title { flex: 1; }
nav a { display: grid; grid-template-columns: 4.5rem 1fr auto 2.5rem; gap: .4rem; color: #ccd; text-decoration: none;
        padding: .1rem .3rem; margin-left: .6rem; }
nav a:hover { background: #2a2a38; }
.key { color: #889; } .snippet { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cost { text-align: right; color: #aab; } .count { color: #778; }
.badge { font-size: 11px; padding: 0 .3rem; border-radius: .5rem; background: #33334a; }
.badge.fault { background: #6a2020; } .badge.dangle { background: #5a4a18; }
main { overflow-y: auto; padding: 1rem; display: grid; grid-template-columns: minmax(20rem, 1fr) auto; gap: 1rem;
       align-content: start; }
textarea { width: 100%; height: 16rem; font: 14px ui-monospace, monospace; background: #1d1d27; color: #eee; }
pre.original { white-space: pre-wrap; color: #99a; }
img { image-rendering: pixelated; }
p.fault { color: #ff6060; }
.flaw { display: inline-block; margin: .1rem .3rem 0 0; padding: 0 .4rem; border-radius: .6rem; background: #33334a; }
.better { color: #6c6; } .worse { color: #f66; }
"""


def page(listing: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>katsuji preview</title>
<script src="/static/htmx.min.js"></script><style>{STYLE}</style></head>
<body>
<nav>
  <input type="search" name="q" placeholder="key or text (empty: by scene)" hx-get="/messages"
         hx-trigger="input changed delay:300ms" hx-target="#messages" hx-include="[name=sort]">
  <label><input type="checkbox" name="sort" value="cost" hx-get="/messages" hx-target="#messages"
         hx-include="[name=q]"> worst first</label>
  <div id="messages">{listing}</div>
</nav>
<main id="editor"><p>Pick a message.</p></main>
</body></html>"""


def tree(scenes: Sequence[tuple[str, Scene]], totals: Sequence[Row] | None = None) -> str:
    """Scenes to open, each loading its inside when opened; with `totals`, each with its messages summed up."""
    return "\n".join(
        _scene(path, scene, totals[index] if totals else None) for index, (path, scene) in enumerate(scenes)
    )


def _scene(path: str, scene: Scene, total: Row | None) -> str:
    count = len(set(scene.all_keys()))
    summed = f"{badges(total)}<span class='cost'>{total.cost}</span>" if total else ""
    return (
        f'<details hx-get="/scene?path={path}" hx-trigger="toggle once" hx-target="find .inside">'
        f'<summary><span class="title">{escape(scene.title)}</span>{summed}<span class="count">{count}</span></summary>'
        f'<div class="inside"></div></details>'
    )


def rows(listed: Sequence[Row]) -> str:
    return "\n".join(
        f'<a href="#" hx-get="/message?key={quote(row.key)}" hx-target="#editor" title="{escape(row.snippet)}">'
        f'<span class="key">{escape(row.key)}</span><span class="snippet">{escape(row.snippet)}</span>'
        f"<span>{badges(row)}</span><span class='cost'>{'' if row.cost is None else row.cost}</span></a>"
        for row in listed
    )


def badges(row: Row) -> str:
    """A badge per kind of trouble the row has: its faults, then its worst flaws."""
    counts = {"faults": row.faults, **asdict(row.flaws)}
    return "".join(
        f'<span class="badge {kind}" title="{name}">{mark}{counts[name]}</span>'
        for name, mark, kind in BADGES
        if counts[name]
    )


def editor(key: str, text: str, original: str | None, view: str) -> str:
    beside = f'<pre class="original">{escape(original)}</pre>' if original else ""
    return f"""<section>
<h3>{escape(key)}</h3>
<form hx-post="/preview" hx-trigger="input changed delay:300ms from:textarea" hx-target="#view">
  <input type="hidden" name="key" value="{escape(key)}">
  <textarea name="text">{escape(text)}</textarea>
  <button hx-post="/save" hx-target="#view">Save</button>
</form>
{beside}
</section>
<section id="view">{view}</section>"""


def view(shown: View, saved: int, note: str = "") -> str:
    """The windows, then their faults and flaws, then the cost against the saved text's."""
    image = base64.b64encode(shown.png).decode()
    faults = "".join(f'<p class="fault">{escape(fault)}</p>' for fault in shown.faults)
    flaws = "".join(f'<span class="flaw">{name} {count}</span>' for name, count in asdict(shown.flaws).items() if count)
    delta = shown.cost - saved
    trend = "better" if delta < 0 else "worse" if delta > 0 else ""
    cost = f'<p>cost {shown.cost} <span class="{trend}">({delta:+d} on saved)</span> {escape(note)}</p>'
    return f'<img src="data:image/png;base64,{image}" style="zoom: {SCALE}">{faults}<p>{flaws}</p>{cost}'
