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
  state.traits = ['Crafting_CraftingKeystone_ArmoirAugmentSlots10'];
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

test('skill prerequisites, cumulative costs, purchased traits and reductions preserve valid builds', () => {
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
  expect(Build.budget(data, state)).toBe(1);
  state.traits = data.tracks.find(track => track.id === 'combattrack').keystones
    .filter(trait => trait.skillPointsGranted).map(trait => trait.id);
  expect(Build.budget(data, state)).toBe(55); // 1 character point + 54 purchased combat points.
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
  state.levels.craftingtrack = 1;
  state.traits = ['Crafting_CraftingKeystone_RangedWeaponAugmentSlots1'];
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
  state.traits = [];
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

test('augmentation and trait controls support keyboard focus and update source-backed values', async ({ page }) => {
  await page.goto(url);
  await page.getByLabel('Hands equipment', { exact: true }).selectOption(id('Circuit Gauntlets'));
  await page.getByRole('button', { name: 'Progression', exact: true }).click();
  await page.getByLabel('Crafting level', { exact: true }).fill('10');
  await page.getByLabel('Crafting level', { exact: true }).press('Tab');
  const track = page.locator('.track').filter({ has: page.getByRole('heading', { name: 'Crafting', exact: true }) });
  await track.getByText('Traits · 0 purchased', { exact: true }).click();
  await page.locator('#trait-Crafting_CraftingKeystone_ArmoirAugmentSlots10').check();
  await expect(page.locator('#trait-Crafting_CraftingKeystone_ArmoirAugmentSlots10')).toBeFocused();
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
