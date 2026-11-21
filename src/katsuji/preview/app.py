"""The preview's routes: the page, then the fragments htmx asks for."""

import importlib
import sys
from pathlib import Path
from urllib.parse import parse_qs

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from katsuji.preview import DialogGame, Preview, html

STATIC = Path(__file__).parent / "static"
HOST = "127.0.0.1"  # it writes the game's files: never on the network
PORT = 8732


def app(game: DialogGame) -> Starlette:
    preview = Preview(game)

    async def index(request: Request) -> HTMLResponse:
        return HTMLResponse(html.page(html.listing(preview.listing())))

    async def messages(request: Request) -> HTMLResponse:
        query = request.query_params
        return HTMLResponse(html.listing(preview.listing(query.get("q", ""), query.get("sort") == "cost")))

    async def message(request: Request) -> HTMLResponse:
        key = request.query_params["key"]
        text = game.text(key)
        shown = html.view(preview.view(key, text), preview.cost(key))
        return HTMLResponse(html.editor(key, text, game.original(key), shown))

    async def show(request: Request) -> HTMLResponse:
        key, text = await _form(request)
        return HTMLResponse(html.view(preview.view(key, text), preview.cost(key)))

    async def save(request: Request) -> HTMLResponse:
        key, text = await _form(request)
        saved = preview.cost(key)
        return HTMLResponse(html.view(preview.save(key, text), saved, "saved"))

    return Starlette(
        routes=[
            Route("/", index),
            Route("/messages", messages),
            Route("/message", message),
            Route("/preview", show, methods=["POST"]),
            Route("/save", save, methods=["POST"]),
            Mount("/static", StaticFiles(directory=STATIC)),
        ]
    )


async def _form(request: Request) -> tuple[str, str]:
    """The key and text htmx posts, url-encoded (read here: starlette's `form` needs python-multipart)."""
    fields = parse_qs((await request.body()).decode(), keep_blank_values=True)
    return fields["key"][0], fields["text"][0]


def load(target: str) -> DialogGame:
    """The game `module:attribute` names, from the current directory: the attribute itself, or what calling it
    makes when it is a function."""
    module, _, attribute = target.partition(":")
    if not attribute:
        raise ValueError(f"{target!r}: name the game as module:attribute (tools.preview:game)")
    sys.path.insert(0, str(Path.cwd()))
    found = getattr(importlib.import_module(module), attribute)
    game: DialogGame = found() if callable(found) else found
    return game


def serve(target: str, port: int = PORT) -> None:
    import uvicorn

    uvicorn.run(app(load(target)), host=HOST, port=port)
