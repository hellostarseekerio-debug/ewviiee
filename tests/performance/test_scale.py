"""Performance/load tests simulating an office's accumulated document
history (thousands of rows) and a large rule set. These insert data
directly at the database layer (not through OCR/PDF processing, which is
I/O- and CPU-bound in ways unrelated to this codebase's own logic) so they
run quickly in CI while still exercising the exact code paths - indexing,
search query construction, fuzzy matching - that would slow down under
real volume.

Thresholds here are deliberately generous (an order of magnitude above
what a modest office server should need) - the goal is to catch a
regression that makes something scale quadratically or worse, not to
micro-benchmark. Each test seeds its own data (rather than sharing a
module-scoped fixture) so it composes cleanly with the per-test database
isolation in `tests/conftest.py`.
"""
from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timedelta

from app.core.database import init_db, session_scope
from app.core.models import Document, DocumentStatus
from app.rules.engine import RuleEngine
from app.rules.schema import District, Estate, RuleSet
from app.search.query import SearchFilters, search_documents

DOCUMENT_COUNT = 5000

_DISTRICTS = ["Kwun Tong", "Wong Tai Sin", "Sha Tin", "Kwai Tsing", "Tuen Mun"]
_ESTATES = [f"Test Estate {i}" for i in range(50)]


def _seed_documents(session, count: int) -> None:
    base_time = datetime.utcnow() - timedelta(days=365)
    rows = []
    for i in range(count):
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "filename": f"document_{i}.pdf",
                "source_path": f"/data/import/document_{i}.pdf",
                "document_type": "application_pdf",
                "workflow_name": "housing_estate_poster",
                "status": random.choice(list(DocumentStatus)),
                "district": random.choice(_DISTRICTS),
                "estate": random.choice(_ESTATES),
                "politician": f"Councillor {i % 200}",
                "reference_number": f"HEP-{i:06d}",
                "document_date": base_time + timedelta(hours=i),
                "ocr_text": f"Sample OCR text for document {i} mentioning {random.choice(_ESTATES)}",
                "created_at": base_time + timedelta(hours=i),
                "updated_at": base_time + timedelta(hours=i),
            }
        )
    session.bulk_insert_mappings(Document, rows)


def _seeded_db() -> None:
    """Each test's autouse fixture already points at a fresh, isolated
    SQLite file - just create the schema and seed it."""
    init_db()
    with session_scope() as session:
        _seed_documents(session, DOCUMENT_COUNT)


def test_bulk_insert_of_thousands_of_documents_is_fast():
    init_db()

    start = time.perf_counter()
    with session_scope() as session:
        _seed_documents(session, DOCUMENT_COUNT)
    elapsed = time.perf_counter() - start

    with session_scope() as session:
        assert session.query(Document).count() == DOCUMENT_COUNT

    # Generous ceiling: bulk-inserting 5,000 rows should take well under a
    # few seconds on any machine capable of running this office's workload.
    assert elapsed < 10.0, f"Bulk insert of {DOCUMENT_COUNT} rows took {elapsed:.2f}s"


def test_search_by_district_and_estate_is_fast():
    _seeded_db()

    with session_scope() as session:
        start = time.perf_counter()
        results, total = search_documents(
            session, SearchFilters(district="Kwun Tong", estate="Test Estate 5", limit=50)
        )
        elapsed = time.perf_counter() - start

    assert total >= 0
    assert elapsed < 1.0, f"Filtered search took {elapsed:.2f}s over {DOCUMENT_COUNT} rows"


def test_search_ordered_listing_is_fast():
    """Exercises the same `ORDER BY created_at DESC` path as
    `GET /api/documents` and the unfiltered `GET /api/search` - this is
    the query that benefits from the created_at index added alongside
    this test."""
    _seeded_db()

    with session_scope() as session:
        start = time.perf_counter()
        results, total = search_documents(session, SearchFilters(limit=100))
        elapsed = time.perf_counter() - start

    assert total == DOCUMENT_COUNT
    assert len(results) == 100
    assert elapsed < 1.0, f"Unfiltered ordered listing took {elapsed:.2f}s over {DOCUMENT_COUNT} rows"


def test_keyword_search_across_ocr_text_is_reasonably_fast():
    _seeded_db()

    with session_scope() as session:
        start = time.perf_counter()
        results, total = search_documents(session, SearchFilters(keyword="document 4", limit=50))
        elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"Keyword search took {elapsed:.2f}s over {DOCUMENT_COUNT} rows"


def test_date_range_search_is_fast():
    _seeded_db()

    with session_scope() as session:
        start = time.perf_counter()
        results, total = search_documents(
            session,
            SearchFilters(
                date_from=datetime.utcnow() - timedelta(days=30),
                date_to=datetime.utcnow(),
                limit=100,
            ),
        )
        elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"Date-range search took {elapsed:.2f}s over {DOCUMENT_COUNT} rows"


def test_fuzzy_matching_scales_to_hundreds_of_estates():
    """The fuzzy matching tier (app/rules/fuzzy.py) is O(candidates x
    aliases x text length) per document in the worst case - verify it
    stays fast even with a much larger rule set than the shipped Housing
    Estate Poster config, since an office could plausibly configure
    hundreds of estates."""
    districts = [District(id=f"d{i}", name=f"District {i}", aliases=[f"D{i}"]) for i in range(20)]
    estates = [
        Estate(id=f"e{i}", name=f"Test Estate {i}", district_id=f"d{i % 20}", aliases=[f"TE{i}"])
        for i in range(500)
    ]
    ruleset = RuleSet(districts=districts, estates=estates)
    engine = RuleEngine(ruleset)

    sample_text = "OCR text mentioning Test Estate 250 and District 10 with some noise 藍田邨"

    start = time.perf_counter()
    for _ in range(20):
        engine.resolve_district(sample_text)
        engine.resolve_estate(sample_text)
    elapsed = time.perf_counter() - start

    per_document = elapsed / 20
    assert per_document < 0.5, f"Fuzzy matching took {per_document:.3f}s/document with 500 estates"
