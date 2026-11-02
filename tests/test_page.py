"""The two pages, as an admin of the plugin sees them, and their read tools."""

from __future__ import annotations

from meridian.testing import PageClient

from gse_disclosures import page
from gse_disclosures.preview import render


def test_the_pages_render_on_sample_data() -> None:
    connection = render("connection")
    assert "Sample data" in connection and "Files" in connection
    datasets = render("datasets")
    assert "gse-disclosures:fannie_mae" in datasets and "gse-disclosures:freddie_mac" in datasets


def test_the_pages_render_before_anything_runs() -> None:
    page.running.clear()
    client = PageClient(page.pages)
    assert client.get("/", "admin").status == 200
    assert client.get("/datasets", "admin").status == 200


def test_each_page_is_a_read_tool_at_admin() -> None:
    client = PageClient(page.pages)
    assert client.get("/", "read").status in (403, 404)
