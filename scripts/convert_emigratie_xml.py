#!/usr/bin/env python3
"""Write a few Emigratie samples via the generic IngForms XML converter.

  python3 scripts/convert_emigratie_xml.py --zip /path/to/content_repository.zip
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_ingforms_xml import Catalog, convert_document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLES = {
    "persoon": "content_repository/emigratie/data/nederland/personen/01Haveman.xml",
    "instelling": "content_repository/emigratie/data/nederland/instellingen/Sociale Zaken/01sz_emc.xml",
    "autopsie": "content_repository/emigratie/data/nederland/instellingen/Hoge_colleges_van_Staat/11mr.xml",
    "tekst": "content_repository/emigratie/data/Bijlagen/samenvatting.xml",
}


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
    catalog = Catalog()
    catalog.load_zip(zf)
    for type_name, zip_name in SAMPLES.items():
        root = ET.parse(io.BytesIO(zf.read(zip_name))).getroot()
        obj_name = os.path.splitext(os.path.basename(zip_name))[0]
        data = convert_document(root, catalog, "emigratie", obj_name, zip_name)
        dest = os.path.join(args.out, f"{type_name}-full.json")
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {dest} ({len(json.dumps(data))} chars)")


if __name__ == "__main__":
    main()
