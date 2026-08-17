#!/usr/bin/env python3
"""Convert a few IngForms emigratie XML records to JSON.

The zip is not in this repo. Pass --zip /path/to/content_repository.zip.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import zipfile
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLES = {
    "persoon": "content_repository/emigratie/data/nederland/personen/01Haveman.xml",
    "instelling": "content_repository/emigratie/data/nederland/instellingen/Sociale Zaken/01sz_emc.xml",
    "autopsie": "content_repository/emigratie/data/nederland/instellingen/Hoge_colleges_van_Staat/11mr.xml",
    "tekst": "content_repository/emigratie/data/Bijlagen/samenvatting.xml",
}

# Child tag used when serializing List(Choice(__name__=...))
LIST_CHILD = {
    "land_herkomst": "land",
    "typering_persoon": "typering",
    "typering_instelling": "typering",
    "typering_taken": "typering",
    "kerk": "kerk",
    "zuil": "kerk",
    "doelgroepen": "doelgroep",
    "informatiedrager": "drager",
    "verw_wetten_ned": "wet",
    "verw_wetten_bilateraal": "wet",
    "verw_wetten_multilateraal": "wet",
    "bestemmings_landen": "land",
}


def unescape(text: str | None) -> str | None:
    if text is None:
        return None
    value = html.unescape(text)
    return value if value.strip() else None


def child_text(parent: ET.Element, tag: str) -> str | None:
    el = parent.find(tag)
    if el is None:
        return None
    return unescape("".join(el.itertext()) if list(el) else (el.text or ""))


def choice_list(parent: ET.Element, field: str) -> list[str]:
    el = parent.find(field)
    if el is None:
        return []
    child = LIST_CHILD[field]
    return [t for t in (unescape(c.text) for c in el.findall(child)) if t]


def relations(parent: ET.Element, field: str) -> list[str]:
    el = parent.find(field)
    if el is None:
        return []
    return [t for t in (unescape(c.text) for c in el.findall("relation")) if t]


def xhtml(parent: ET.Element, field: str) -> str:
    value = child_text(parent, field)
    return value or ""


def string(parent: ET.Element, field: str) -> str:
    value = child_text(parent, field)
    return value or ""


def convert_persoon(root: ET.Element, obj_name: str) -> dict:
    fields_str = [
        "naam_archiefvormer",
        "periode",
        "datum_laatste_verandering",
    ]
    fields_xhtml = [
        "naam_varianten",
        "biografie",
        "functies",
        "literatuur",
        "andere_archiefvormers",
        "archieven",
        "periode_archief",
        "vindplaats",
        "openbaarheid",
        "omvang_invnr",
        "vernietigd",
        "toegang",
        "kenmerk_toegang",
        "indices_toegang",
        "originele_archivalia_ander",
        "originele_archivalia_deze",
        "opmerkingen_archief",
        "seriele_bescheiden",
        "statistische_gegevens",
        "verw_wetten",
        "inhoud_overig",
        "opmerkingen",
        "aantekeningen",
    ]
    fields_rel = [f"{f}_link" for f in [
        "naam_varianten", "biografie", "functies", "literatuur",
        "andere_archiefvormers", "archieven", "periode_archief", "vindplaats",
        "openbaarheid", "omvang_invnr", "vernietigd", "toegang",
        "kenmerk_toegang", "indices_toegang", "originele_archivalia_ander",
        "originele_archivalia_deze", "opmerkingen_archief", "seriele_bescheiden",
        "statistische_gegevens", "verw_wetten", "inhoud_overig", "opmerkingen",
    ]]
    fields_list = [
        "land_herkomst", "typering_persoon", "kerk", "doelgroepen",
        "informatiedrager", "verw_wetten_ned", "verw_wetten_bilateraal",
        "verw_wetten_multilateraal", "bestemmings_landen",
    ]
    data = {"obj_name": obj_name}
    for f in fields_str:
        data[f] = string(root, f)
    for f in fields_xhtml:
        data[f] = xhtml(root, f)
    for f in fields_rel:
        data[f] = relations(root, f)
    for f in fields_list:
        data[f] = choice_list(root, f)
    return data


def convert_instelling(root: ET.Element, obj_name: str) -> dict:
    data = convert_persoon(root, obj_name)
    # instelling-specific names
    data["periode_van_bestaan"] = string(root, "periode_van_bestaan")
    data.pop("periode", None)
    data["organisatie"] = xhtml(root, "organisatie")
    data["organisatie_link"] = relations(root, "organisatie_link")
    data["taak"] = xhtml(root, "taak")
    data["taak_link"] = relations(root, "taak_link")
    data["voorloper"] = xhtml(root, "voorloper")
    data["voorloper_link"] = relations(root, "voorloper_link")
    data["opvolger"] = xhtml(root, "opvolger")
    data["opvolger_link"] = relations(root, "opvolger_link")
    data["typering_instelling"] = choice_list(root, "typering_instelling")
    data["typering_taken"] = choice_list(root, "typering_taken")
    data["zuil"] = choice_list(root, "zuil")
    for drop in ("typering_persoon", "kerk", "biografie", "biografie_link",
                 "functies", "functies_link"):
        data.pop(drop, None)
    return data


def convert_autopsie(root: ET.Element, obj_name: str) -> dict:
    archief = []
    wrapper = root.find("archief")
    if wrapper is not None:
        for inv in wrapper.findall("inventaris"):
            archief.append({
                "inventarisomschrijving": xhtml(inv, "inventarisomschrijving"),
                "anker": string(inv, "anker"),
                "omschrijving": xhtml(inv, "omschrijving"),
            })
    return {
        "obj_name": obj_name,
        "titel": string(root, "titel"),
        "text": xhtml(root, "text"),
        "archief": archief,
        "opmerkingen": xhtml(root, "opmerkingen"),
        "aantekeningen": xhtml(root, "aantekeningen"),
    }


def convert_tekst(root: ET.Element, obj_name: str) -> dict:
    annotatie = []
    wrapper = root.find("annotatie")
    if wrapper is not None:
        for anno in wrapper.findall("anno"):
            annotatie.append({
                "ankernaam": string(anno, "ankernaam"),
                "annotatie_tekst": xhtml(anno, "annotatie_tekst"),
            })
    return {
        "obj_name": obj_name,
        "titel": string(root, "titel"),
        "tekst": xhtml(root, "tekst"),
        "annotatie": annotatie,
        "aantekeningen": xhtml(root, "aantekeningen"),
    }


CONVERTERS = {
    "persoon": convert_persoon,
    "instelling": convert_instelling,
    "autopsie": convert_autopsie,
    "tekst": convert_tekst,
}


def obj_name_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, help="Path to content_repository.zip")
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "samples"),
        help="Output directory (default: samples/)",
    )
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    zf = zipfile.ZipFile(args.zip)
    for type_name, zip_name in SAMPLES.items():
        xml = zf.read(zip_name)
        root = ET.parse(io.BytesIO(xml)).getroot()
        data = CONVERTERS[type_name](root, obj_name_from_path(zip_name))
        dest = os.path.join(args.out, f"{type_name}-full.json")
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {dest} ({len(json.dumps(data))} chars)")


if __name__ == "__main__":
    main()
