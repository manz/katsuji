from __future__ import annotations

from pathlib import Path

import pytest
from script import Table

from katsuji import Atlas

FF4 = Path(__file__).parent / "fixtures" / "ff4"


@pytest.fixture(scope="session")
def dialog_atlas() -> Atlas:
    return Atlas.open(FF4 / "vwf.png", cell_height=16)


@pytest.fixture(scope="session")
def dialog_table() -> Table:
    return Table(str(FF4 / "ff4fr.tbl"))
