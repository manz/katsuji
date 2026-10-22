from pathlib import Path

import pytest

from katsuji import Atlas
from katsuji.script import Table

FF4 = Path(__file__).parent / "fixtures" / "ff4"


@pytest.fixture(scope="session")
def dialog_atlas() -> Atlas:
    return Atlas.open(FF4 / "vwf.png", cell_height=16)


@pytest.fixture(scope="session")
def dialog_table() -> Table:
    return Table(str(FF4 / "ff4fr.tbl"))
