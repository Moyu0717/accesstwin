"""Planning Brief HTML + CSV export (spec section 5.8, M7)."""
from __future__ import annotations

import csv
import io
from html.parser import HTMLParser

import pytest

from accesstwin.core import store
from accesstwin.core.demand import suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import build_graph, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core import report
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import load_upgrades, rank_upgrades


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.text: list[str] = []
        self.mismatches: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("meta", "br", "img", "input", "link"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.mismatches.append(tag)

    def handle_data(self, data):
        self.text.append(data)


@pytest.fixture(scope="module")
def ctx():
    store.reset_demo()
    G = build_graph(load_township())
    P = load_personas()
    scores = compute_scores(G, P)
    upgrades = load_upgrades()
    ranking_op = rank_upgrades(G, upgrades, P, mode="operate")
    ranking_de = rank_upgrades(G, upgrades, P, mode="design")
    demand = suppressed_demand(G, P, camera_counts())
    reports = store.list_reports()
    return dict(G=G, P=P, scores=scores, ranking_op=ranking_op, ranking_de=ranking_de,
                demand=demand, reports=reports)


def _brief(ctx, mode="operate"):
    ranking = ctx["ranking_op"] if mode == "operate" else ctx["ranking_de"]
    return report.brief_html(ctx["G"], ctx["P"], ctx["scores"], ranking, ctx["demand"], ctx["reports"], mode=mode)


def test_brief_is_html_document_with_required_sections(ctx):
    doc = _brief(ctx)
    assert isinstance(doc, str)
    assert doc.startswith("<!doctype html>")
    # V2 rename: the brief's headline score is "Access Score" (higher is better).
    for needle in ("Access Score", "Top 5", "Suppressed", "E7", "planning aid"):
        assert needle in doc, needle


def test_brief_parses_without_errors(ctx):
    parser = _Collector()
    parser.feed(_brief(ctx))
    parser.close()
    assert parser.mismatches == []
    assert parser.stack == [], f"unclosed tags: {parser.stack}"


def test_design_mode_title_is_pre_construction(ctx):
    doc = _brief(ctx, mode="design")
    assert "<title>" in doc
    title = doc.split("<title>", 1)[1].split("</title>", 1)[0]
    assert "Pre-construction" in title


def test_ranking_csv_header_and_rows_operate(ctx):
    text = report.ranking_csv(ctx["ranking_op"])
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    assert header[:3] == ["rank", "id", "title"]
    assert len(rows) - 1 >= 6


def test_demand_csv_has_e7_row(ctx):
    text = report.demand_csv(ctx["demand"])
    rows = list(csv.DictReader(io.StringIO(text)))
    e7 = [r for r in rows if r["edge"] == "E7"]
    assert len(e7) == 1
    assert e7[0]["camera"] == "CAM_02"
    assert e7[0]["status"] == "Suppressed demand"


def test_report_stats_counts_by_status_and_type():
    reports = [
        {"status": "pending", "reporter_role": "resident", "ai": {"obstacle_type": "high_curb"}},
        {"status": "pending", "reporter_role": "guard", "ai": {"obstacle_type": "high_curb"}},
        {"status": "approved", "reporter_role": "resident", "ai": None},
    ]
    stats = report.report_stats(reports)
    assert stats["total"] == 3
    assert stats["by_status"] == {"pending": 2, "approved": 1}
    assert stats["by_type"] == {"high_curb": 2, "other": 1}
    assert stats["by_role"] == {"resident": 2, "guard": 1}
