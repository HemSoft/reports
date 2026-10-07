const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const Build = require('../../scripts/dune-build/model.js');
const edition = path.resolve(__dirname, '../../editions/dune-awakening-build-editor/2026-10-06');
const data = JSON.parse(fs.readFileSync(path.join(edition, 'payload.json'), 'utf8'));
const url = pathToFileURL(path.join(edition, 'report.html')).href;
const id = name => data.items.find(item => item.name === name).id;
const close = (actual, expected) => expect(actual).toBeCloseTo(expected, 5);

function fullBuild() {
  let state = Build.initial(data);
  const gear = { head: 'Acheronian Helmet', chest: 'Power Harness', hands: 'Circuit Gauntlets',
    legs: 'Acheronian Pants', feet: 'Acheronian Boots', shield: 'Adaptive Holtzman Shield',
    powerpack: 'Accelerator Power Pack', suspensor: 'Sentinel Belt', hotbar1: 'A Dart for Every Man' };
  for (const [slot, name] of Object.entries(gear)) state = Build.equip(data, state, slot, id(name)).state;
  return state;
}

test('source-backed full builds, grade scaling and augment arithmetic stay independent per slot', () => {
  const state = fullBuild();
  // Independently checked source values: 283 + 525 + 263 + 283 + 213.
  close(Build.calculate(data, state).armor, 1567);
  close(Build.calculate(data, state).volume, 9.5);
  state.equipment.hands.grade = 5;
  state.levels.craftingtrack = 10;
  state.equipment.hands.augments = [{ id: 't6_augment_armor6', grade: 1, roll: 100 }];
  close(Build.calculate(data, state).armor, 1765.0736); // 1304 + 443.34 × 1.04.
  expect(Build.validate(data, state)).toEqual([]);
  const suit = Build.equip(data, state, 'chest', id('Slaver Stillsuit Body')).state;
  expect(suit.equipment.legs.id).toBe('');
  close(Build.calculate(data, suit).armor, 1022.0736); // 283 + 65 + 461.0736 + 213.
  expect(Build.equip(data, suit, 'legs', id('Acheronian Pants')).error).toContain('Remove the chest');
  expect(Build.equip(data, state, 'head', id('A Dart for Every Man')).error).toContain('compatible');
  const removed = Build.equip(data, state, 'hands', '').state;
  close(Build.calculate(data, removed).armor, 1304);
  expect(state.equipment.hands.id).toBe(id('Circuit Gauntlets'));
});

test('every equipment choice fits a supported slot and every available grade is finite', () => {
  for (const item of data.items) {
    const slot = item.slot === 'hotbar' ? 'hotbar1' : item.slot;
    const state = Build.equip(data, Build.initial(data), slot, item.id).state;
    expect(state).toBeDefined();
    for (const grade of [0, ...item.scaledStats.map(row => row.grade)]) {
      state.equipment[slot].grade = grade;
      for (const stat of Build.itemStats(data, state.equipment[slot]).stats) {
        if (stat.type === 'number' && stat.value !== null) expect(Number.isFinite(stat.value)).toBe(true);
      }
    }
  }
});

test('source augmentation unlocks cover eligible items and follow specialization levels automatically', () => {
  for (const item of data.items) {
    const traits = Build.augmentTraits(data, item);
    expect(traits.length > 0).toBe(Build.compatibleAugments(data, item).length > 0);
  }
  const state = fullBuild();
  const hands = Build.itemById(data, state.equipment.hands.id);
  const traits = Build.augmentTraits(data, hands);
  expect(traits.map(trait => trait.level)).toEqual([10, 42]);
  state.levels.craftingtrack = 42;
  expect(Build.augmentLimit(data, state, hands)).toBe(2);
  state.levels.craftingtrack = 10;
  expect(Build.augmentLimit(data, state, hands)).toBe(1);
  state.levels.craftingtrack = 9;
  expect(Build.augmentLimit(data, state, hands)).toBe(0);
});

for (const width of [1440, 390]) {
  test(`equipment actions guide locked garment and ranged augments through level entry and removal at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.locator('#gear-hands').selectOption(id('Circuit Gauntlets'));
    await page.locator('#gear-hotbar1').selectOption(id('A Dart for Every Man'));
    const hands = page.getByRole('button', { name: 'Hands augments', exact: true });
    await expect(hands).toBeVisible();
    await expect(hands).toContainText('locked');
    await hands.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`augment-access-${width}.png`) });
    await hands.focus();
    await hands.press('Enter');
    await expect(page.locator('#augment-target')).toHaveValue('hands');
    await expect(page.locator('#inspect-slot')).toHaveValue('hands');
    await expect(page.locator('#augment-target')).toBeFocused();
    await expect(page.locator('#augment-0')).toBeDisabled();
    await expect(page.locator('#augmentation')).toContainText('Requires Crafting level 10 for Garment Augmentation Limit');
    await expect(page.locator('#augmentation')).toContainText('Requires Crafting level 42');
    await page.screenshot({ path: testInfo.outputPath(`augment-locked-${width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Configure Garment Augmentation Limit · level 10', exact: true }).click();
    await expect(page.locator('#level-craftingtrack')).toBeFocused();
    await page.locator('#level-craftingtrack').fill('10');
    await page.locator('#level-craftingtrack').press('Tab');
    await page.getByRole('button', { name: 'Return to Hands augments', exact: true }).click();
    await expect(page.locator('#augment-0')).toBeEnabled();
    await expect(page.locator('#augment-1')).toBeDisabled();
    await page.locator('#augment-0').selectOption('t6_augment_armor6');
    await page.locator('#roll-0').fill('100');
    await page.locator('#roll-0').press('Tab');
    await expect(page.locator('#armor-total')).toHaveText('273.52');
    await expect(page.locator('#item-title')).toHaveText('Hands: Circuit Gauntlets');
    await expect(page.locator('#augment-effect-rows')).toContainText('Garment Reinforcement');
    await page.screenshot({ path: testInfo.outputPath(`augment-garment-${width}.png`), fullPage: width === 1440 });
    await page.locator('#augment-0').selectOption('');
    await expect(page.locator('#armor-total')).toHaveText('263');

    await page.getByRole('button', { name: 'Progression', exact: true }).click();
    await page.locator('#level-craftingtrack').fill('0');
    await page.locator('#level-craftingtrack').press('Tab');
    await page.getByRole('button', { name: 'Equipment', exact: true }).click();
    await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
    await page.getByRole('button', { name: 'Configure Ranged Augmentation Limit · level 1', exact: true }).click();
    await expect(page.locator('#level-craftingtrack')).toBeFocused();
    await page.locator('#level-craftingtrack').fill('1');
    await page.locator('#level-craftingtrack').press('Tab');
    await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
    await page.locator('#augment-0').selectOption('t6_augment_smg1');
    await expect(page.locator('#augment-0')).not.toContainText('Karpov');
    await page.locator('#augment-grade-0').selectOption('3');
    await page.locator('#roll-0').fill('100');
    await page.locator('#roll-0').press('Tab');
    await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Damage Per Shot', exact: true }) }).locator('td').first()).toHaveText('40.66');
    await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Clip Size', exact: true }) }).locator('td').first()).toHaveText('76.8');
    await page.screenshot({ path: testInfo.outputPath(`augment-weapon-${width}.png`), fullPage: width === 1440 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
    await page.locator('#augment-0').selectOption('');
    await expect(page.locator('#item-stat-rows')).toContainText('42.8');
    await page.locator('#augment-0').selectOption('t6_augment_smg1');
    await page.locator('#gear-hotbar1').selectOption(id('Maula Pistol'));
    await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
    await expect(page.locator('#augmentation')).toContainText('Maula Pistol cannot be augmented in this snapshot');
    await expect(page.locator('#augment-0')).toHaveCount(0);
    await page.locator('#gear-hotbar1').selectOption(id('A Dart for Every Man'));
    await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
    await expect(page.locator('#augment-0')).toHaveValue('');
    await page.getByRole('button', { name: 'Reset build', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Hands augments', exact: true })).toHaveCount(0);
    await expect(page.locator('#armor-total')).toHaveText('0');
    expect(errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test('melee augments can be edited and removed after losing a slot unlock', async ({ page }) => {
  await page.goto(url);
  await page.locator('#gear-hotbar1').selectOption(id('Leech’s Maw'));
  await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
  await page.getByRole('button', { name: 'Configure Melee Augmentation Limit · level 3', exact: true }).click();
  await page.locator('#level-craftingtrack').fill('3');
  await page.locator('#level-craftingtrack').press('Tab');
  await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
  await page.locator('#augment-0').selectOption('t6_augment_melee1');
  await page.locator('#roll-0').fill('100');
  await page.locator('#roll-0').press('Tab');
  await expect(page.locator('#augment-effect-rows')).toContainText('Blade Sharpener');
  await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Damage Per Hit', exact: true }) }).locator('td').first()).toHaveText('148.12');
  await page.locator('#augment-grade-0').selectOption('2');
  await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Damage Per Hit', exact: true }) }).locator('td').first()).toHaveText('157.72');
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#level-craftingtrack').fill('0');
  await page.locator('#level-craftingtrack').press('Tab');
  await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
  await expect(page.locator('#build-status')).toHaveText('Invalid build');
  await expect(page.locator('#augment-0')).toBeEnabled();
  await expect(page.locator('#augment-grade-0')).toBeDisabled();
  await page.locator('#augment-0').selectOption('');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
  await expect(page.locator('#augment-0')).toBeDisabled();
  await expect(page.locator('#item-stat-rows')).toContainText('137.15');
  await page.locator('#gear-hotbar1').selectOption('');
  await expect(page.locator('#augment-0')).toHaveCount(0);
});

test('a single augment in a later position stays editable within the reduced slot limit', async ({ page }) => {
  await page.goto(url);
  await page.locator('#gear-hotbar1').selectOption(id('Leech’s Maw'));
  await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
  await page.getByRole('button', { name: 'Configure Melee Augmentation Limit · level 30', exact: true }).click();
  await page.locator('#level-craftingtrack').fill('30');
  await page.locator('#level-craftingtrack').press('Tab');
  await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
  await page.locator('#augment-1').selectOption('t6_augment_melee1');
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#level-craftingtrack').fill('3');
  await page.locator('#level-craftingtrack').press('Tab');
  await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
  await expect(page.locator('#build-status')).toHaveText('Build valid');
  await expect(page.locator('#augment-grade-1')).toBeEnabled();
  await page.locator('#augment-grade-1').selectOption('2');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
});

test('specialization levels activate every eligible trait without purchase state', () => {
  const state = Build.initial(data);
  for (const track of data.tracks) {
    for (const level of [0, 1, 10, 50, 100]) {
      state.levels[track.id] = level;
      const active = Build.selectedTraits(data, state).filter(trait => trait.track === track.name);
      expect(active.map(trait => trait.id)).toEqual(track.keystones.filter(trait => trait.level <= level).map(trait => trait.id));
    }
    state.levels[track.id] = 0;
  }
  state.levels.combattrack = 50;
  expect(Build.budget(data, state)).toBe(28);
  expect(Build.calculate(data, state).combat).toEqual({ level: 50, damageBonus: 0.5, mitigationBonus: 0.25, healthBonus: 20, staminaBonus: 30 });
  state.levels.combattrack = 100;
  expect(Build.budget(data, state)).toBe(55);
  expect(Build.calculate(data, state).combat).toEqual({ level: 100, damageBonus: 1, mitigationBonus: 0.5, healthBonus: 55, staminaBonus: 55 });
  state.levels.combattrack = 0;
  expect(Build.selectedTraits(data, state)).toEqual([]);
  expect(Build.budget(data, state)).toBe(1);
});

test('Combat damage applies once after equipment grades and augments without changing carried weapons or defenses', () => {
  let state = Build.initial(data);
  state = Build.equip(data, state, 'hotbar1', id('A Dart for Every Man')).state;
  state = Build.equip(data, state, 'hotbar2', id('Leech’s Maw')).state;
  state = Build.equip(data, state, 'hands', id('Circuit Gauntlets')).state;
  const damage = (slot, key) => Build.calculate(data, state).equipment[slot].stats.find(stat => stat.key === key).value;
  state.levels.combattrack = 50;
  close(damage('hotbar1', 'damagePerShot'), 64.2);
  close(damage('hotbar2', 'damagePerHit'), 205.725);
  close(damage('hands', 'armorValue'), 263);
  close(damage('hotbar1', 'shieldDamagePerShot'), 25);
  expect(damage('hotbar1', 'dps')).toBeNull();
  state.equipment.hotbar1.grade = 1;
  close(damage('hotbar1', 'damagePerShot'), 68.7);
  state.equipment.hotbar1.grade = 0;
  state.levels.craftingtrack = 10;
  state.equipment.hotbar1.augments = [{ id: 't6_augment_smg1', grade: 3, roll: 100 }];
  close(damage('hotbar1', 'damagePerShot'), 60.99);
  close(damage('hotbar2', 'damagePerHit'), 205.725);
  expect(Build.calculate(data, state).errors).toEqual([]);
  state.levels.combattrack = 100;
  close(damage('hotbar1', 'damagePerShot'), 81.32);
  state.levels.combattrack = 0;
  close(damage('hotbar1', 'damagePerShot'), 40.66);
  state.equipment.hotbar1.augments = [];
  close(damage('hotbar1', 'damagePerShot'), 42.8);
  close(damage('hotbar1', 'dps'), 428);
});

for (const width of [1440, 390]) {
  test(`Combat and Crafting levels automatically update traits and weapon damage at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.locator('#gear-hotbar1').selectOption(id('A Dart for Every Man'));
    await page.getByRole('button', { name: 'Progression', exact: true }).click();
    await expect(page.locator('#track-rows h3')).toHaveText(['Crafting', 'Gathering', 'Exploration', 'Combat', 'Sabotage']);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`specialization-order-${width}.png`), fullPage: true });
    await page.locator('#level-combattrack').fill('50');
    await page.locator('#level-combattrack').press('Tab');
    await expect(page.locator('#point-count')).toHaveText('0 / 28 skill points');
    await expect(page.locator('#combat-damage')).toHaveText('50%');
    await expect(page.locator('#combat-mitigation')).toHaveText('25%');
    await expect(page.locator('#combat-health')).toHaveText('+20');
    await expect(page.locator('#combat-stamina')).toHaveText('+30');
    await expect(page.locator('#track-rows input[type="checkbox"]')).toHaveCount(0);
    const combat = page.locator('.track').filter({ has: page.getByRole('heading', { name: 'Combat', exact: true }) });
    await combat.locator('summary').click();
    await expect(combat.locator('summary')).toHaveText('Traits · 20 active');
    await combat.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`automatic-traits-${width}.png`) });
    await page.getByRole('button', { name: 'Equipment', exact: true }).click();
    await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
    const damage = page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Damage Per Shot', exact: true }) });
    await expect(damage.locator('td').first()).toHaveText('64.2');
    await expect(damage).toContainText('Combat level 50 (+50% damage)');
    await page.getByRole('button', { name: 'Configure Ranged Augmentation Limit · level 1', exact: true }).click();
    await expect(page.locator('#level-craftingtrack')).toBeFocused();
    await page.locator('#level-craftingtrack').fill('1');
    await page.locator('#level-craftingtrack').press('Tab');
    await page.getByRole('button', { name: 'Return to Quickbar 1 augments', exact: true }).click();
    await expect(page.locator('#augment-0')).toBeEnabled();
    await page.locator('#augment-0').selectOption('t6_augment_smg1');
    await page.locator('#augment-grade-0').selectOption('3');
    await page.locator('#roll-0').fill('100');
    await page.locator('#roll-0').press('Tab');
    await expect(damage.locator('td').first()).toHaveText('60.99');
    if (width === 390) {
      await page.locator('#stats-heading').scrollIntoViewIfNeeded();
      await page.screenshot({ path: testInfo.outputPath('combat-summary-390.png') });
      await damage.scrollIntoViewIfNeeded();
    }
    await page.screenshot({ path: testInfo.outputPath(`combat-damage-${width}.png`), fullPage: width === 1440 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Progression', exact: true }).click();
    await page.locator('#level-combattrack').fill('100');
    await page.locator('#level-combattrack').press('Tab');
    await expect(page.locator('#point-count')).toHaveText('0 / 55 skill points');
    await expect(damage.locator('td').first()).toHaveText('81.32');
    await page.locator('#level-combattrack').fill('0');
    await page.locator('#level-combattrack').press('Tab');
    await expect(damage.locator('td').first()).toHaveText('40.66');
    await expect(page.locator('#combat-damage')).toHaveText('0%');
    await page.getByRole('button', { name: 'Equipment', exact: true }).click();
    await page.locator('#augment-0').selectOption('');
    await expect(damage.locator('td').first()).toHaveText('42.8');
    expect(errors).toEqual([]);
  });
}

test('skill prerequisites, cumulative costs, automatic traits and reductions preserve valid builds', () => {
  let state = Build.initial(data);
  expect(Build.rank(data, state, 'skills-ability-assaultseeker', 1).error).toContain('prerequisite');
  state = Build.rank(data, state, 'skills-attribute-weaponry1', 1).state;
  expect(Build.points(data, state)).toBe(1);
  expect(Build.rank(data, state, 'skills-attribute-weaponry1', 2).error).toContain('budget');
  state.characterLevel = 20;
  state = Build.rank(data, state, 'skills-attribute-weaponry1', 3).state;
  expect(Build.points(data, state)).toBe(8);
  close(Build.modifiers(data, state).find(row => row.key === 'RangedDamageBonus').value, 0.09);
  state = Build.rank(data, state, 'skills-attribute-blade1', 2).state;
  expect(Build.points(data, state)).toBe(12);
  state.characterLevel = 1;
  expect(Build.validate(data, state)).toContain('Skill points exceed the budget by 11.');
  state = Build.rank(data, state, 'skills-attribute-weaponry1', 1).state;
  expect(state).toBeDefined(); // Budget can be repaired in several rank reductions.
  state = Build.rank(data, state, 'skills-attribute-blade1', 0).state;
  expect(Build.validate(data, state)).toEqual([]);
  state.levels.combattrack = 100;
  expect(Build.budget(data, state)).toBe(55); // 1 character point + 54 automatic Combat points.
  state.levels.combattrack = 0;
  expect(Build.budget(data, state)).toBe(1);
});

test('weapon-family augments, minimum grades, penalties and unknown formulas are explicit', () => {
  const state = fullBuild();
  const item = Build.itemById(data, state.equipment.hotbar1.id);
  const compatible = Build.compatibleAugments(data, item).map(augment => augment.id);
  expect(compatible).toContain('t6_augment_smg1');
  expect(compatible).not.toContain('t6_augment_br1');
  expect(compatible).not.toContain('t6_augment_armor6');
  state.equipment.hotbar1.grade = 1;
  const graded = Build.calculate(data, state).equipment.hotbar1.stats;
  close(graded.find(stat => stat.key === 'dps').value, 457.96);
  close(graded.find(stat => stat.key === 'effectiveDps').value, 348.93);
  state.equipment.hotbar1.grade = 0;
  state.levels.craftingtrack = 1;
  state.equipment.hotbar1.augments = [{ id: 't6_augment_smg1', grade: 3, roll: 100 }];
  const result = Build.calculate(data, state);
  const stats = result.equipment.hotbar1.stats;
  close(stats.find(stat => stat.key === 'damagePerShot').value, 40.66); // 42.8 × 0.95.
  close(stats.find(stat => stat.key === 'clipSize').value, 76.8); // 48 × 1.6.
  expect(stats.find(stat => stat.key === 'dps').value).toBeNull();
  expect(stats.find(stat => stat.key === 'accuracy').value).toBeNull();
  expect(stats.find(stat => stat.key === 'stability').value).toBeNull();
  expect(Build.validate(data, state)).toEqual([]);
  state.equipment.hotbar2 = { id: item.id, grade: 0, augments: [] };
  close(Build.calculate(data, state).equipment.hotbar2.stats.find(stat => stat.key === 'damagePerShot').value, 42.8);
  state.equipment.hotbar1.augments[0].grade = 1;
  expect(Build.validate(data, state).join(' ')).toContain('incompatible augment or grade');
  state.equipment.hotbar1.augments[0].grade = 3;
  state.levels.craftingtrack = 0;
  expect(Build.validate(data, state).join(' ')).toContain('augmentation limit');
});

test('equipped abilities and techniques require learned skills and retain their conditional effects', () => {
  let state = Build.initial(data);
  state.characterLevel = 30;
  for (const skill of ['skills-ability-cablepull', 'skills-ability-fraggrenade', 'skills-attribute-weaponry1', 'skills-perk-bodyshots']) {
    state = Build.rank(data, state, skill, 1).state;
    expect(state).toBeDefined();
  }
  state.abilities[0] = 'skills-ability-fraggrenade';
  state.techniques[0] = 'skills-perk-bodyshots';
  expect(Build.validate(data, state)).toEqual([]);
  expect(Build.modifiers(data, state).filter(row => row.source === 'Center of Mass').every(row => row.conditional)).toBe(true);
  expect(Build.rank(data, state, 'skills-ability-cablepull', 0).error).toContain('prerequisite');
  state.abilities[1] = 'skills-ability-fraggrenade';
  expect(Build.validate(data, state).join(' ')).toContain('only be equipped once');
  state.abilities[1] = 'skills-ability-cablepull';
  state.abilitySlots = 1;
  expect(Build.validate(data, state).join(' ')).toContain('Too many abilities');
  state.abilitySlots = 3;
  state.abilities[1] = '';
  state = Build.rank(data, state, 'skills-perk-bodyshots', 0).state;
  expect(state.techniques[0]).toBe('');
  expect(Build.modifiers(data, state).filter(row => row.source === 'Center of Mass')).toEqual([]);
});

test('all body, utility and quickbar slots update and remove their selected pieces', async ({ page }) => {
  await page.goto(url);
  for (const slot of Build.slots) {
    const item = Build.compatibleItems(data, slot).find(candidate => !candidate.blocksLegs);
    await page.locator(`#gear-${slot}`).selectOption(item.id);
    await expect(page.locator('#item-title')).toContainText(item.name);
    await page.locator(`#gear-${slot}`).selectOption('');
    await expect(page.locator(`#gear-${slot}`)).toHaveValue('');
    await expect(page.locator('#volume-total')).toHaveText('0 V');
  }
});

test('an over-budget build suppresses totals and can be repaired with rank reductions', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.getByLabel('Character level', { exact: true }).fill('20');
  await page.getByLabel('Character level', { exact: true }).press('Tab');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.getByLabel('Ranged Damage rank', { exact: true }).selectOption('3');
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.getByLabel('Character level', { exact: true }).fill('1');
  await page.getByLabel('Character level', { exact: true }).press('Tab');
  await expect(page.locator('#build-status')).toHaveText('Invalid build');
  await expect(page.locator('#errors')).toContainText('exceed the budget by 7');
  await expect(page.locator('#armor-total')).toHaveText('Unavailable');
  await page.screenshot({ path: testInfo.outputPath('build-invalid-budget-1440.png'), fullPage: false });
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.getByLabel('Ranged Damage rank', { exact: true }).selectOption('2');
  await expect(page.getByLabel('Ranged Damage rank', { exact: true })).toHaveValue('2');
  await page.getByLabel('Ranged Damage rank', { exact: true }).selectOption('1');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
});

test('editor works offline, updates totals, filters gear, rejects invalid skills and resets', async ({ browser }) => {
  const context = await browser.newContext({ offline: true });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await expect(page.locator('#coverage')).toContainText('573 equipment choices');
  await expect(page.locator('#skill-tree option')).toHaveCount(5);
  await expect(page.locator('#skill-tree')).not.toContainText('Hidden');
  await page.getByLabel('Head equipment', { exact: true }).selectOption(id('Acheronian Helmet'));
  await page.getByLabel('Hands equipment', { exact: true }).selectOption(id('Circuit Gauntlets'));
  await expect(page.locator('#armor-total')).toHaveText('546');
  await page.getByLabel('Hands item grade', { exact: true }).selectOption('5');
  await expect(page.locator('#armor-total')).toHaveText('726.34');
  await page.getByLabel('Legs equipment', { exact: true }).selectOption(id('Acheronian Pants'));
  await page.getByLabel('Chest / body equipment', { exact: true }).selectOption(id('Slaver Stillsuit Body'));
  await expect(page.getByLabel('Legs equipment', { exact: true })).toBeDisabled();
  await expect(page.locator('#armor-total')).toHaveText('791.34');
  await page.getByLabel('Find equipment').fill('circuit');
  await expect(page.getByLabel('Hands equipment', { exact: true }).locator('option')).toHaveCount(2);
  await page.getByLabel('Find equipment').fill('');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.getByLabel('Assault Seeker rank', { exact: true }).selectOption('1');
  await expect(page.locator('#message')).toContainText('prerequisite');
  await expect(page.getByLabel('Assault Seeker rank', { exact: true })).toHaveValue('0');
  await page.getByLabel('Ranged Damage rank', { exact: true }).selectOption('1');
  await expect(page.locator('#point-count')).toHaveText('1 / 1 skill points');
  await page.getByLabel('Ranged Damage rank', { exact: true }).selectOption('2');
  await expect(page.locator('#message')).toContainText('budget');
  await page.getByRole('button', { name: 'Reset build' }).click();
  await expect(page.locator('#armor-total')).toHaveText('0');
  await expect(page.locator('#point-count')).toHaveText('0 / 1 skill points');
  await expect(page.getByLabel('Ranged Damage rank', { exact: true })).toHaveValue('0');
  await expect(page.getByRole('link', { name: 'All reports', exact: true })).toHaveAttribute('href', '../../../');
  expect(errors).toEqual([]);
  await context.close();
});

test('specialization levels automatically unlock augmentation and update source-backed values', async ({ page }) => {
  await page.goto(url);
  await page.getByLabel('Hands equipment', { exact: true }).selectOption(id('Circuit Gauntlets'));
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.getByLabel('Crafting level', { exact: true }).fill('10');
  await page.getByLabel('Crafting level', { exact: true }).press('Tab');
  const track = page.locator('.track').filter({ has: page.getByRole('heading', { name: 'Crafting', exact: true }) });
  await track.getByText('Traits · 5 active', { exact: true }).click();
  await expect(track.getByRole('checkbox')).toHaveCount(0);
  await page.getByRole('button', { name: 'Equipment', exact: true }).click();
  await page.locator('#augmentation summary').click();
  await page.locator('#augment-0').selectOption('t6_augment_armor6');
  await page.locator('#roll-0').fill('100');
  await page.locator('#roll-0').press('Tab');
  await expect(page.locator('#armor-total')).toHaveText('273.52');
  await expect(page.locator('#item-stat-rows')).toContainText('Garment Reinforcement');
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.getByLabel('Crafting level', { exact: true }).fill('0');
  await page.getByLabel('Crafting level', { exact: true }).press('Tab');
  await expect(page.locator('#build-status')).toHaveText('Invalid build');
  await expect(page.locator('#armor-total')).toHaveText('Unavailable');
  await page.locator('#character-level').fill('20');
  await page.locator('#character-level').press('Tab');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.locator('#rank-skills-attribute-weaponry1').selectOption('2');
  await expect(page.locator('#rank-skills-attribute-weaponry1')).toHaveValue('2');
  await expect(page.locator('#point-count')).toHaveText('4 / 20 skill points');
  await expect(page.locator('#build-status')).toHaveText('Invalid build');
  await page.locator('#rank-skills-attribute-weaponry1').selectOption('0');
  await expect(page.locator('#rank-skills-attribute-weaponry1')).toHaveValue('0');
});

test('welding torch P0 repair-quality formats display fractional percentages', async ({ page }) => {
  await page.goto(url);
  for (const [item, value] of [['repairtool', '70%'], ['repairtool3', '80%'], ['repairtool5', '90%']]) {
    await page.locator('#gear-hotbar1').selectOption(item);
    await expect(page.locator('#item-stat-rows tr').filter({ hasText: 'Repair Quality' }).locator('td').first()).toHaveText(value);
  }
});

test('source-provided weapon grade DPS remains visible without augments', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(url);
  await page.locator('#gear-hotbar1').selectOption(id('A Dart for Every Man'));
  await page.locator('#grade-hotbar1').selectOption('1');
  await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'DPS', exact: true }) }).locator('td').first()).toHaveText('457.96');
  await expect(page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Effective DPS', exact: true }) }).locator('td').first()).toHaveText('348.93');
  await page.screenshot({ path: testInfo.outputPath('build-grade-dps-1440.png'), fullPage: true });
});

test('skill percentages retain point units while fractional bonuses scale once', async ({ page }) => {
  await page.goto(url);
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#character-level').fill('200');
  await page.locator('#character-level').press('Tab');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.locator('#skill-tree').selectOption('BeneGesserit');
  await page.locator('#rank-skills-attribute-selfcontrol1').selectOption('1');
  await page.locator('#rank-skills-attribute-selfcontrol2').selectOption('1');
  for (const [rank, value] of [['1', '20%'], ['2', '30%'], ['3', '45%']]) {
    await page.locator('#rank-skills-attribute-selfcontrol5').selectOption(rank);
    await expect(page.locator('#modifier-rows tr').filter({ hasText: 'Poison Tolerance' }).locator('td:first-of-type')).toHaveText([value, value]);
  }
  await page.locator('#skill-tree').selectOption('Planetologist');
  await page.locator('#rank-skills-attribute-scientist1').selectOption('1');
  await expect(page.locator('#modifier-rows tr').filter({ hasText: 'Hand-held Cutteray Yield' }).locator('td').first()).toHaveText('2.5%');
  await page.locator('#skill-tree').selectOption('Trooper');
  await page.locator('#rank-skills-attribute-weaponry1').selectOption('3');
  await expect(page.locator('#modifier-rows tr').filter({ hasText: 'Ranged Damage' }).locator('td').first()).toHaveText('9%');
});

test('choosing later augment slots first remains safe through cloned build edits', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await page.locator('#gear-hands').selectOption(id('Circuit Gauntlets'));
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#character-level').fill('200');
  await page.locator('#character-level').press('Tab');
  await page.getByLabel('Crafting level', { exact: true }).fill('100');
  await page.getByLabel('Crafting level', { exact: true }).press('Tab');
  await page.getByRole('button', { name: 'Equipment', exact: true }).click();
  await page.locator('#augmentation summary').click();
  await page.locator('#augment-1').selectOption('t6_augment_armor6');
  await page.locator('#gear-head').selectOption(id('Acheronian Helmet'));
  await expect(page.locator('#build-status')).toHaveText('Build valid');
  await page.locator('#gear-hotbar1').selectOption(id('A Dart for Every Man'));
  await page.locator('#augment-target').selectOption('hotbar1');
  await page.locator('#augment-2').selectOption('t6_augment_smg1');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.locator('#rank-skills-attribute-weaponry1').selectOption('1');
  await page.locator('#rank-skills-ability-cablepull').selectOption('1');
  await page.locator('#ability-0').selectOption('skills-ability-cablepull');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
  expect(errors).toEqual([]);
});

test('switching modes removes incompatible and orphaned skills while keeping learned roots', async ({ page }) => {
  await page.goto(url);
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#character-level').fill('30');
  await page.locator('#character-level').press('Tab');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await page.locator('#skill-tree').selectOption('Planetologist');
  await page.locator('#rank-skills-ability-suspensorpad').selectOption('1');
  await page.locator('#rank-skills-attribute-explorer1').selectOption('1');
  await page.locator('#rank-skills-attribute-explorer3').selectOption('1');
  await page.locator('#ability-0').selectOption('skills-ability-suspensorpad');
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.locator('#game-mode').selectOption('singleplayer');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
  await expect(page.locator('#point-count')).toHaveText('1 / 30 skill points');
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  await expect(page.locator('#rank-skills-attribute-explorer3')).toHaveValue('0');
  await expect(page.locator('#rank-skills-ability-suspensorpad')).toHaveValue('1');
  await expect(page.locator('#ability-0')).toHaveValue('skills-ability-suspensorpad');
  await page.locator('#rank-skills-attribute-explorer6').selectOption('1');
  await page.locator('#rank-skills-attribute-explorer3').selectOption('1');
  await expect(page.locator('#build-status')).toHaveText('Build valid');
});

test('desktop and mobile editor states fit their viewports and pass accessibility checks', async ({ page }, testInfo) => {
  await page.goto(url);
  for (const width of [1440, 1000, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    for (const view of ['Equipment', 'Skills', 'Progression']) {
      await page.getByRole('button', { name: view, exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      expect(scan.violations).toEqual([]);
    }
    await page.getByRole('button', { name: 'Equipment', exact: true }).click();
    if (width === 1440 || width === 390) {
      await page.screenshot({ path: testInfo.outputPath(`build-empty-${width}.png`), fullPage: false });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const [slot, item] of Object.entries(fullBuild().equipment).filter(([, selected]) => selected.id)) {
    await page.locator(`#gear-${slot}`).selectOption(item.id);
  }
  await expect(page.locator('#armor-total')).toHaveText('1,567');
  await page.screenshot({ path: testInfo.outputPath('build-configured-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#stats-heading').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('build-configured-390.png'), fullPage: false });
});
