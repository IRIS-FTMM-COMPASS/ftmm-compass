"""SSOT katalog kurikulum FTMM.

Satu-satunya jalur baca katalog untuk API: DB (hasil seed kanonik), dengan fallback
ke berkas `Ekstrak/*.json` bila database belum terisi. Admin CRUD menulis ke DB,
memanggil `refresh_from_db`, lalu membatalkan cache respons TTL. Cache ini hanya
menyimpan payload database untuk kunci filter tertentu dan tidak pernah menyimpan
jalur fallback lokal.
"""

import copy
import glob
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from academics import parity_of, term_of
from models import Course, Curriculum, CurriculumCourse, StudyProgram
from schemas import CourseModel

logger = logging.getLogger("ftmm_compass.catalog")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EKSTRAK_DIR = os.path.join(REPO_ROOT, "Ekstrak")

PRODI_ALIASES = {
    "teknologi sains data": "Teknologi Sains Data",
    "sains data": "Teknologi Sains Data",
    "data science": "Teknologi Sains Data",
    "tsd": "Teknologi Sains Data",
    "teknik robotika dan kecerdasan buatan": "Teknik Robotika dan Kecerdasan Buatan",
    "teknik robotika & kecerdasan buatan": "Teknik Robotika dan Kecerdasan Buatan",
    "robotika dan kecerdasan buatan": "Teknik Robotika dan Kecerdasan Buatan",
    "robotika": "Teknik Robotika dan Kecerdasan Buatan",
    "trkb": "Teknik Robotika dan Kecerdasan Buatan",
    "s1 rekayasa nanoteknologi": "Rekayasa Nanoteknologi",
    "rekayasa nanoteknologi": "Rekayasa Nanoteknologi",
    "nanoteknologi": "Rekayasa Nanoteknologi",
    "nano": "Rekayasa Nanoteknologi",
    "rn": "Rekayasa Nanoteknologi",
    "teknik industri": "Teknik Industri",
    "industri": "Teknik Industri",
    "ti": "Teknik Industri",
    "teknik elektro": "Teknik Elektro",
    "elektro": "Teknik Elektro",
    "te": "Teknik Elektro",
}

DEFAULT_PRODI = "Teknologi Sains Data"

PROGRAM_NAMES = {
    "TSD": "Teknologi Sains Data",
    "TRKB": "Teknik Robotika dan Kecerdasan Buatan",
    "RN": "Rekayasa Nanoteknologi",
    "TI": "Teknik Industri",
    "TE": "Teknik Elektro",
}

PROGRAM_ORDER = ["TSD", "RN", "TRKB", "TE", "TI"]

PROGRAM_HEADINGS = {
    code: f"S1 {name}" for code, name in PROGRAM_NAMES.items()
}

CURRICULUM_DOCS = {
    "TRKB": "754 KR KURIKULUM S1 TEKNIK ROBOTIKA KECERDASAN BUATAN FTMM stempel.pdf",
    "TSD": "Dokumen Kurikulum TSD.pdf",
}

PRODI_CODES = {name: code for code, name in PROGRAM_NAMES.items()}

ADMIN_REQUIREMENT_NOTES = "admin_catalog"

_CURRICULUM: Dict[str, List[CourseModel]] = {}
_SOURCE = "empty"

CATALOG_CACHE_TTL_SECONDS = 30.0
_catalog_cache: Dict[tuple, tuple[float, Any]] = {}
_catalog_cache_lock = threading.Lock()


def _clone_cached(value: Any) -> Any:
    return copy.deepcopy(value)


def catalog_cache_get(key: tuple) -> Optional[Any]:
    """Ambil payload katalog dari cache bila masih segar; gagal baca diabaikan."""
    try:
        with _catalog_cache_lock:
            entry = _catalog_cache.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if time.monotonic() >= expires_at:
                _catalog_cache.pop(key, None)
                return None
        return _clone_cached(payload)
    except Exception:
        logger.debug("Gagal membaca cache katalog", exc_info=True)
        return None


def catalog_cache_set(key: tuple, payload: Any) -> None:
    """Simpan payload katalog untuk kunci filter dengan TTL; gagal tulis diabaikan."""
    try:
        cloned = _clone_cached(payload)
        with _catalog_cache_lock:
            _catalog_cache[key] = (
                time.monotonic() + CATALOG_CACHE_TTL_SECONDS,
                cloned,
            )
    except Exception:
        logger.debug("Gagal menulis cache katalog", exc_info=True)


def invalidate_catalog_cache() -> None:
    """Hapus semua entri cache katalog setelah penulisan katalog oleh admin."""
    try:
        with _catalog_cache_lock:
            _catalog_cache.clear()
    except Exception:
        logger.debug("Gagal membatalkan cache katalog", exc_info=True)


async def catalog_db_is_available(db: AsyncSession) -> bool:
    """Probe ringan: apakah database masih dapat menjawab kueri sederhana."""
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.debug("Probe ketersediaan database gagal", exc_info=True)
        return False


async def catalog_cache_get_checked(db: AsyncSession, key: tuple) -> Optional[Any]:
    """Sajikan cache hanya bila database hidup; batalkan bila database mati."""
    cached = catalog_cache_get(key)
    if cached is None:
        return None
    try:
        available = await catalog_db_is_available(db)
    except Exception:
        logger.debug("Probe katalog tidak dapat dijalankan", exc_info=True)
        available = False
    if available:
        return cached
    invalidate_catalog_cache()
    return None


def normalize_prodi(prodi_input: Optional[str]) -> Optional[str]:
    if not prodi_input:
        return None
    cleaned = prodi_input.strip().lower()
    if cleaned in PRODI_ALIASES:
        return PRODI_ALIASES[cleaned]
    for alias, formal_name in PRODI_ALIASES.items():
        if len(alias) > 3 and alias in cleaned:
            return formal_name
    return prodi_input.strip()


def prodi_code(prodi: Optional[str]) -> str:
    return PRODI_CODES.get(normalize_prodi(prodi) or "", "")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "course"


def normalize_course_type(raw: Optional[str]) -> str:
    value = (raw or "").lower()
    if any(key in value for key in ("pilihan", "pengayaan", "peminatan")):
        return "Pilihan"
    return "Wajib"


def _build_course(
    program: str,
    code: Optional[str],
    name: str,
    credits: int,
    semester: int,
    course_type: Optional[str],
    term: Optional[str],
    desc: str,
    prerequisites: List[str],
    used_ids: set,
    lecturer: Optional[str] = None,
    is_active: bool = True,
    course_scope: str = "program_studi",
) -> CourseModel:
    course_id = f"{slugify(program)}:{code or slugify(name)}"
    if course_id in used_ids:
        course_id = f"{course_id}-{slugify(name)}"
    while course_id in used_ids:
        course_id += "-x"
    used_ids.add(course_id)

    parity = parity_of(semester)
    if term in ("ganjil", "genap"):
        parity = "odd" if term == "ganjil" else "even"

    return CourseModel(
        id=course_id,
        code=code or None,
        name=name,
        credits=credits,
        semester=semester,
        type=normalize_course_type(course_type),
        parity=parity,
        desc=desc or "",
        program=program,
        lecturer=lecturer,
        prerequisites=prerequisites,
        is_active=is_active,
        course_scope=course_scope,
    )


def load_ekstrak(directory: str = EKSTRAK_DIR) -> Dict[str, List[CourseModel]]:
    """Fallback offline: baca kurikulum dari berkas JSON hasil ekstraksi PDF."""
    curriculum: Dict[str, List[CourseModel]] = {}
    if not os.path.isdir(directory):
        return curriculum

    for filepath in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            with open(filepath, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        meta = data.get("metadata", {})
        raw_program = (
            meta.get("program_studi")
            or os.path.basename(filepath).replace("FIX ", "").replace(".json", "")
        )
        program = normalize_prodi(re.sub(r"^S1\s+", "", raw_program).strip())
        if not program:
            continue

        used_ids: set = set()
        courses: List[CourseModel] = []
        for index, item in enumerate(data.get("mata_kuliah", [])):
            name = (item.get("nama_mk") or f"Matkul {index + 1}").strip()
            semester = int(item.get("semester") or 1)
            prerequisites = [
                str(entry).strip()
                for entry in (item.get("prasyarat") or [])
                if isinstance(entry, (str, dict)) and str(entry).strip()
            ]
            courses.append(
                _build_course(
                    program=program,
                    code=(item.get("kode_mk") or None),
                    name=name,
                    credits=int(item.get("sks") or 3),
                    semester=semester,
                    course_type=item.get("jenis"),
                    term=term_of(semester),
                    desc=item.get("deskripsi") or "",
                    prerequisites=prerequisites,
                    used_ids=used_ids,
                    is_active=True,
                    course_scope="program_studi",
                )
            )
        if courses:
            curriculum[program] = courses

    return curriculum


async def _load_requirement_leaves(db: AsyncSession) -> Dict[str, List[str]]:
    """Prasyarat per curriculum_course_id dari pohon requirement di DB."""
    rows = (
        await db.execute(
            text(
                """
                SELECT r.curriculum_course_id,
                       r.notes,
                       r.raw_expression,
                       n.node_type,
                       n.threshold_value,
                       ref_course.course_name,
                       ref_course.course_code
                FROM course_requirement_rules r
                LEFT JOIN course_requirement_nodes n
                  ON n.course_requirement_rule_id = r.course_requirement_rule_id
                LEFT JOIN curriculum_courses ref_cc
                  ON ref_cc.curriculum_course_id = n.referenced_curriculum_course_id
                LEFT JOIN courses ref_course
                  ON ref_course.course_id = ref_cc.course_id
                ORDER BY r.curriculum_course_id, r.notes, n.node_order
                """
            )
        )
    ).mappings()

    leaves: Dict[str, List[str]] = defaultdict(list)
    for row in rows:
        node_type = row["node_type"]
        if node_type is None:
            if row["notes"] == ADMIN_REQUIREMENT_NOTES and row["raw_expression"]:
                leaves[str(row["curriculum_course_id"])].append(row["raw_expression"])
            continue
        label = row["course_name"] or row["course_code"]
        if node_type in ("course_passed", "course_taken_or_concurrent") and label:
            leaves[str(row["curriculum_course_id"])].append(label)
        elif node_type == "minimum_completed_sks":
            leaves[str(row["curriculum_course_id"])].append(
                f"Minimal {int(row['threshold_value'] or 0)} SKS"
            )
        elif node_type == "minimum_choice_sks":
            leaves[str(row["curriculum_course_id"])].append(
                f"Minimal {int(row['threshold_value'] or 0)} SKS MK Pilihan"
            )
        elif node_type == "minimum_semester":
            leaves[str(row["curriculum_course_id"])].append(
                f"Minimal semester {int(row['threshold_value'] or 0)}"
            )
    return leaves


async def _resolve_prerequisite_references(
    db: AsyncSession, keys: List[str], curriculum_id
) -> Dict[str, object]:
    if not keys:
        return {}
    rows = (
        await db.execute(
            text(
                """
                SELECT lower(c.course_code) AS code_key,
                       lower(c.course_name) AS name_key,
                       cc.curriculum_course_id
                FROM curriculum_courses cc
                JOIN courses c ON c.course_id = cc.course_id
                WHERE lower(c.course_code) = ANY(:keys)
                   OR lower(c.course_name) = ANY(:keys)
                ORDER BY (cc.curriculum_id = :cid) DESC, c.course_code
                """
            ),
            {"keys": keys, "cid": str(curriculum_id) if curriculum_id else None},
        )
    ).mappings().all()
    refs: Dict[str, object] = {}
    for row in rows:
        refs.setdefault(row["code_key"], row["curriculum_course_id"])
        refs.setdefault(row["name_key"], row["curriculum_course_id"])
    return refs


async def replace_prerequisites(
    db: AsyncSession, curriculum_course_id, prerequisites: List[str]
) -> None:
    """Tulis ulang rule prasyarat satu matkul kurikulum dari daftar label admin."""
    course_key = str(curriculum_course_id)
    await db.execute(
        text(
            """
            DELETE FROM course_requirement_nodes
            WHERE course_requirement_rule_id IN (
                SELECT course_requirement_rule_id FROM course_requirement_rules
                WHERE curriculum_course_id = :cc
            )
            """
        ),
        {"cc": course_key},
    )
    await db.execute(
        text("DELETE FROM course_requirement_rules WHERE curriculum_course_id = :cc"),
        {"cc": course_key},
    )

    labels = list(
        dict.fromkeys(label.strip() for label in prerequisites if label and label.strip())
    )
    if not labels:
        return

    curriculum_id = (
        await db.execute(
            text(
                "SELECT curriculum_id FROM curriculum_courses WHERE curriculum_course_id = :cc"
            ),
            {"cc": course_key},
        )
    ).scalar_one_or_none()
    refs = await _resolve_prerequisite_references(
        db, [label.lower() for label in labels], curriculum_id
    )

    for label in labels:
        rule_id = (
            await db.execute(
                text(
                    """
                    INSERT INTO course_requirement_rules
                        (curriculum_course_id, raw_expression, notes)
                    VALUES (:cc, :raw, :notes)
                    RETURNING course_requirement_rule_id
                    """
                ),
                {"cc": course_key, "raw": label, "notes": ADMIN_REQUIREMENT_NOTES},
            )
        ).scalar_one()
        ref = refs.get(label.lower())
        if ref is None:
            continue
        root_id = (
            await db.execute(
                text(
                    """
                    INSERT INTO course_requirement_nodes
                        (course_requirement_rule_id, node_order, node_type)
                    VALUES (:rule, 1, 'all')
                    RETURNING course_requirement_node_id
                    """
                ),
                {"rule": rule_id},
            )
        ).scalar_one()
        await db.execute(
            text(
                """
                INSERT INTO course_requirement_nodes
                    (course_requirement_rule_id, parent_node_id, node_order,
                     node_type, referenced_curriculum_course_id)
                VALUES (:rule, :parent, 1, 'course_passed', :ref)
                """
            ),
            {"rule": rule_id, "parent": root_id, "ref": ref},
        )


def _pick_richest(coverage: Dict[tuple[str, int], int]) -> Dict[str, int]:
    """Kurikulum otoritatif per prodi: cakupan mata kuliah terbanyak, seri -> tahun terbaru."""
    chosen: Dict[str, tuple[int, int]] = {}
    for (program, year), count in coverage.items():
        best = chosen.get(program)
        if best is None or count > best[0] or (count == best[0] and year > best[1]):
            chosen[program] = (count, year)
    return {program: year for program, (_, year) in chosen.items()}


async def authoritative_curriculum_id(
    db: AsyncSession, program_name: str
) -> Optional[object]:
    """Id kurikulum yang dipakai katalog untuk prodi ini (sumber sama dengan refresh)."""
    program = normalize_prodi(program_name) or DEFAULT_PRODI
    rows = (
        await db.execute(
            select(
                Curriculum.curriculum_id,
                Curriculum.curriculum_year,
                StudyProgram.program_name,
            )
            .join(CurriculumCourse, CurriculumCourse.curriculum_id == Curriculum.curriculum_id)
            .join(StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id)
        )
    ).mappings().all()

    coverage: Dict[tuple[str, int], int] = defaultdict(int)
    by_key: Dict[tuple[str, int], object] = {}
    for row in rows:
        name = normalize_prodi(row["program_name"]) or DEFAULT_PRODI
        year = row["curriculum_year"] or 0
        coverage[(name, year)] += 1
        by_key[(name, year)] = row["curriculum_id"]

    year = _pick_richest(coverage).get(program)
    return by_key.get((program, year)) if year is not None else None


async def build_catalog_from_db(db: AsyncSession) -> Optional[Dict[str, List[CourseModel]]]:
    """Bangun katalog dari kurikulum otoritatif di database, atau None bila kosong."""
    rows = (
        await db.execute(
            select(
                StudyProgram.program_name,
                Curriculum.curriculum_year,
                CurriculumCourse.curriculum_course_id,
                CurriculumCourse.credits_total,
                CurriculumCourse.recommended_semester,
                CurriculumCourse.term,
                CurriculumCourse.course_type,
                CurriculumCourse.description,
                Course.course_code,
                Course.course_name,
                CurriculumCourse.course_scope,
                CurriculumCourse.is_active,
            )
            .join(CurriculumCourse, CurriculumCourse.course_id == Course.course_id)
            .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
            .join(StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id)
            .where(Course.is_active.is_(True))
        )
    ).mappings().all()

    if not rows:
        return None

    leaves = await _load_requirement_leaves(db)
    coverage: Dict[tuple[str, int], int] = defaultdict(int)
    for row in rows:
        program = normalize_prodi(row["program_name"]) or DEFAULT_PRODI
        coverage[(program, row["curriculum_year"] or 0)] += 1
    chosen = _pick_richest(coverage)

    catalog: Dict[str, List[CourseModel]] = {}
    used_by_program: Dict[str, set] = defaultdict(set)
    for row in rows:
        program = normalize_prodi(row["program_name"]) or DEFAULT_PRODI
        if (row["curriculum_year"] or 0) != chosen[program]:
            continue
        catalog.setdefault(program, []).append(
            _build_course(
                program=program,
                code=row["course_code"],
                name=row["course_name"],
                credits=row["credits_total"] or 0,
                semester=row["recommended_semester"] or 1,
                course_type=row["course_type"],
                term=row["term"],
                desc=row["description"] or "",
                prerequisites=leaves.get(str(row["curriculum_course_id"]), []),
                used_ids=used_by_program[program],
                is_active=row["is_active"],
                course_scope=row["course_scope"],
            )
        )
    return catalog


async def get_catalog_from_source(
    db: AsyncSession,
) -> tuple[Dict[str, List[CourseModel]], str]:
    """Satu jalur baca katalog publik: database bila hidup, lokal bila tidak."""
    try:
        catalog = await build_catalog_from_db(db)
        if catalog:
            return catalog, "database"
    except Exception:
        logger.debug("Katalog database tidak terbaca, memakai fallback lokal")
    local = load_ekstrak()
    if local:
        return local, "local_fallback"
    return dict(_CURRICULUM), "local_fallback"


async def refresh_from_db(db: AsyncSession) -> int:
    """Bangun ulang cache katalog dari database; kembalikan jumlah mata kuliah."""
    global _CURRICULUM, _SOURCE

    catalog = await build_catalog_from_db(db)
    if catalog is None:
        if not _CURRICULUM:
            _CURRICULUM = load_ekstrak()
            _SOURCE = "ekstrak"
        return sum(len(courses) for courses in _CURRICULUM.values())

    _CURRICULUM = catalog
    _SOURCE = "database"
    return sum(len(courses) for courses in catalog.values())


def catalog_source() -> str:
    return _SOURCE


def get_available_programs(catalog: Optional[Dict[str, List[CourseModel]]] = None) -> List[str]:
    return sorted((catalog if catalog is not None else _CURRICULUM).keys())


def get_courses_for_program(
    prodi: str, catalog: Optional[Dict[str, List[CourseModel]]] = None
) -> List[CourseModel]:
    source = catalog if catalog is not None else _CURRICULUM
    program = normalize_prodi(prodi)
    if program and program in source:
        return list(source[program])
    return list(source.get(DEFAULT_PRODI, []))


async def get_courses_for_curriculum(
    db: AsyncSession, curriculum_id
) -> List[CourseModel]:
    """Katalog untuk satu kurikulum konkret (mis. kurikulum milik mahasiswa)."""
    rows = (
        await db.execute(
            select(
                StudyProgram.program_name,
                CurriculumCourse.curriculum_course_id,
                CurriculumCourse.credits_total,
                CurriculumCourse.recommended_semester,
                CurriculumCourse.term,
                CurriculumCourse.course_type,
                CurriculumCourse.description,
                Course.course_code,
                Course.course_name,
            )
            .join(CurriculumCourse, CurriculumCourse.course_id == Course.course_id)
            .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
            .join(StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id)
            .where(
                CurriculumCourse.curriculum_id == curriculum_id,
                Course.is_active.is_(True),
                CurriculumCourse.is_active.is_(True),
            )
        )
    ).mappings().all()
    if not rows:
        return []

    program = normalize_prodi(rows[0]["program_name"]) or DEFAULT_PRODI
    leaves = await _load_requirement_leaves(db)
    used_ids: set = set()
    return [
        _build_course(
            program=program,
            code=row["course_code"],
            name=row["course_name"],
            credits=row["credits_total"] or 0,
            semester=row["recommended_semester"] or 1,
            course_type=row["course_type"],
            term=row["term"],
            desc=row["description"] or "",
            prerequisites=leaves.get(str(row["curriculum_course_id"]), []),
            used_ids=used_ids,
        )
        for row in rows
    ]


def get_all_courses(catalog: Optional[Dict[str, List[CourseModel]]] = None) -> List[CourseModel]:
    source = catalog if catalog is not None else _CURRICULUM
    return [course for courses in source.values() for course in courses]


def get_course(
    course_id: str, catalog: Optional[Dict[str, List[CourseModel]]] = None
) -> Optional[CourseModel]:
    if not course_id:
        return None
    needle = course_id.strip().lower()
    for course in get_all_courses(catalog):
        if course.id.lower() == needle or (course.code or "").lower() == needle:
            return course
    return None


_CURRICULUM = load_ekstrak()
_SOURCE = "ekstrak" if _CURRICULUM else "empty"
