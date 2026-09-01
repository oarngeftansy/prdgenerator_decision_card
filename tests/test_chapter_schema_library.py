import pytest

from backend.chapter_schema_library import SCHEMA_VERSION, chapter_schema_library


def test_library_resolves_base_and_registered_variant_overlay():
    base = chapter_schema_library.resolve("randomization", None, SCHEMA_VERSION)
    variant = chapter_schema_library.resolve("randomization", "three_choice", SCHEMA_VERSION)
    assert variant.base_schema_key == base.schema_key
    assert variant.mechanic_variant == "three_choice"
    assert {slot.slot_id for slot in variant.slots} > {slot.slot_id for slot in base.slots}


def test_library_has_no_custom_and_all_slots_obey_applicability_contract():
    assert "custom" not in chapter_schema_library.list_types(SCHEMA_VERSION)
    assert chapter_schema_library.validate_all() == ()


def test_library_rejects_unregistered_variant():
    with pytest.raises(KeyError, match="unregistered mechanic variant"):
        chapter_schema_library.resolve("randomization", "loot_box", SCHEMA_VERSION)
