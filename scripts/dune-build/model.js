/* Pure build rules. This module is also embedded in the offline edition. */
'use strict';
const DuneBuild = (() => {
  const slots = ['head', 'chest', 'hands', 'legs', 'feet', 'shield', 'powerpack', 'suspensor',
    ...Array.from({ length: 8 }, (_, index) => `hotbar${index + 1}`)];
  const bodySlots = slots.slice(0, 5);
  // These source skill attributes already store percentage points. Other percent
  // skill/progression attributes store fractions or multipliers, including > 1.
  const percentPointKeys = new Set(['PoisonStatusTolerance', 'BleedStatusTolerance',
    'UI_Hand-heldCutterayYield', 'UI_AnalysisModeYield']);
  const itemById = (data, id) => data.items.find(item => item.id === id);
  const skillById = (data, id) => data.skills.find(skill => skill.id === id);
  const clone = value => JSON.parse(JSON.stringify(value));
  const itemGroup = item => item.categories.includes('items/garment') ? 'armor'
    : item.tags.some(tag => tag.startsWith('Items.Holsters.MeleeWeapons')) ? 'melee'
    : item.tags.some(tag => tag.startsWith('Items.Holsters.RangedWeapons')) ? 'ranged' : 'utility';

  function initial(data) {
    return { equipment: Object.fromEntries(slots.map(slot => [slot, { id: '', grade: 0, augments: [] }])),
      ranks: {}, abilities: ['', '', ''], techniques: ['', '', ''],
      levels: Object.fromEntries(data.tracks.map(track => [track.id, 0])),
      characterLevel: 1, abilitySlots: 3, gameMode: 'multiplayer' };
  }

  const fileLimit = 64 * 1024;
  function serialize(data, state) {
    return JSON.stringify({ format: 'hemsoft-dune-build', version: 1,
      gameVersion: data.gameVersion, build: state }, null, 2);
  }

  // Validate the whole file before handing a new state to the editor. Rule
  // warnings (for example a lowered Crafting level) remain editable drafts.
  function deserialize(data, text) {
    try {
      const require = (condition, message) => { if (!condition) throw new Error(message); };
      require(typeof text === 'string' && text.length <= fileLimit, 'Build files must be 64 KB or smaller. Choose a saved build file.');
      let file;
      try { file = JSON.parse(text); }
      catch { return { error: 'This file is not valid JSON. Choose a file downloaded with Save build.' }; }
      const record = (value, keys, label, partial = false) => {
        require(value !== null && typeof value === 'object' && !Array.isArray(value)
          && Object.keys(value).every(key => keys.includes(key))
          && (partial || keys.every(key => Object.hasOwn(value, key))),
        `${label} is incomplete or contains unsupported fields. Choose a saved build file.`);
      };
      record(file, ['format', 'version', 'gameVersion', 'build'], 'Build file');
      require(file.format === 'hemsoft-dune-build' && file.version === 1,
        'This build file format is unsupported. Choose a file downloaded with Save build.');
      require(file.gameVersion === data.gameVersion,
        'This build uses different game data. Open it with the matching editor.');
      const next = file.build;
      record(next, Object.keys(initial(data)), 'Build');
      require(data.characterLevels.some(row => row.level === next.characterLevel), 'Character level is unsupported. Choose a saved build file.');
      require([1, 2, 3].includes(next.abilitySlots), 'Ability slot count must be 1, 2 or 3.');
      require(['multiplayer', 'singleplayer'].includes(next.gameMode), 'Game mode is unsupported. Choose a saved build file.');
      record(next.levels, data.tracks.map(track => track.id), 'Specialization levels');
      for (const track of data.tracks) require(Number.isInteger(next.levels[track.id])
        && next.levels[track.id] >= 0 && next.levels[track.id] <= track.maxLevel, `${track.name} level is outside its supported range.`);
      record(next.ranks, data.skills.map(skill => skill.id), 'Skill ranks', true);
      for (const [id, rank] of Object.entries(next.ranks)) require(Number.isInteger(rank)
        && rank >= 0 && rank <= skillById(data, id).maxLevel, 'A skill rank is outside its supported range.');
      for (const [key, kind] of [['abilities', 'Ability'], ['techniques', 'Technique']]) {
        require(Array.isArray(next[key]) && next[key].length === 3
          && next[key].every(id => id === '' || (typeof id === 'string' && skillById(data, id)?.skillType === kind)),
        `Equipped ${key} contain an unsupported selection. Choose a saved build file.`);
      }
      record(next.equipment, slots, 'Equipment slots');
      for (const slot of slots) {
        const selection = next.equipment[slot];
        record(selection, ['id', 'grade', 'augments'], `Equipment in ${slot}`);
        const item = compatibleItems(data, slot).find(item => item.id === selection.id);
        require(selection.id === '' || !!item, `Equipment in ${slot} is unknown or incompatible.`);
        require(Number.isInteger(selection.grade) && (selection.grade === 0
          || item?.scaledStats.some(row => row.grade === selection.grade)), `Equipment grade in ${slot} is unsupported.`);
        require(Array.isArray(selection.augments) && selection.augments.length <= 3,
          `Augment slots in ${slot} are unsupported.`);
        for (const chosen of selection.augments) {
          if (chosen === null) continue;
          record(chosen, ['id', 'grade', 'roll'], `Augment in ${slot}`);
          const augment = compatibleAugments(data, item).find(augment => augment.id === chosen.id);
          require(chosen.id === '' || !!augment, `Augment in ${slot} is unknown or incompatible.`);
          require(Number.isInteger(chosen.grade) && (chosen.id === '' ? chosen.grade === 1
            : augment.stats.every(stat => stat.values.some(row => row.quality === chosen.grade))),
          `Augment grade in ${slot} is unsupported.`);
          require(Number.isFinite(chosen.roll) && chosen.roll >= 0 && chosen.roll <= 100,
            `Augment roll in ${slot} must be between 0 and 100.`);
        }
      }
      return { state: clone(next) };
    } catch (error) { return { error: error.message }; }
  }

  function compatibleItems(data, slot) {
    return data.items.filter(item => item.slot === (slot.startsWith('hotbar') ? 'hotbar' : slot));
  }

  function selectedTraits(data, state) {
    return data.tracks.flatMap(track => track.keystones
      .filter(trait => trait.level <= state.levels[track.id])
      .map(trait => ({ ...trait, track: track.name })));
  }

  function budget(data, state) {
    const base = data.characterLevels.find(row => row.level === state.characterLevel)?.totalSkillPoints ?? 0;
    const bonus = selectedTraits(data, state).reduce((sum, trait) => sum + (trait.skillPointsGranted?.value ?? 0), 0);
    return base + bonus;
  }

  function points(data, state) {
    return data.skills.reduce((sum, skill) => sum + (skill.costPerLevel ?? [])
      .slice(0, state.ranks[skill.id] ?? 0).reduce((a, b) => a + b, 0), 0);
  }

  // The source builder treats prerequisites as connected graph edges, not an AND list.
  // Require every learned node to remain connected to a learned root in its tree.
  function disconnected(data, state) {
    const learned = data.skills.filter(skill => state.ranks[skill.id] > 0);
    const reached = new Set(learned.filter(skill => skill.gridY === 0).map(skill => skill.tag));
    let changed = true;
    while (changed) {
      changed = false;
      for (const skill of learned) {
        if (reached.has(skill.tag)) continue;
        const connected = (skill.prerequisites ?? []).some(tag => reached.has(tag))
          || learned.some(other => reached.has(other.tag) && other.skillTree === skill.skillTree
            && (other.prerequisites ?? []).includes(skill.tag));
        if (connected) { reached.add(skill.tag); changed = true; }
      }
    }
    return learned.filter(skill => !reached.has(skill.tag));
  }

  function augmentTraits(data, item) {
    if (!item || item.tier !== 6 || item.rarity !== 'Unique' || itemGroup(item) === 'utility') return [];
    const key = { armor: 'ArmorAugmentLimit', melee: 'MeleeWeaponAugmentLimit', ranged: 'RangedWeaponAugmentLimit' }[itemGroup(item)];
    return data.tracks.find(track => track.id === 'craftingtrack').keystones
      .filter(trait => (trait.stats ?? []).some(stat => stat.key === key)).sort((a, b) => a.level - b.level);
  }

  function augmentLimit(data, state, item) {
    const purchased = new Set(selectedTraits(data, state).map(trait => trait.id));
    return augmentTraits(data, item).filter(trait => purchased.has(trait.id))
      .flatMap(trait => trait.stats).filter(stat => stat.key.endsWith('AugmentLimit'))
      .reduce((sum, stat) => sum + stat.value, 0);
  }

  const weaponFamilies = {
    br: 'battleRifle', fireballer: 'Fireballer', flamethrower: 'Flamethrower',
    heavypistol: 'Heavy.Pistol', lasgun: 'Lasgun', lmg: 'LMG', maulapistol: 'Light.Pistol',
    rocketlauncher: 'RocketLauncher', scattergun: 'Light.Shotgun', shotgun: 'Heavy.Shotgun',
    smg: 'SMG', spitdartrifle: 'SpitDart', spitdart: 'SpitDart',
  };

  function compatibleAugments(data, item) {
    if (!item || item.tier !== 6 || item.rarity !== 'Unique') return [];
    const group = itemGroup(item);
    return data.augments.filter(augment => {
      const category = augment.categories.at(-1).split('/').at(-1);
      if (category !== 'misc' && category !== group) return false;
      if (group === 'utility') return false;
      const family = augment.id.replace(/^t6_augment_(ch5_)?/, '').replace(/\d+$/, '');
      const required = weaponFamilies[family];
      return !required || item.tags.some(tag => tag.toLowerCase().includes(required.toLowerCase()));
    });
  }

  function validateSkills(data, state) {
    const errors = [];
    if (points(data, state) > budget(data, state)) errors.push(`Skill points exceed the budget by ${points(data, state) - budget(data, state)}.`);
    for (const skill of disconnected(data, state)) errors.push(`${skill.name} needs a connected learned prerequisite.`);
    for (const skill of data.skills) {
      const rank = state.ranks[skill.id] ?? 0;
      if (rank < 0 || rank > skill.maxLevel || !Number.isInteger(rank)) errors.push(`${skill.name} has an invalid rank.`);
      if (rank && !skill.gameModes.includes(state.gameMode)) errors.push(`${skill.name} is unavailable in this game mode.`);
    }
    for (const [kind, list] of [['Ability', state.abilities], ['Technique', state.techniques]]) {
      const used = list.filter(Boolean);
      if (new Set(used).size !== used.length) errors.push(`Each ${kind.toLowerCase()} can only be equipped once.`);
      if (kind === 'Ability' && used.length > state.abilitySlots) errors.push('Too many abilities for the unlocked ability slots.');
      if (kind === 'Ability' && list.some((id, index) => id && index >= state.abilitySlots)) errors.push('An equipped ability occupies a locked slot. Unlock that slot or clear the ability.');
      if (kind === 'Technique' && used.length > 3) errors.push('At most three techniques can be equipped.');
      for (const id of used) {
        const skill = skillById(data, id);
        if (!skill || skill.skillType !== kind || !state.ranks[id]) errors.push(`Equipped ${kind.toLowerCase()} must be learned.`);
      }
    }
    return errors;
  }

  function validate(data, state) {
    const errors = validateSkills(data, state);
    const chest = itemById(data, state.equipment.chest.id);
    if (chest?.blocksLegs && state.equipment.legs.id) errors.push('The selected body garment occupies chest and legs. Remove the separate leg piece.');
    for (const [slot, selection] of Object.entries(state.equipment)) {
      if (!selection.id) continue;
      const item = itemById(data, selection.id);
      if (!item || !compatibleItems(data, slot).some(candidate => candidate.id === item.id)) {
        errors.push(`Invalid equipment in ${slot}.`); continue;
      }
      if (selection.grade && !item.scaledStats.some(row => row.grade === selection.grade)) errors.push(`${item.name} does not support that grade.`);
      const augments = selection.augments.filter(augment => augment?.id);
      if (augments.length > augmentLimit(data, state, item)) errors.push(`${item.name} exceeds the unlocked augmentation limit.`);
      if (new Set(augments.map(augment => augment.id)).size !== augments.length) errors.push(`${item.name} has a duplicate augment.`);
      for (const selected of augments) {
        const augment = compatibleAugments(data, item).find(candidate => candidate.id === selected.id);
        if (!augment || !augment.stats.every(stat => stat.values.some(row => row.quality === selected.grade))) errors.push(`${item.name} has an incompatible augment or grade.`);
        if (!Number.isFinite(selected.roll) || selected.roll < 0 || selected.roll > 100) errors.push('Augment roll must be between 0 and 100.');
      }
    }
    return errors;
  }

  function equip(data, state, slot, id) {
    const next = clone(state);
    if (!slots.includes(slot) || (id && !compatibleItems(data, slot).some(item => item.id === id))) return { error: 'Choose equipment compatible with this slot.' };
    if (slot === 'legs' && id && itemById(data, next.equipment.chest.id)?.blocksLegs) return { error: 'Remove the chest garment before equipping separate legs.' };
    next.equipment[slot] = { id, grade: 0, augments: [] };
    if (slot === 'chest' && itemById(data, id)?.blocksLegs) next.equipment.legs = { id: '', grade: 0, augments: [] };
    return { state: next };
  }

  function rank(data, state, id, value) {
    const skill = skillById(data, id);
    if (!skill || !Number.isInteger(value) || value < 0 || value > skill.maxLevel) return { error: 'Choose a valid skill rank.' };
    if (value > (state.ranks[id] ?? 0) && value && skill.gridY > 0
      && !(skill.prerequisites ?? []).some(tag => data.skills.some(other => other.tag === tag && state.ranks[other.id] > 0))) {
      return { error: `Learn a connected prerequisite before ${skill.name}.` };
    }
    const next = clone(state);
    next.ranks[id] = value;
    if (!value) {
      next.abilities = next.abilities.map(selected => selected === id ? '' : selected);
      next.techniques = next.techniques.map(selected => selected === id ? '' : selected);
    }
    // Skill edits do not change equipment compatibility or Crafting unlocks.
    // Keep those errors visible in validate(), without freezing unrelated ranks.
    const errors = validateSkills(data, next).filter(error => !(value < (state.ranks[id] ?? 0) && error.startsWith('Skill points exceed')));
    return errors.length ? { error: errors[0] } : { state: next };
  }

  function mode(data, state, gameMode) {
    const next = clone(state);
    next.gameMode = gameMode;
    for (const skill of data.skills.filter(skill => !skill.gameModes.includes(gameMode))) next.ranks[skill.id] = 0;
    for (const skill of disconnected(data, next)) next.ranks[skill.id] = 0;
    next.abilities = next.abilities.map(id => next.ranks[id] ? id : '');
    next.techniques = next.techniques.map(id => next.ranks[id] ? id : '');
    return next;
  }

  // Explicit translation from game attribute names to the catalog's presentation keys.
  const aliases = {
    ArmorValue: ['armorValue'], Damage: ['damagePerShot', 'damagePerHit', 'heavyAttackDamage', 'heavyAttackDamageUnshielded'],
    ShieldDamage: ['shieldDamagePerShot', 'shieldDamagePerHit'], ShotsPerSecond: ['rateOfFire'],
    ReloadTime: ['reloadSpeed'], MaxAmmo: ['clipSize'], EffectiveRange: ['effectiveRange'],
    PowerConsumptionPerShot: ['powerConsumption'], Volume: ['volume'],
    AttackStaminaBaseCost: ['attackStaminaCost'], BlockStaminaCost: ['blockStaminaCost'],
    PhysicalDamageMitigation: ['concussiveMitigation'], EnergyDamageMitigation: ['energyMitigation'],
    HeatDamageMitigation: ['heatMitigation'], RadiationDamageMitigation: ['radiationMitigation'],
    MeleeDamageMitigation: ['bladeMitigation'], DartDamageMitigation: ['lightDartMitigation', 'heavyDartMitigation'],
    PoisonDamageMitigation: ['poisonMitigation'],
  };

  function itemStats(data, selection) {
    const item = itemById(data, selection.id);
    if (!item) return { item: null, stats: [], modifiers: [] };
    const rows = clone([...item.stats, { key: 'volume', name: 'Equipment volume', type: 'number', value: item.volume, format: '{v:0.#} V' }]).map(stat => ({ ...stat, base: stat.value, grade: stat.value, modifiers: [] }));
    const gradeStats = item.scaledStats.find(row => row.grade === selection.grade)?.stats ?? [];
    for (const override of gradeStats) {
      const stat = rows.find(row => row.key === override.key);
      if (stat) { stat.value = override.value; stat.grade = override.value; }
    }
    const modifiers = [];
    for (const chosen of selection.augments.filter(augment => augment?.id)) {
      const augment = data.augments.find(candidate => candidate.id === chosen.id);
      if (!augment) continue;
      for (const effect of augment.stats) {
        const range = effect.values.find(row => row.quality === chosen.grade);
        if (!range) continue;
        const value = range.min + (range.max - range.min) * chosen.roll / 100;
        const keys = aliases[effect.key] ?? [];
        const matched = rows.filter(row => keys.includes(row.key) && row.type === 'number');
        const unavailableKey = { ADSBaseAccuracyOffset: 'accuracy', RecoilPitchScalar: 'stability' }[effect.key];
        if (unavailableKey) {
          const row = rows.find(stat => stat.key === unavailableKey);
          if (row) row.value = null;
        }
        const modifier = { name: effect.name.replace(/:$/, ''), source: augment.name,
          value, operation: effect.operation, format: effect.format, applied: matched.length > 0 };
        modifiers.push(modifier);
        for (const row of matched) {
          const before = row.value;
          if (effect.operation === 'multiply') row.value *= value;
          else if (effect.operation === 'add') row.value += value * (row.format?.includes('%') ? 100 : 1);
          else if (effect.operation === 'set') row.value = value;
          row.modifiers.push({ ...modifier, change: row.value - before });
        }
      }
    }
    // Catalog DPS includes weapon-specific behavior. Do not invent a new combat formula.
    for (const row of rows.filter(stat => ['dps', 'effectiveDps'].includes(stat.key))) {
      if (modifiers.length || (selection.grade && !gradeStats.some(stat => stat.key === row.key))) row.value = null;
    }
    return { item, stats: rows, modifiers };
  }

  function modifiers(data, state) {
    const rows = [];
    for (const skill of data.skills) {
      const rank = state.ranks[skill.id] ?? 0;
      const equipped = skill.skillType === 'Attribute' || state.abilities.includes(skill.id) || state.techniques.includes(skill.id);
      if (!rank || !equipped) continue;
      for (const stat of skill.stats.filter(row => row.level === rank)) rows.push({ ...stat,
        source: skill.name, kind: skill.skillType, conditional: skill.skillType !== 'Attribute',
        percentScale: percentPointKeys.has(stat.key) ? 1 : 100 });
    }
    for (const track of data.tracks) {
      for (const stat of track.passiveAttributes ?? []) rows.push({ key: stat.key, name: stat.name,
        value: stat.values[state.levels[track.id]], format: '{v:0.#}%', source: `${track.name} level`, kind: 'Specialization' });
    }
    for (const trait of selectedTraits(data, state)) {
      for (const stat of trait.stats ?? []) rows.push({ ...stat, source: `${trait.track}: ${trait.name}`, kind: 'Trait' });
    }
    return rows;
  }

  function calculate(data, state) {
    const track = data.tracks.find(track => track.id === 'combattrack');
    const level = state.levels.combattrack;
    const passive = key => track.passiveAttributes.find(stat => stat.key === key).values[level];
    const traits = selectedTraits(data, state).filter(trait => trait.track === track.name);
    const bonus = key => traits.flatMap(trait => trait.stats ?? [])
      .filter(stat => stat.key === key).reduce((sum, stat) => sum + stat.value, 0);
    const combat = { level, damageBonus: passive('DamageBonus_SpecTrack'),
      mitigationBonus: passive('TotalDamageMitigation_SpecTrack'),
      healthBonus: bonus('MaxHealth'), staminaBonus: bonus('MaxStamina') };
    const equipment = Object.fromEntries(slots.map(slot => [slot, itemStats(data, state.equipment[slot])]));
    for (const entry of Object.values(equipment)) {
      if (!entry.item || !['ranged', 'melee'].includes(itemGroup(entry.item)) || !combat.damageBonus) continue;
      for (const stat of entry.stats) {
        if (['damagePerShot', 'damagePerHit', 'heavyAttackDamage', 'heavyAttackDamageUnshielded'].includes(stat.key) && Number.isFinite(stat.value)) {
          const before = stat.value;
          stat.value *= 1 + combat.damageBonus;
          stat.modifiers.push({ source: `Combat level ${level} (+${Number((combat.damageBonus * 100).toFixed(2))}% damage)`, change: stat.value - before });
        }
        // Catalog DPS and shield damage have separate source formulas. Only
        // project the sourced Combat bonus onto direct weapon health damage.
        if (['dps', 'effectiveDps'].includes(stat.key)) stat.value = null;
      }
    }
    const armor = bodySlots.reduce((sum, slot) => sum + (equipment[slot].stats.find(stat => stat.key === 'armorValue')?.value ?? 0), 0);
    const volume = Object.values(equipment).reduce((sum, entry) => sum + (entry.stats.find(stat => stat.key === 'volume')?.value ?? 0), 0);
    return { equipment, armor, volume, points: points(data, state), budget: budget(data, state),
      combat, modifiers: modifiers(data, state), errors: validate(data, state) };
  }

  return { slots, bodySlots, initial, fileLimit, serialize, deserialize, itemById, skillById, itemGroup, compatibleItems, compatibleAugments,
    selectedTraits, budget, points, disconnected, augmentTraits, augmentLimit, validate, equip, rank, mode, itemStats, modifiers, calculate, clone };
})();
if (typeof module !== 'undefined') module.exports = DuneBuild;
