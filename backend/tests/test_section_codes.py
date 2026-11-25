"""Penamaan kode section kelas per prodi dan untuk MK umum."""

from section_codes import format_section_code, section_prefix


def test_prodi_specific_course_uses_program_prefix() -> None:
    assert section_prefix({"TSD"}, {"program_studi"}) == "SD"
    assert section_prefix({"TRKB"}, {"program_studi"}) == "RK"
    assert section_prefix({"TI"}, {"program_studi"}) == "TI"


def test_shared_scope_or_multiple_programs_use_um_prefix() -> None:
    assert section_prefix({"TSD"}, {"universitas"}) == "UM"
    assert section_prefix({"TSD"}, {"fakultas"}) == "UM"
    assert section_prefix({"TSD", "TRKB"}, {"program_studi"}) == "UM"
    assert section_prefix(set(), {"program_studi"}) == "UM"


def test_unknown_program_code_is_used_as_prefix() -> None:
    assert section_prefix({"XX"}, {"program_studi"}) == "XX"


def test_section_codes_are_sequential_with_prefix() -> None:
    prefix = section_prefix({"TSD"}, {"program_studi"})
    assert [format_section_code(prefix, ordinal) for ordinal in (1, 2, 3)] == [
        "SD-A1",
        "SD-A2",
        "SD-A3",
    ]
