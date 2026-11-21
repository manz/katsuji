"""The preview's HTML: the page, and the fragments htmx swaps into it."""

import base64
from collections.abc import Sequence
from dataclasses import asdict
from html import escape
from urllib.parse import quote

from katsuji.preview import View

SCALE = 3  # the sheet's pixels drawn this many screen pixels wide

STYLE = """
body { margin: 0; display: grid; grid-template-columns: 18rem 1fr; height: 100vh; font: 14px system-ui;
       background: #15151c; color: #ddd; }
nav { overflow-y: auto; border-right: 1px solid #333; padding: .5rem; }
nav input { width: 100%; box-sizing: border-box; margin-bottom: .5rem; }
nav a { display: flex; justify-content: space-between; color: #ccd; text-decoration: none; padding: .1rem .3rem; }
nav a:hover { background: #2a2a38; }
main { overflow-y: auto; padding: 1rem; display: grid; grid-template-columns: minmax(20rem, 1fr) auto; gap: 1rem;
       align-content: start; }
textarea { width: 100%; height: 16rem; font: 14px ui-monospace, monospace; background: #1d1d27; color: #eee; }
pre.original { white-space: pre-wrap; color: #99a; }
img { image-rendering: pixelated; }
.fault { color: #ff6060; }
.flaw { display: inline-block; margin: .1rem .3rem 0 0; padding: 0 .4rem; border-radius: .6rem; background: #33334a; }
.better { color: #6c6; } .worse { color: #f66; }
"""


def page(listing: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>katsuji preview</title>
<script src="/static/htmx.min.js"></script><style>{STYLE}</style></head>
<body>
<nav>
  <input type="search" name="q" placeholder="key or text" hx-get="/messages" hx-trigger="input changed delay:300ms"
         hx-target="#messages" hx-include="[name=sort]">
  <label><input type="checkbox" name="sort" value="cost" hx-get="/messages" hx-target="#messages"
         hx-include="[name=q]"> worst first</label>
  <div id="messages">{listing}</div>
</nav>
<main id="editor"><p>Pick a message.</p></main>
</body></html>"""


def listing(items: Sequence[tuple[str, int | None]]) -> str:
    return "\n".join(
        f'<a href="#" hx-get="/message?key={quote(key)}" hx-target="#editor">'
        f"<span>{escape(key)}</span><span>{'' if cost is None else cost}</span></a>"
        for key, cost in items
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
