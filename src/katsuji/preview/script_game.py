"""A game previewed from its script dumps: `sn:script` files and the `scenes.xml` its walker writes.

`scenes.xml` says where the messages are said, the places first:

    <sn:scenes xmlns:sn="http://snes.ninja/ScriptNS">
      <sn:scene place="14:2">                 <!-- titled by place-title message 14:2: Hikage -->
        <sn:scene title="map $30">
          <sn:scene title="object 12 · talk">
            <sn:say ref="48:5"/><sn:say ref="48:6"/>   <!-- in the order the script says them -->

A scene is titled by the game's own place-title message (`place`, its translation then its original, tags taken
out), or by `title`. A message no scene says, not `unused` and showing no other (`shows`), is listed after them by file.

`ScriptGame` does the script's side of `DialogGame` (messages, text, original, save, scenes); the game gives how a
message is set and drawn (`frame`) and laid out (`lay`), each given the message and its attributes.
"""

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from katsuji.flow import Laid
from katsuji.preview import Frame, Scene
from katsuji.script import sn

NS = "{http://snes.ninja/ScriptNS}"
LEFT = "Not in a scene"


@dataclass
class ScriptGame:
    """The messages of the `sn:script` files in `translated` (their originals in `untranslated`), keyed by `key`
    ("{file}:{id}", or "{id}" when ids are unique across files), placed by `scenes_file`."""

    translated: Path
    framing: Callable[[sn.Message], Frame]
    laying: Callable[[sn.Message, str], Laid]
    untranslated: Path | None = None
    scenes_file: Path | None = None
    key: str = "{file}:{id}"
    loaded: dict[str, sn.Message] = field(default_factory=dict)
    originals: dict[str, sn.Message] = field(default_factory=dict)

    def messages(self) -> list[str]:
        return list(self._messages())

    def text(self, key: str) -> str:
        found = self._messages().get(key)
        return found.text if found else ""

    def original(self, key: str) -> str | None:
        found = self._originals().get(key)
        return found.text if found else None

    def save(self, key: str, text: str) -> None:
        message = self.message(key)
        sn.write(self.translated / f"{message.file}.xml", message.id, text)
        self.loaded[key] = sn.Message(message.file, message.id, text, message.attributes)

    def frame(self, key: str) -> Frame:
        return self.framing(self.message(key))

    def lay(self, key: str, text: str) -> Laid:
        return self.laying(self.message(key), text)

    def message(self, key: str) -> sn.Message:
        """The message at `key`; one the translation lacks, from its original's file and id, without text."""
        if key in self._messages():
            return self.loaded[key]
        message = self._originals()[key]
        return sn.Message(message.file, message.id, "", message.attributes)

    def scenes(self) -> list[Scene]:
        """`scenes_file`'s scenes, then the messages none says, by file."""
        placed: list[Scene] = []
        if self.scenes_file and self.scenes_file.exists():
            root = ElementTree.parse(self.scenes_file).getroot()
            placed = [self._scene(element) for element in root.findall(f"{NS}scene")]
        said = {key for scene in placed for key in scene.all_keys()}
        left = [message for key, message in self._messages().items() if key not in said and _listed(message)]
        return [*placed, *([Scene(LEFT, scenes=_by_file(left, self._key))] if left else [])]

    def _scene(self, element: ElementTree.Element) -> Scene:
        keys = tuple(say.attrib["ref"] for say in element.findall(f"{NS}say"))
        inner = tuple(self._scene(child) for child in element.findall(f"{NS}scene"))
        return Scene(self._title(element), keys, inner)

    def _title(self, element: ElementTree.Element) -> str:
        place = element.get("place")
        if place is None:
            return element.get("title", "")
        tag = self.frame(place).judge.layout.markup.tag if place in self._known() else r"\[[^\]]*\]"
        name, original = (
            re.sub(tag, "", text, flags=re.IGNORECASE) for text in (self.text(place), self.original(place) or "")
        )
        if not name:
            return original or element.get("title", place)
        return f"{name} · {original}" if original and original != name else name

    def _known(self) -> set[str]:
        return self._messages().keys() | self._originals().keys()

    def _messages(self) -> dict[str, sn.Message]:
        if not self.loaded:
            self.loaded = {self._key(message): message for message in _read_all(self.translated)}
        return self.loaded

    def _originals(self) -> dict[str, sn.Message]:
        if not self.originals:
            self.originals = {self._key(message): message for message in _read_all(self.untranslated)}
        return self.originals

    def _key(self, message: sn.Message) -> str:
        return self.key.format(file=message.file, id=message.id)


def _read_all(folder: Path | None) -> Iterator[sn.Message]:
    if folder is None:
        return
    for path in sorted(folder.glob("*.xml")):
        yield from sn.read(path)


def _listed(message: sn.Message) -> bool:
    """A message to list where no scene says it: one shown, and in its own right."""
    return message.attributes.get("unused") != "1" and "shows" not in message.attributes


def _by_file(messages: Sequence[sn.Message], key: Callable[[sn.Message], str]) -> tuple[Scene, ...]:
    files: dict[str, list[str]] = {}
    for message in messages:
        files.setdefault(message.file, []).append(key(message))
    return tuple(Scene(file, tuple(keys)) for file, keys in files.items())
