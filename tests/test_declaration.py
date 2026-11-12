"""What the version declares: a dataset per GSE, each the factors with their
optional fields, pulled and pushed daily, with no default licence (rulings
1030 to 1032); the files' storage; and its two roles."""

from __future__ import annotations

import tomllib
from pathlib import Path

from gse_disclosures.declaration import CATALOGUE, DECLARATION


def test_a_dataset_per_gse() -> None:
    assert [d.key for d in CATALOGUE] == ["fannie_mae", "freddie_mac"]
    assert [d.vendor for d in CATALOGUE] == ["Fannie Mae", "Freddie Mac"]
    for declared in CATALOGUE:
        assert declared.data_types[0] == "meridian.v1.Factor"
        # Contract 30 (ruling 1032): each agency's terms in words, never a licence.
        assert declared.vendor in declared.terms_and_pricing
        assert declared.gap_recovery == "backfill" and not declared.sessions_calendar_id
        assert declared.cadence == 86_400 and declared.history == 396
        assert not declared.aggregator and not declared.venue_id and not declared.calendar_id


def test_its_roles_and_declaration() -> None:
    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert project["tool"]["meridian"]["roles"] == ["data", "reference"]
    assert project["project"]["dependencies"] == ["open-meridian==0.36.0"]
    assert DECLARATION.documentation == "docs"
