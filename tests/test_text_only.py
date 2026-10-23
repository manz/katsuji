"""Without the `render` extra: the text side imports, the command line says what is missing."""

import subprocess
import sys

import pytest

# numpy and pillow made unimportable, as in an install without katsuji[render]
BLOCKED = "import sys; sys.modules.update(numpy=None, PIL=None); "


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", BLOCKED + code], capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    "module",
    ["katsuji", "katsuji.script", "katsuji.typeset", "katsuji.wrap", "katsuji.layout", "katsuji.codecs.sdd1"],
)
def test_text_modules_import_without_render(module: str) -> None:
    assert run(f"import {module}").stderr == ""


def test_the_command_line_names_the_render_extra() -> None:
    result = run("from katsuji.cli import main; raise SystemExit(main(['build', 'x.toml']))")
    assert (result.returncode, "katsuji[render]" in result.stderr) == (2, True)
