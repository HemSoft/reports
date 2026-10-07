"""Normalize factual gaming.tools exports into the standalone build-editor dataset."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDITION = ROOT / "editions/dune-awakening-build-editor/2026-10-06"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def item_slot(item):
    categories = item.get("categories") or []
    if "items/garment" in categories:
        for part in ("head", "chest", "hands", "legs", "feet"):
            if any(category.endswith("/" + part) for category in categories):
                return part
        if "items/garment/utilitywearables" in categories:
            return "chest"
    for part in ("shield", "powerpack", "suspensor"):
        if "items/utility/utilitytools/" + part in categories:
            return part
    if "items/weapons" in categories and "items/weapons/ammunition" not in categories:
        return "hotbar"
    if "items/utility" in categories and "items/weapons/ammunition" not in categories:
        return "hotbar"
    return None


def stats(records):
    return [{key: value for key, value in stat.items() if key != "iconPath"} for stat in records]


def normalize(items, skill_data, details, descriptions):
    by_id = {item["id"]: item for item in details}
    descriptions = {item["id"]: item["description"] for item in descriptions}
    gear = []
    for item in items:
        slot = item_slot(item)
        if slot is None or item.get("isSchematic"):
            continue
        detail = by_id.get(item["id"], {})
        categories = item.get("categories") or []
        gear.append(
            {
                "id": item["id"],
                "name": item["name"].strip(),
                "slot": slot,
                "tier": item.get("tier", 0),
                "rarity": item.get("rarity", "Common"),
                "categories": categories,
                "tags": item.get("itemTags", []),
                "volume": item.get("volume", 0),
                "blocksLegs": slot == "chest"
                and any(
                    c in categories
                    for c in ("items/garment/stillsuits", "items/garment/utilitywearables")
                ),
                "stats": stats(item.get("stats", [])),
                "scaledStats": [
                    {"grade": row["grade"], "stats": stats(row["stats"])}
                    for row in detail.get("scaledStats", [])
                ],
            }
        )
    augments = []
    for item in details:
        if not item.get("augmentStats"):
            continue
        augments.append(
            {
                "id": item["id"],
                "name": item["name"].strip(),
                "description": descriptions[item["id"]],
                "categories": item["categories"],
                "minGrade": item.get("augmentMinQuality", 1),
                "stats": [
                    {key: value for key, value in stat.items() if key != "probability"}
                    for stat in item["augmentStats"]
                ],
            }
        )
    skills = [
        {
            key: value
            for key, value in skill.items()
            if key not in ("iconPath", "mainCategoryId", "categories")
        }
        for skill in skill_data["skills"]
    ]
    tracks = [
        {
            key: item[key]
            for key in ("id", "name", "trackType", "passiveAttributes", "maxLevel", "keystones")
        }
        for item in details
        if item.get("trackType")
    ]
    return {
        "schema": 1,
        "gameVersion": "1.5.3.6",
        "checked": "2026-10-06",
        "sourceRevision": "1791310175139",
        "sources": {
            "items": "https://dune.gaming.tools/items",
            "skills": "https://dune.gaming.tools/skill-builder",
            "specializations": "https://dune.gaming.tools/specializations",
            "patchNotes": "https://duneawakening.com/news/dune-awakening-chapter-3-patch-notes/",
        },
        "coverage": {
            "sourceItems": len(items),
            "equipment": len(gear),
            "augments": len(augments),
            "skills": len(skills),
            "specializations": len(tracks),
            "slots": {
                slot: sum(i["slot"] == slot for i in gear)
                for slot in (
                    "head",
                    "chest",
                    "hands",
                    "legs",
                    "feet",
                    "shield",
                    "powerpack",
                    "suspensor",
                    "hotbar",
                )
            },
            "scope": "All personal equipment, held weapons, tools and consumables in the source catalog. Vehicles, building pieces, materials, ammunition and schematics are excluded.",
        },
        "items": sorted(gear, key=lambda i: i["name"].casefold()),
        "augments": sorted(augments, key=lambda i: i["name"].casefold()),
        "skills": skills,
        "tracks": tracks,
        "characterLevels": skill_data["characterLevels"],
        "combatLevels": skill_data["combatLevels"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for source in ("items", "skills", "details", "descriptions"):
        parser.add_argument("--" + source, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ("items", "skills", "details", "descriptions")}
    data = normalize(*(read(path) for path in paths.values()))
    data["sourceExportSha256"] = {
        name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in paths.items()
    }
    EDITION.mkdir(parents=True, exist_ok=True)
    (EDITION / "payload.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["coverage"]))


if __name__ == "__main__":
    main()
