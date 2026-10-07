const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const Build = require('../../scripts/dune-build/model.js');
const edition = path.resolve(__dirname, '../../editions/dune-awakening-build-editor/2026-10-06');
const data = JSON.parse(fs.readFileSync(path.join(edition, 'payload.json'), 'utf8'));
const url = pathToFileURL(path.join(edition, 'report.html')).href;
const itemId = name => data.items.find(item => item.name === name).id;
const fileInput = (text, name = 'build.json') => ({ name, mimeType: 'application/json', buffer: Buffer.from(text) });

function savedBuild() {
  let state = Build.initial(data);
  for (const slot of Build.slots) {
    const item = Build.compatibleItems(data, slot).find(item => !item.blocksLegs);
    state = Build.equip(data, state, slot, item.id).state;
  }
  state = Build.equip(data, state, 'hands', itemId('Circuit Gauntlets')).state;
  state = Build.equip(data, state, 'hotbar1', itemId('A Dart for Every Man')).state;
  state.equipment.hands.grade = 5;
  state.equipment.hands.augments = [{ id: 't6_augment_armor6', grade: 1, roll: 37.5 }];
  state.equipment.hotbar1.augments = [{ id: '', grade: 1, roll: 0 }, { id: 't6_augment_smg1', grade: 3, roll: 100 }];
  Object.assign(state.levels, { explorationtrack: 10, gatheringtrack: 20, sabotagetrack: 30, combattrack: 50, craftingtrack: 42 });
  state.characterLevel = 30;
  state.abilitySlots = 2;
  state.gameMode = 'singleplayer';
  for (const id of ['skills-ability-cablepull', 'skills-ability-fraggrenade', 'skills-attribute-weaponry1', 'skills-perk-bodyshots']) {
    state = Build.rank(data, state, id, 1).state;
    expect(state).toBeDefined();
  }
  state.abilities[0] = 'skills-ability-fraggrenade';
  state.techniques[0] = 'skills-perk-bodyshots';
  return state;
}

async function downloadBuild(page) {
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save build', exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^dune-build-.*\.json$/);
  return fs.readFileSync(await file.path(), 'utf8');
}

async function loadBuild(page, text) {
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Load build', exact: true }).click();
  await (await chooser).setFiles(fileInput(text));
  await expect(page.getByRole('button', { name: 'Load build', exact: true })).toBeEnabled();
  await expect(page.locator('#message')).not.toHaveText('Loading build file…');
}

test('build files round-trip every selection and recompute Combat damage without storing derived traits', () => {
  const state = savedBuild();
  expect(Build.validate(data, state)).toEqual([]);
  const text = Build.serialize(data, state);
  const file = JSON.parse(text);
  expect(file.format).toBe('hemsoft-dune-build');
  expect(file.version).toBe(1);
  expect(file.gameVersion).toBe('1.5.3.6');
  expect(file.build).not.toHaveProperty('traits');
  expect(file.build).not.toHaveProperty('combat');
  expect(Buffer.byteLength(text)).toBeLessThan(Build.fileLimit);
  const result = Build.deserialize(data, text);
  expect(result.state).toEqual(state);
  expect(result.state).not.toBe(state);
  expect(Build.calculate(data, result.state)).toEqual(Build.calculate(data, state));
  expect(Build.calculate(data, result.state).equipment.hotbar1.stats.find(stat => stat.key === 'damagePerShot').value).toBeCloseTo(60.99, 5);
  expect(Build.deserialize(data, Build.serialize(data, Build.initial(data))).state).toEqual(Build.initial(data));
});

test('load preserves unfinished builds and their existing rule warnings', () => {
  const state = savedBuild();
  state.levels.craftingtrack = 0;
  state.characterLevel = 1;
  state.levels.combattrack = 0;
  const warnings = Build.validate(data, state);
  expect(warnings.join(' ')).toContain('augmentation limit');
  expect(warnings.join(' ')).toContain('budget');
  const result = Build.deserialize(data, Build.serialize(data, state));
  expect(result.state).toEqual(state);
  expect(Build.validate(data, result.state)).toEqual(warnings);
});

test('load rejects malformed, unsupported and hostile fields before exposing a new state', () => {
  const state = savedBuild();
  const original = Build.serialize(data, state);
  for (const mutate of [
    file => { file.format = 'other-editor'; },
    file => { file.version = 2; },
    file => { file.gameVersion = 'other-version'; },
    file => { file.build = null; },
    file => { delete file.build.equipment.head; },
    file => { file.build.equipment.extra = file.build.equipment.head; },
    file => { file.build.equipment.head.id = '<img src=x onerror=alert(1)>'; },
    file => { file.build.equipment.head.id = itemId('A Dart for Every Man'); },
    file => { file.build.equipment.hands.grade = 999; },
    file => { file.build.equipment.hands.augments = {}; },
    file => { file.build.equipment.hands.augments = Array(4).fill(null); },
    file => { file.build.equipment.hands.augments[0].id = 't6_augment_smg1'; },
    file => { file.build.equipment.hotbar1.augments[1].grade = 1; },
    file => { file.build.equipment.hotbar1.augments[1].roll = 101; },
    file => { file.build.equipment.hotbar1.augments[1].roll = '50'; },
    file => { file.build.levels.combattrack = 101; },
    file => { file.build.levels.craftingtrack = 1.5; },
    file => { file.build.characterLevel = '30'; },
    file => { file.build.abilitySlots = 0; },
    file => { file.build.gameMode = 'other'; },
    file => { file.build.ranks.unknown = 1; },
    file => { file.build.ranks['skills-attribute-weaponry1'] = -1; },
    file => { file.build.ranks['skills-attribute-weaponry1'] = 99; },
    file => { file.build.abilities = ['skills-ability-fraggrenade']; },
    file => { file.build.techniques[0] = 'skills-ability-fraggrenade'; },
    file => { file.build.traits = ['fake-purchase']; },
    file => { Object.defineProperty(file.build.ranks, '__proto__', { value: { polluted: true }, enumerable: true }); },
  ]) {
    const file = JSON.parse(original); mutate(file);
    const result = Build.deserialize(data, JSON.stringify(file));
    expect(result.error).toBeTruthy();
    expect(result.state).toBeUndefined();
    expect(Build.serialize(data, state)).toBe(original);
  }
  for (const text of ['{', 'null', '[]', '"build"', '{}', ' '.repeat(Build.fileLimit + 1)]) {
    expect(Build.deserialize(data, text).error).toBeTruthy();
  }
  expect({}.polluted).toBeUndefined();
});

for (const width of [1440, 390]) {
  test(`save and load restores a complete offline build after reload at ${width}px`, async ({ page, context }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    await context.setOffline(true);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    const incoming = Build.serialize(data, savedBuild());
    await loadBuild(page, incoming);
    await expect(page.locator('#message')).toHaveText('Build loaded from file.');
    await expect(page.locator('#load-build')).toBeFocused();
    const saved = await downloadBuild(page);
    expect(JSON.parse(saved)).toEqual(JSON.parse(incoming));
    await expect(page.locator('#message')).toContainText('Build file downloaded');
    await page.screenshot({ path: testInfo.outputPath(`save-controls-${width}.png`) });
    await page.reload();
    await expect(page.locator('#gear-hotbar1')).toHaveValue('');
    await loadBuild(page, saved);
    await expect(page.locator('#gear-hands')).toHaveValue(itemId('Circuit Gauntlets'));
    await expect(page.locator('#grade-hands')).toHaveValue('5');
    await expect(page.locator('#combat-damage')).toHaveText('50%');
    await page.screenshot({ path: testInfo.outputPath(`loaded-build-${width}.png`) });
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Quickbar 1 augments', exact: true }).click();
    await expect(page.locator('#augment-1')).toHaveValue('t6_augment_smg1');
    await expect(page.locator('#augment-grade-1')).toHaveValue('3');
    await expect(page.locator('#roll-1')).toHaveValue('100');
    const damage = page.locator('#item-stat-rows tr').filter({ has: page.getByRole('rowheader', { name: 'Damage Per Shot', exact: true }) });
    await expect(damage.locator('td').first()).toHaveText('60.99');
    await page.getByRole('button', { name: 'Progression', exact: true }).click();
    await expect(page.locator('#character-level')).toHaveValue('30');
    await expect(page.locator('#ability-slots')).toHaveValue('2');
    await expect(page.locator('#game-mode')).toHaveValue('singleplayer');
    for (const [track, level] of Object.entries(savedBuild().levels)) await expect(page.locator(`#level-${track}`)).toHaveValue(String(level));
    await page.getByRole('button', { name: 'Skills', exact: true }).click();
    await expect(page.locator('#rank-skills-attribute-weaponry1')).toHaveValue('1');
    await expect(page.locator('#ability-0')).toHaveValue('skills-ability-fraggrenade');
    await expect(page.locator('#technique-0')).toHaveValue('skills-perk-bodyshots');
    await page.getByRole('button', { name: 'Reset build', exact: true }).click();
    await page.locator('#load-build').focus();
    const chooser = page.waitForEvent('filechooser');
    await page.locator('#load-build').press('Enter');
    await (await chooser).setFiles(fileInput(saved));
    await expect(page.locator('#message')).toHaveText('Build loaded from file.');
    expect(JSON.parse(await downloadBuild(page))).toEqual(JSON.parse(saved));
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect(errors).toEqual([]);
  });

  test(`rejected build files preserve the current build and allow recovery at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    await page.goto(url);
    await page.locator('#gear-hotbar1').selectOption(itemId('A Dart for Every Man'));
    const before = await downloadBuild(page);
    const unknown = JSON.parse(before); unknown.build.equipment.hotbar1.id = 'missing-weapon';
    const version = JSON.parse(before); version.version = 2;
    for (const text of ['{', JSON.stringify(unknown), JSON.stringify(version), ' '.repeat(Build.fileLimit + 1)]) {
      await loadBuild(page, text);
      await expect(page.locator('#message')).toContainText('Choose');
      await expect(page.locator('#message')).toContainText('current build is unchanged');
      await expect(page.locator('#message')).toHaveClass('error');
      await expect(page.locator('#gear-hotbar1')).toHaveValue(itemId('A Dart for Every Man'));
      if (text === '{') {
        await page.screenshot({ path: testInfo.outputPath(`load-error-${width}.png`) });
        expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
      }
      expect(JSON.parse(await downloadBuild(page))).toEqual(JSON.parse(before));
    }
    await loadBuild(page, before);
    await expect(page.locator('#message')).toHaveText('Build loaded from file.');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test('a slow or unreadable build file locks editing briefly and recovers without losing the current build', async ({ page }) => {
  await page.goto(url);
  await page.locator('#gear-hotbar1').selectOption(itemId('A Dart for Every Man'));
  const before = await downloadBuild(page);
  await page.evaluate(() => { File.prototype.text = () => new Promise((resolve, reject) => { window.failBuildRead = reject; }); });
  await page.locator('#build-file').setInputFiles(fileInput(before));
  await expect(page.locator('#message')).toHaveText('Loading build file…');
  for (const selector of ['#save-build', '#load-build', '#reset']) await expect(page.locator(selector)).toBeDisabled();
  expect(await page.locator('.workspace').evaluate(el => el.inert)).toBe(true);
  await page.evaluate(() => window.failBuildRead(new Error('File unavailable')));
  await expect(page.locator('#message')).toContainText('file could not be read');
  await expect(page.locator('#load-build')).toBeEnabled();
  await expect(page.locator('#load-build')).toBeFocused();
  expect(await page.locator('.workspace').evaluate(el => el.inert)).toBe(false);
  expect(JSON.parse(await downloadBuild(page))).toEqual(JSON.parse(before));
});

test('oversized file restores Load focus without reading or replacing the build', async ({ page }) => {
  await page.goto(url);
  const before = await downloadBuild(page);
  await page.evaluate(() => { File.prototype.text = () => { throw new Error('Oversized file must not be read'); }; });
  await page.locator('#gear-head').focus();
  await page.locator('#build-file').setInputFiles(fileInput(' '.repeat(Build.fileLimit + 1)));
  await expect(page.locator('#message')).toContainText('64 KB or smaller');
  await expect(page.locator('#load-build')).toBeFocused();
  expect(JSON.parse(await downloadBuild(page))).toEqual(JSON.parse(before));
});

test('unlearned draft abilities and techniques stay visible and can be cleared', async ({ page }, testInfo) => {
  await page.goto(url);
  const state = savedBuild();
  delete state.ranks[state.abilities[0]];
  delete state.ranks[state.techniques[0]];
  await loadBuild(page, Build.serialize(data, state));
  await page.getByRole('button', { name: 'Skills', exact: true }).click();
  for (const [selector, id] of [['#ability-0', state.abilities[0]], ['#technique-0', state.techniques[0]]]) {
    await expect(page.locator(selector)).toHaveValue(id);
    await expect(page.locator(`${selector} option:checked`)).toContainText('not learned');
  }
  await expect(page.locator('#errors')).toContainText('must be learned');
  await page.screenshot({ path: testInfo.outputPath('loaded-unlearned-draft.png') });
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  await page.locator('#ability-0').selectOption('');
  await page.locator('#technique-0').selectOption('');
  await expect(page.locator('#errors')).toBeHidden();
  const saved = JSON.parse(await downloadBuild(page));
  expect(saved.build.abilities[0]).toBe('');
  expect(saved.build.techniques[0]).toBe('');
});
