# Dune: Awakening build editor sources

The editor uses a factual snapshot of game version **1.5.3.6**, checked
October 6, 2026. It is a character equipment and skill editor, separate from
the loot-location report. Community S/A/B/C rankings never determine equipment
tiers, grades, or stats.

## Dataset

The [gaming.tools item catalog](https://dune.gaming.tools/items) contains 1,420
records. Filtering out schematics, vehicles, buildings, materials and ammunition
leaves 573 personal equipment choices. These include garments, weapons, utility
equipment, handheld tools and consumables. There are 104 augments, 109 playable
skill records across five skill trees, and five specialization tracks. The source
export contains 114 skill records; five internal `Hidden` records are excluded
from the editor. One Cartographer skill
has separate multiplayer and single-player records, so the displayed choices
depend on the selected game mode.

The same site's [skill builder](https://dune.gaming.tools/skill-builder) provides
rank costs, game modes, prerequisite edges, rank-specific effects and character
point budgets. [Specialization tracks](https://dune.gaming.tools/specializations)
provide passive attribute curves and purchasable traits, including skill points
and augmentation limits. Both catalog and skill pages displayed version 1.5.3.6
and an October 6 update when captured. The site's source revision was
`1791310175139`.

Public dataset URLs follow these forms, with the recorded revision as the
`version` query parameter:

- `https://cdn-hosted.gaming.tools/dune/data/en/items.d.json`
- `https://cdn-hosted.gaming.tools/dune/data/en/skill-builder-data.d.json`
- `https://cdn-hosted.gaming.tools/dune/data/en/items/<item-id>.d.json`
- `https://cdn-hosted.gaming.tools/dune/data/en/specializations/<track-id>.d.json`

The source site's public Svelte loader decodes the `.d.json` format. Its
`fetchData` and `getDetail` functions can export decoded JSON from an ordinary
browser session. On this capture, direct command-line dataset requests returned
HTTP 403; the public browser loader succeeded. No authentication or private
endpoints were used.

The snapshot preserves stable game IDs, category and item tags, numeric values,
stat formats, rank costs, prerequisite edges, grade overrides, augment min/max
ranges and operation types. Detail records were captured for 101 unique tier 6
equipment choices, 104 augments and five tracks. Eighty-five equipment records
have grade overrides. The remaining eligible utility items retain base stats
and cannot be augmented. SHA-256 hashes of the decoded input exports appear in
`payload.json` as provenance; they are not credentials.

The secret scanner mistakes the public game attribute
`MaxDurabilityRepairReduction_WeaponsAndTools` for an IBM key and the four
provenance hashes for secrets. Its exceptions match only those five exact
fingerprints in this edition's payload and generated HTML. Security integration
tests verify that the same values elsewhere and new secrets in the snapshot
still fail the gate.

## Equipment and calculations

Body slots are head, chest/body, hands, legs and feet, with separate shield,
power pack and suspensor slots. Eight quickbar slots accept weapons, handheld
tools and consumables. Stillsuit bodies and radiation suits occupy chest and
legs, so selecting one removes a separate leg piece. Each weapon has its own
stat table; carried weapons do not contribute damage to each other.

[Funcom's Chapter 3 notes](https://duneawakening.com/news/dune-awakening-chapter-3-patch-notes/)
establish augmentation of unique tier 6 garments and weapons. The snapshot's
Crafting traits supply the available slot limits. Ranged slots unlock at track
levels 1, 31 and 87; melee slots at 3, 30 and 88; garment slots at 10 and 42.
All traits at or below the entered specialization levels are assumed purchased.
Crafting level alone determines these augmentation limits.

Specialized augments require matching game weapon-family tags. For example,
[Disruptor M11 Precision Tuning](https://dune.gaming.tools/items/t6_augment_smg1)
can apply to the SMG family, while Karpov augments require the BattleRifle family.
Augment grade choices come from the actual supplied quality rows.

Grade overrides replace the corresponding base item stat. Augment roll position
selects `min + (max - min) × position / 100`, preserving the source's endpoint
order, including ranges where a lower value is better. This is a chosen roll
value, not a probability or an expected random roll. Mapped `multiply`, `add`
and `set` operations apply to the relevant item fields. Fractional additive
mitigation values convert to percentage points for the catalog's percentage
presentation. Both beneficial effects and penalties appear in the breakdown.

The model's explicit mapping translates game attribute names to catalog display
keys. Accuracy-offset and recoil-scalar effects do not have a verified mapping
to the catalog's normalized accuracy/stability values; those final values become
unavailable when changed. Other unmapped effects stay in the source-effect
ledger. Source-provided grade DPS and effective DPS remain visible. Augment-modified
DPS is unavailable because the catalog's effective-DPS calculation includes
weapon behavior this snapshot does not establish. If a grade lacks a DPS
override, the editor does not reuse base DPS as that grade's final value.

Equipped armor value is the sum of body-item values after grades and mapped
armor augments. Selected equipment volume is the sum of item volume after
volume augments. Source units remain visible where supplied.

## Skills and progression

Character levels 1 through 200 use the source's total skill-point curve.
Additional points count from every Combat trait unlocked by the entered level. Do not also
add the source's combat-level point table; it represents the same progression
and would double count. At maximum progression, automatic Combat point traits
add 54 points.

The source skill builder treats prerequisite edges as a connected graph.
Learning a skill requires an already learned adjacent prerequisite; removing a
skill cannot disconnect learned nodes from their tree's learned starting node.
Ranks use cumulative costs. Abilities and techniques must be learned, fit their
separate three-slot lists, and cannot repeat within a list. The user sets one to
three unlocked ability slots to match completed story unlocks.
Switching game modes removes incompatible skills and any descendants left
disconnected, while preserving learned roots and other valid allocations.

The effect ledger shows selected-rank values for learned passives, equipped
abilities/techniques, track-level passive curves and automatically active traits. Conditional
combat effects are labeled. Final health, damage mitigation and combined damage
formulas across skills, progression and equipment remain unavailable, rather
than estimated. Removing ranks or lowering specialization levels immediately removes the
affected ledger rows.
Invalid builds display their errors and suppress the aggregate totals.
Percentage presentation uses explicit source attribute units: Poison/Bleed
Tolerance and the `UI_Hand-heldCutterayYield`/`UI_AnalysisModeYield` skill
attributes already contain percentage points. Fractional bonuses and
multipliers scale once for presentation, without a magnitude-based heuristic.
The catalog's `P0` repair-quality format is also a fractional percentage:
Welding Torch Mk1/Mk3/Mk5 show 70%/80%/90%. Equipment validity and skill validity
are checked separately when editing ranks, so a lost augmentation unlock keeps
its error visible without blocking unrelated legal skill edits.

## Independently checked builds

The browser tests use these source-backed expectations:

- Acheronian Helmet 283, Power Harness 525, Circuit Gauntlets 263, Acheronian
  Pants 283 and Acheronian Boots 213 give **1,567 armor**.
- Grade 5 Circuit Gauntlets have 443.34 armor. A grade 1
  [Garment Reinforcement](https://dune.gaming.tools/items/t6_augment_armor6) at the
  upper source endpoint multiplies that by 1.04, producing 461.0736 and a full
  build total of **1,765.0736**.
- Replacing chest and legs with Slaver Stillsuit Body 65 gives
  `283 + 65 + 461.0736 + 213 = 1,022.0736`.
- A Dart for Every Man has 42.8 damage per shot and 48 clip size. Grade 3
  Disruptor M11 Precision Tuning at its upper source endpoint applies 0.95 damage
  and 1.6 clip-size multipliers, producing **40.66 damage per shot** and **76.8
  clip size**. Fractional source results stay visible; integer-rounding behavior
  in the game remains unverified.

## Rebuild and refresh

Rebuild the standalone HTML from its committed sources and payload:

```sh
python scripts/dune-build/build.py
python scripts/run_tests.py
npm run test:browser
python publish.py sync /tmp/reports-site --editions editions
python publish.py build /tmp/reports-site
```

For a refresh, export the source item catalog, skill-builder data, relevant
unique tier 6 equipment/augment/track details, and augment descriptions as
decoded JSON. Inspect the source's version and category changes first. Update
the edition/version/revision constants deliberately, then normalize the exports:

```sh
python scripts/dune-build/import_snapshot.py \
  --items items-source.json --skills skills-source.json \
  --details details-source.json --descriptions augment-descriptions-source.json
python scripts/dune-build/build.py
```

New versions should use a new edition directory and manifest, preserving this
snapshot's archive. The existing Pages workflow discovers the manifest through
static-edition synchronization. Publication requires the workflow on `main`,
then verification of the report-directory link and editor on the live site.

## Using augmentation

Choose **Augments** beside an equipped item. The editor opens that item's
augment slots and stats. Locked slots name the required Crafting level and trait. **Configure** opens Progression and focuses Crafting level. Enter
your level, then choose **Return to [slot] augments**. All eligible traits apply
automatically; there are no manual trait-purchase controls.

Select a compatible augment, its grade and roll position. Choose **None** to
remove it. Locked slots still permit removing an existing augment after an
unlock is lost; the invalid-build warning remains until the build is repaired.
Replacing equipment clears that item's augments, and Reset clears the build.
Items outside the snapshot's unique tier 6 garment/weapon coverage explain
why augmentation is unavailable.

## Automatic specialization traits and Combat

Enter a level for each specialization. The editor applies every trait at or below
that level, including Combat skill-point rewards and Crafting augment slots.
The trait list is a read-only record of active and locked rewards. Lowering a
level removes its higher rewards from calculations; retained skill ranks and
augments can make the build invalid until edited or removed.

The [Combat source](https://dune.gaming.tools/specializations/combattrack)
and stored passive curves give 1% damage and 0.5% damage mitigation per level.
At level 50, automatic traits grant 27 extra skill points, 20 additional health
and 30 additional stamina. At level 100, those totals are 54, 55 and 55.

Direct ranged/melee weapon health damage is a projection of equipment damage
after grade and augment operations multiplied by `1 + DamageBonus_SpecTrack`.
A Dart for Every Man has 42.8 base damage, 64.2 at Combat 50 and 85.6 at Combat
100. At augment grade 3/roll 100, its equipment damage is 40.66, which projects
to 60.99 at Combat 50. The breakdown names each applied contribution.

Combat mitigation stays separate from item armor and individual resistances.
Health and stamina rows show additional Combat trait values, not invented
character baselines. Shield damage, abilities, target armor, conditional effects
and stacking with other skills are outside this direct damage projection.
Catalog DPS is unavailable while Combat or augments modify damage; its
weapon-specific behavior has not been reconstructed. No overall power score is
invented. The dated game snapshot remains unchanged.
