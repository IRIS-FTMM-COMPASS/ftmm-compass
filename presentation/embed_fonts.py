"""Salin font yang sudah tertanam di template_utama.pptx ke deck hasil build.

PptxGenJS tidak bisa menanam font. Skrip ini menambahkan ppt/fonts/*.fntdata,
relasi, dan embeddedFontLst agar deck tetap memakai Inter/Anantason di mesin
yang tidak memasang font tersebut.

Jalankan setelah `node presentation/build_deck.js`:
    python presentation/embed_fonts.py
"""

from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
DECK = ROOT / "FTMM-Compass-Deck.pptx"
TEMPLATE = ROOT / "template_utama.pptx"
TMP = ROOT / ".FTMM-Compass-Deck.tmp.pptx"

FONT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"


def font_payload():
    with zipfile.ZipFile(TEMPLATE) as tpl:
        rels = tpl.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        pres = tpl.read("ppt/presentation.xml").decode("utf-8")
        rel_target = dict(
            re.findall(
                r'<Relationship Id="([^"]+)"[^>]*Target="fonts/([^"]+)"',
                rels,
            )
        )
        files = {
            name: tpl.read(name)
            for name in tpl.namelist()
            if name.startswith("ppt/fonts/")
        }
        block = re.search(
            r"<p:embeddedFontLst>.*?</p:embeddedFontLst>", pres, re.S
        )
        if not block:
            raise SystemExit("template tidak punya embeddedFontLst")
        entries = re.findall(
            r"<p:embeddedFont>.*?</p:embeddedFont>", block.group(0), re.S
        )

    new_entries = []
    new_rels = []
    used = 0
    for entry in entries:
        def repl(match):
            nonlocal used
            used += 1
            old_id = match.group(1)
            target = rel_target.get(old_id)
            if not target:
                raise SystemExit(f"relasi font {old_id} tidak ditemukan")
            new_id = f"rIdFont{used}"
            new_rels.append(
                f'<Relationship Id="{new_id}" Type="{FONT_REL_TYPE}" Target="fonts/{target}"/>'
            )
            return f'r:id="{new_id}"'

        new_entries.append(re.sub(r'r:id="([^"]+)"', repl, entry))

    return files, "<p:embeddedFontLst>" + "".join(new_entries) + "</p:embeddedFontLst>", new_rels


def main():
    files, block, rels = font_payload()

    with zipfile.ZipFile(DECK) as deck:
        parts = {name: deck.read(name) for name in deck.namelist()}

    parts.update(files)

    content_types = parts["[Content_Types].xml"].decode("utf-8")
    if 'Extension="fntdata"' not in content_types:
        content_types = content_types.replace(
            "</Types>",
            '<Default Extension="fntdata" ContentType="application/x-fontdata"/></Types>',
        )
    parts["[Content_Types].xml"] = content_types.encode("utf-8")

    presentation = parts["ppt/presentation.xml"].decode("utf-8")
    if "embedTrueTypeFonts" not in presentation:
        presentation = presentation.replace(
            "<p:presentation ",
            '<p:presentation embedTrueTypeFonts="1" ',
            1,
        )
    presentation = presentation.replace(
        "<p:defaultTextStyle>",
        block + "<p:defaultTextStyle>",
        1,
    )
    parts["ppt/presentation.xml"] = presentation.encode("utf-8")

    rels_xml = parts["ppt/_rels/presentation.xml.rels"].decode("utf-8")
    rels_xml = rels_xml.replace("</Relationships>", "".join(rels) + "</Relationships>")
    parts["ppt/_rels/presentation.xml.rels"] = rels_xml.encode("utf-8")

    with zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in parts.items():
            out.writestr(name, data)

    shutil.move(TMP, DECK)
    print(f"Embedded {len(files)} font files into {DECK.name}")


if __name__ == "__main__":
    main()
