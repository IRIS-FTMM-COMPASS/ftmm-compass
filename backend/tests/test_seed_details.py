"""Unit test resolusi deskripsi mata kuliah saat seeding katalog.

Semua data bersifat sintetis: berkas ditulis ke tmp_path dan EKSTRAK_DIR
di-monkeypatch, sehingga test tidak menyentuh Ekstrak/ asli maupun database.
"""

import json

import reconcile_catalog as rc
import seed_full_catalog as seed

KEY = "TSD:AGI101:Agama Islam"


def _catalog():
    return {
        "programs": {
            "TSD": {
                "courses": [
                    {
                        "code": "AGI101",
                        "name": "Agama Islam",
                        "json_record_key": "MK-001#1",
                    }
                ]
            }
        }
    }


def _write_raw(tmp_path, description):
    (tmp_path / "FIX TSD.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "program_studi": "Teknologi Sains Data",
                    "source_document": "UJI",
                },
                "mata_kuliah": [
                    {
                        "id": "MK-001",
                        "kode_mk": "AGI101",
                        "nama_mk": "Agama Islam I",
                        "sks": 2,
                        "semester": 1,
                        "prasyarat": [],
                        "jenis": "Wajib",
                        "deskripsi": description,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_derived_details_take_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "EKSTRAK_DIR", str(tmp_path))
    derived = tmp_path / "derived"
    derived.mkdir()
    (derived / "catalog_details.json").write_text(
        json.dumps({KEY: {"deskripsi": "DARI DERIVED"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_raw(tmp_path, "DARI EKSTRAK LAIN")

    details = seed.load_details(_catalog())

    assert details[KEY]["deskripsi"] == "DARI DERIVED"


def test_raw_ekstrak_fills_missing_details(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "EKSTRAK_DIR", str(tmp_path))
    _write_raw(tmp_path, "DARI EKSTRAK")

    details = seed.load_details(_catalog())

    assert details[KEY]["deskripsi"] == "DARI EKSTRAK"


def test_empty_ekstrak_returns_no_details(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "EKSTRAK_DIR", str(tmp_path))

    assert seed.load_details(_catalog()) == {}
