"""PostgreSQL refuses a value longer than its column; SQLite does not, so the widths are checked here."""
import re
from pathlib import Path

from mrcourt.models import InboundMessage
from mrcourt.models.whatsapp import INBOUND_KIND_WIDTH, INBOUND_KINDS

SOURCE = Path(__file__).resolve().parents[2] / "src" / "mrcourt" / "services" / "whatsapp" / "inbound.py"


def test_every_kind_an_incoming_message_can_have_fits_its_column() -> None:
    assert InboundMessage.__table__.c.kind.type.length == INBOUND_KIND_WIDTH
    assert max(len(kind) for kind in INBOUND_KINDS) <= INBOUND_KIND_WIDTH


def test_the_kinds_the_code_assigns_are_all_listed() -> None:
    assigned = set(re.findall(r'row\.kind = "(\w+)"', SOURCE.read_text(encoding="utf-8")))
    assert assigned <= set(INBOUND_KINDS), assigned - set(INBOUND_KINDS)
