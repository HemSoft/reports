# Dune: Awakening Overland loot reference

Checked 2026-10-05. Structured facts are in `payload.json`.

## Scope and sources

Funcom introduced five repeatable Overland Testing Stations in [Chapter 3](https://duneawakening.com/news/dune-awakening-chapter-3-patch-notes/), with difficulty affecting reward Grades. [Update 1.4](https://duneawakening.com/news/dune-awakening-1-4-0-0-patch-notes/) added The Old Quarry.

Current item names, recipe status, station memberships and decimal chest probabilities were recovered from the database's complete embedded dungeon records, rather than its initially grade-filtered visible table. The source reports game version **1.5.3.3**, updated **2026-09-24**. [Dungeons database](https://dune.gaming.tools/dungeons).

| Station | Theme | Schematic entries | Current source |
| --- | --- | ---: | --- |
| 24 | Darkness | 60 | [Database](https://dune.gaming.tools/dungeons/dgn_024_darkness) |
| 89 | Radiation | 72 | [Database](https://dune.gaming.tools/dungeons/dgn_089_radiation) |
| 136 | Fire | 59 | [Database](https://dune.gaming.tools/dungeons/dgn_136_fire) |
| 152 | Electric | 59 | [Database](https://dune.gaming.tools/dungeons/dgn_152_electric) |
| 195 | Poison | 68 | [Database](https://dune.gaming.tools/dungeons/dgn_195_poison) |
| The Old Quarry | Multiple | 59 | [Database](https://dune.gaming.tools/dungeons/dgn_pit) |

There are **192 distinct schematics**: 104 augments, 44 armor pieces, 41 weapons, two tools and one consumable recipe. Every entry is explicitly `isSchematic=true` in current dungeon data. Recipes shared by stations count once in the distinct total, and once per station pool.

## Rankings

Ratings are **Method community usefulness rankings**, not official game tiers or progression Grades. The [live Overland Companion](https://www.method.gg/dune-awakening/overland-companion) supplies 44 S, 36 A, 46 B and 63 C ratings; the two tools and consumable are unranked. No D-rated entries occur in this pool. All station memberships match the current database exactly.

Method's [weapon](https://www.method.gg/dune-awakening/dune-awakening-best-weapons-tier-list), [armor](https://www.method.gg/dune-awakening/dune-awakening-best-armor-tier-list), and [augment](https://www.method.gg/dune-awakening/dune-awakening-best-augments-tier-list) discussions are dated **2026-05-19**. Rankings consider mixed PvE/PvP use; augment ratings focus on higher Grades. These ratings may lag later combat patches. Use the live companion's explicit badges consistently: for example, it marks Disruptor M11 Heavy Kit B while discussion prose calls it A.

## Verified alias

The sole name mismatch is **JABAL Spitdart Focuser**, called **JABAL Spitdart Ranger** by Method. [Current item](https://dune.gaming.tools/items/t6_augment_ch5_spitdart1) and [Method item](https://www.method.gg/dune-awakening/database/augmentations/jabal-spitdart-ranger) match all Grade 3–5 effects: recoil reduction, faster reload and −10% rate of fire. Both drop in Quarry. The JSON retains Method's C rating, searchable old name, and a note explaining the mapping. This mapping is an inference from identical effects and source location, not an official rename announcement.

## Rate interpretation and UI copy

Use: **“Database chest chance · Grade depends on difficulty.”**

The current Focuser item identifies its source as an Ultra Rare Container. Rates are database-reported container probabilities; do not present them as guarantees, observed player frequencies, or Grade-specific full-run odds. The JSON preserves exact probabilities and formats rates to one decimal, while retaining Method's older rounded display values.

Use current names by default, include aliases in search, and display unranked recipes under “Unranked.” No unsupported rankings have been assigned. This is a dated static reference; source links allow checking subsequent changes.

## JSON contract

`stations`: id (string), number (nullable), name, theme/hazard, boss, current database url and methodUrl.

`items`: id (Method slug), gameId, name, type/category, tier (S/A/B/C/null), isSchematic, aliases, optional notes, current database url/gameUrl, methodUrl, and locations with station/stationId, decimal rate text, exact probability, and methodRate.

Metadata contains checked date, source version/update dates, ranking date/source, rate label, and concise caveats. No external item artwork was copied.
