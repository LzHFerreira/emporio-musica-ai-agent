import pytest

from emporio.sources.merge import merge_rows


def test_append_adds_upload_and_retains_omitted_base_rows():
    base = [{"product_id": "1", "name": "A"}, {"product_id": "2", "name": "B"}]
    uploaded = [{"product_id": "3", "name": "C"}]

    assert merge_rows("products", base, uploaded, "append") == base + uploaded


def test_upsert_updates_by_product_id_and_keeps_omitted_rows():
    base = [{"product_id": "1", "name": "Old"}, {"product_id": "2", "name": "Keep"}]
    uploaded = [{"product_id": "1", "name": "New"}, {"product_id": "3", "name": "Add"}]

    assert merge_rows("products", base, uploaded, "upsert") == [
        {"product_id": "1", "name": "New"},
        {"product_id": "2", "name": "Keep"},
        {"product_id": "3", "name": "Add"},
    ]


def test_replace_uses_uploaded_rows_and_drops_omitted_base_rows():
    base = [{"product_id": "1", "name": "Old"}, {"product_id": "2", "name": "Drop"}]
    uploaded = [{"product_id": "1", "name": "New"}]

    assert merge_rows("products", base, uploaded, "replace") == uploaded


def test_identical_uploaded_duplicates_are_ignored():
    row = {"product_id": "1", "name": "Same"}

    assert merge_rows("products", [], [row, row.copy()], "append") == [row]


def test_conflicting_uploaded_duplicates_raise_value_error():
    rows = [{"product_id": "1", "name": "First"}, {"product_id": "1", "name": "Other"}]

    with pytest.raises(ValueError):
        merge_rows("products", [], rows, "append")
