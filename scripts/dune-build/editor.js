'use strict';
(() => {
  const data = JSON.parse(document.getElementById('build-data').textContent);
  let state = DuneBuild.initial(data);
  let inspected = 'head';
  let augmentSlot = 'head';
  let search = '';
  let tier = '';
  let tree = 'Trooper';
  const names = { head: 'Head', chest: 'Chest / body', hands: 'Hands', legs: 'Legs', feet: 'Feet',
    shield: 'Shield', powerpack: 'Power pack', suspensor: 'Suspensor belt' };
  for (let index = 1; index <= 8; index++) names[`hotbar${index}`] = `Quickbar ${index}`;
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const option = (value, label, selected) => `<option value="${esc(value)}"${selected === value ? ' selected' : ''}>${esc(label)}</option>`;
  const source = (id, category = 'items') => `https://dune.gaming.tools/${category}/${encodeURIComponent(id)}`;
  function number(value) { return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value); }
  function format(stat, modifier = false) {
    if (stat.value == null) return 'Unavailable';
    if (stat.type === 'string') return esc(stat.value);
    const percentageFormat = stat.format?.match(/\{v:P(\d+)\}/);
    const suffix = percentageFormat || stat.format?.includes('%') ? '%' : stat.format?.includes('/s') ? '/s'
      : stat.format?.includes(' RPM') ? ' RPM' : stat.format?.includes('}s') ? ' s'
      : stat.format?.includes('}m') ? ' m' : stat.format?.includes(' V') ? ' V' : '';
    const value = stat.value * (percentageFormat ? 100 : modifier && suffix === '%' ? (stat.percentScale ?? 100) : 1);
    const formatted = percentageFormat ? new Intl.NumberFormat('en-US', { maximumFractionDigits: Number(percentageFormat[1]) }).format(value) : number(value);
    return `${formatted}${suffix}`;
  }
  function notify(message, error = false) {
    $('#message').textContent = message;
    $('#message').classList.toggle('error', error);
  }
  function update(result, message) {
    if (result.error) { notify(result.error, true); render(); return; }
    state = result.state;
    notify(message);
    render();
  }

  function gearRow(slot) {
    const selected = state.equipment[slot];
    const item = DuneBuild.itemById(data, selected.id);
    const choices = DuneBuild.compatibleItems(data, slot).filter(candidate => candidate.id === selected.id
      || ((!tier || candidate.tier === Number(tier)) && candidate.name.toLowerCase().includes(search)));
    const locked = slot === 'legs' && DuneBuild.itemById(data, state.equipment.chest.id)?.blocksLegs;
    const grades = item?.scaledStats ?? [];
    return `<tr><th scope="row">${names[slot]}</th><td class="item-cell"><label class="sr-only" for="gear-${slot}">${names[slot]} equipment</label>
      <select id="gear-${slot}" data-gear="${slot}"${locked ? ' disabled' : ''}>${option('', locked ? 'Covered by body garment' : 'Empty', selected.id)}
      ${choices.map(candidate => option(candidate.id, `${candidate.name} · T${candidate.tier} ${candidate.rarity}`, selected.id)).join('')}</select></td>
      <td class="grade-cell"><label class="sr-only" for="grade-${slot}">${names[slot]} item grade</label><select id="grade-${slot}" data-grade="${slot}"${!grades.length ? ' disabled' : ''}>
      ${option('0', 'Base', String(selected.grade))}${grades.map(row => option(String(row.grade), `G${row.grade}`, String(selected.grade))).join('')}</select></td>
      <td class="inspect-cell"><button type="button" data-inspect="${slot}"${!item ? ' disabled' : ''}>Stats</button></td></tr>`;
  }

  function renderGear() {
    $('#gear-rows').innerHTML = DuneBuild.slots.slice(0, 8).map(gearRow).join('');
    $('#quickbar-rows').innerHTML = DuneBuild.slots.slice(8).map(gearRow).join('');
    const equipped = DuneBuild.slots.filter(slot => state.equipment[slot].id);
    if (!equipped.includes(inspected)) inspected = equipped[0] ?? 'head';
    $('#inspect-slot').innerHTML = DuneBuild.slots.map(slot => option(slot, names[slot], inspected)).join('');
  }

  function renderAugments() {
    const eligible = DuneBuild.slots.filter(slot => {
      const item = DuneBuild.itemById(data, state.equipment[slot].id);
      return item && DuneBuild.compatibleAugments(data, item).length;
    });
    if (!eligible.includes(augmentSlot)) augmentSlot = eligible[0] ?? '';
    $('#augment-target').innerHTML = option('', 'Select equipped T6 unique gear', augmentSlot)
      + eligible.map(slot => option(slot, `${names[slot]}: ${DuneBuild.itemById(data, state.equipment[slot].id).name}`, augmentSlot)).join('');
    const item = DuneBuild.itemById(data, state.equipment[augmentSlot]?.id);
    const limit = DuneBuild.augmentLimit(data, state, item);
    $('#augment-note').textContent = item ? `${limit} slots unlocked by purchased Crafting traits. Rolls are values within the source range, not drop chances.`
      : 'Equip a unique tier 6 garment or weapon, then purchase augmentation-limit traits in Progression.';
    const selections = state.equipment[augmentSlot]?.augments ?? [];
    const count = Math.max(limit, selections.length);
    const choices = DuneBuild.compatibleAugments(data, item);
    $('#augment-rows').innerHTML = Array.from({ length: count }, (_, index) => {
      const selected = selections[index] ?? { id: '', grade: 1, roll: 0 };
      const augment = data.augments.find(candidate => candidate.id === selected.id);
      const grades = augment ? augment.stats[0].values.map(row => row.quality) : [1, 2, 3, 4, 5];
      return `<div class="augment-row"><label>Augment ${index + 1}<select id="augment-${index}" data-augment="${index}">${option('', 'None', selected.id)}
        ${choices.map(candidate => option(candidate.id, candidate.name, selected.id)).join('')}</select></label>
        <label>Grade<select id="augment-grade-${index}" data-augment-grade="${index}"${!selected.id ? ' disabled' : ''}>${grades.map(grade => option(String(grade), `Grade ${grade}`, String(selected.grade))).join('')}</select></label>
        <label>Roll position %<input type="number" min="0" max="100" step="1" value="${selected.roll}" id="roll-${index}" data-roll="${index}"${!selected.id ? ' disabled' : ''}></label>
        ${augment ? `<p>${esc(augment.description)} <a href="${source(augment.id)}">Source</a></p>` : ''}</div>`;
    }).join('');
  }

  function learnedOptions(kind, selected) {
    return option('', 'Empty', selected) + data.skills.filter(skill => skill.skillType === kind && state.ranks[skill.id] > 0)
      .map(skill => option(skill.id, `${skill.name} · rank ${state.ranks[skill.id]}`, selected)).join('');
  }
  function renderSkills() {
    $('#skill-rows').innerHTML = data.skills.filter(skill => skill.skillTree === tree && skill.gameModes.includes(state.gameMode))
      .sort((a, b) => a.gridX - b.gridX || a.gridY - b.gridY).map(skill => {
        const rank = state.ranks[skill.id] ?? 0;
        const prereqs = (skill.prerequisites ?? []).map(tag => data.skills.find(other => other.tag === tag)?.name).filter(Boolean);
        return `<tr><th scope="row"><a href="${source(skill.id, 'skills')}">${esc(skill.name)}</a><small>${skill.skillType === 'Attribute' ? 'Passive' : skill.skillType}
          ${prereqs.length ? ` · Connected to ${esc(prereqs.join(' / '))}` : ' · Starting skill'}</small></th>
          <td><label class="sr-only" for="rank-${skill.id}">${esc(skill.name)} rank</label><select id="rank-${skill.id}" data-rank="${esc(skill.id)}">
          ${Array.from({ length: skill.maxLevel + 1 }, (_, value) => option(String(value), `${value} / ${skill.maxLevel}`, String(rank))).join('')}</select></td>
          <td>${(skill.costPerLevel ?? []).slice(0, rank).reduce((a, b) => a + b, 0)}</td></tr>`;
      }).join('');
    $('#ability-selectors').innerHTML = state.abilities.map((id, index) => `<label>Ability ${index + 1}<select id="ability-${index}" data-ability="${index}"${index >= state.abilitySlots ? ' disabled' : ''}>${learnedOptions('Ability', id)}</select></label>`).join('');
    $('#technique-selectors').innerHTML = state.techniques.map((id, index) => `<label>Technique ${index + 1}<select id="technique-${index}" data-technique="${index}">${learnedOptions('Technique', id)}</select></label>`).join('');
  }

  function renderProgression() {
    $('#track-rows').innerHTML = data.tracks.map(track => `<section class="track"><h3>${esc(track.name)}</h3>
      <label>${esc(track.name)} level<input type="number" min="0" max="${track.maxLevel}" value="${state.levels[track.id]}" id="level-${track.id}" data-track="${track.id}"></label>
      <details id="traits-${track.id}"><summary>Traits · ${state.traits.filter(id => track.keystones.some(trait => trait.id === id)).length} purchased</summary>
      <div class="trait-list">${track.keystones.map(trait => `<label class="trait"><input type="checkbox" id="trait-${esc(trait.id)}" data-trait="${esc(trait.id)}"${state.traits.includes(trait.id) ? ' checked' : ''}${trait.level > state.levels[track.id] ? ' disabled' : ''}>
      <span>${esc(trait.name)} <small>Level ${trait.level}${trait.skillPointsGranted ? ` · +${trait.skillPointsGranted.value} skill points` : ''}</small>
      <small>${esc(trait.description ?? '')}</small></span></label>`).join('')}</div></details></section>`).join('');
  }

  function renderStats() {
    const result = DuneBuild.calculate(data, state);
    $('#point-count').textContent = `${result.points} / ${result.budget} skill points`;
    $('#build-status').textContent = result.errors.length ? 'Invalid build' : 'Build valid';
    $('#build-status').classList.toggle('invalid', result.errors.length > 0);
    $('#errors').hidden = !result.errors.length;
    $('#errors').innerHTML = result.errors.map(error => `<li>${esc(error)}</li>`).join('');
    $('#armor-total').textContent = result.errors.length ? 'Unavailable' : number(result.armor);
    $('#mobile-armor').textContent = result.errors.length ? 'Invalid build' : `Armor ${number(result.armor)}`;
    $('#mobile-points').textContent = `${result.points}/${result.budget} SP`;
    $('#volume-total').textContent = result.errors.length ? 'Unavailable' : `${number(result.volume)} V`;
    const entry = result.equipment[inspected];
    $('#item-title').textContent = entry.item ? `${names[inspected]}: ${entry.item.name}` : 'Equipment details';
    $('#item-source').hidden = !entry.item;
    $('#item-source').href = entry.item ? source(entry.item.id) : '#';
    $('#item-stat-rows').innerHTML = entry.item ? (entry.stats.length ? entry.stats.map(stat => `<tr><th scope="row">${esc(stat.name.replace(/:$/, ''))}</th>
      <td>${format(stat)}</td><td>${stat.value == null ? 'Formula unverified after modification' : `Base ${format({ ...stat, value: stat.base })}${stat.grade !== stat.base ? `; grade ${format({ ...stat, value: stat.grade })}` : ''}${stat.modifiers.length ? `; ${esc(stat.modifiers.map(modifier => modifier.source).join(', '))}` : ''}`}</td></tr>`).join('') : '<tr><td colspan="3">No numeric stats supplied for this item.</td></tr>')
      : '<tr><td colspan="3">Equip a piece, then select Stats to inspect its values.</td></tr>';
    $('#augment-effect-rows').innerHTML = entry.modifiers.map(modifier => {
      const value = modifier.operation === 'multiply' ? `${number((modifier.value - 1) * 100)}%` : `${number(modifier.value * (modifier.format?.includes('%') ? 100 : 1))}${modifier.format?.includes('%') ? '%' : ''}`;
      return `<tr><th scope="row">${esc(modifier.name)}</th><td>${value}</td><td>${esc(modifier.source)} · ${modifier.applied ? 'Applied to item above' : 'Final item value unavailable'}</td></tr>`;
    }).join('');
    $('#augment-effects').hidden = !entry.modifiers.length;
    const modifiers = result.modifiers.filter(stat => stat.value !== 0);
    $('#modifier-rows').innerHTML = modifiers.length ? modifiers.map(stat => `<tr><th scope="row">${esc(stat.name.replace(/:$/, ''))}</th><td>${format(stat, true)}</td>
      <td>${esc(stat.source)}<small>${stat.conditional ? 'Equipped effect; conditional on use or combat state' : 'Modifier; final character formula unverified'}</small></td></tr>`).join('') : '<tr><td colspan="3">Learn skills or select progression traits to see their effects.</td></tr>';
    $('#coverage').textContent = `${data.items.length} equipment choices · ${data.augments.length} augments · ${data.skills.length} skills · ${data.tracks.length} specializations`;
  }

  function render() {
    const focused = document.activeElement?.id;
    const open = [...document.querySelectorAll('details[open][id]')].map(details => details.id);
    renderGear(); renderAugments(); renderSkills(); renderProgression(); renderStats();
    for (const id of open) document.getElementById(id)?.setAttribute('open', '');
    if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
  }

  document.addEventListener('change', event => {
    const input = event.target;
    if (input.dataset.gear) {
      inspected = input.dataset.gear;
      update(DuneBuild.equip(data, state, input.dataset.gear, input.value), 'Equipment updated.');
    } else if (input.dataset.grade) {
      state.equipment[input.dataset.grade].grade = Number(input.value);
      inspected = input.dataset.grade; render(); notify('Item grade updated.');
    } else if (input.dataset.rank) {
      update(DuneBuild.rank(data, state, input.dataset.rank, Number(input.value)), 'Skill rank updated.');
    } else if (input.dataset.ability || input.dataset.technique) {
      const kind = input.dataset.ability ? 'abilities' : 'techniques';
      const index = Number(input.dataset.ability ?? input.dataset.technique);
      const next = DuneBuild.clone(state);
      if (input.value && next[kind].includes(input.value) && next[kind][index] !== input.value) {
        notify('That skill is already equipped. Choose a different skill.', true); render(); return;
      }
      next[kind][index] = input.value;
      state = next; render(); notify('Equipped skills updated.');
    } else if (input.dataset.track) {
      const track = data.tracks.find(candidate => candidate.id === input.dataset.track);
      if (!Number.isInteger(Number(input.value)) || Number(input.value) < 0 || Number(input.value) > track.maxLevel) { notify(`Enter a level between 0 and ${track.maxLevel}.`, true); render(); return; }
      state.levels[track.id] = Number(input.value);
      const unavailable = track.keystones.filter(trait => trait.level > state.levels[track.id]).map(trait => trait.id);
      state.traits = state.traits.filter(id => !unavailable.includes(id));
      render(); notify('Progression updated. Check skill and augment limits after lowering a level.');
    } else if (input.dataset.trait) {
      state.traits = state.traits.filter(id => id !== input.dataset.trait);
      if (input.checked) state.traits.push(input.dataset.trait);
      render(); notify('Purchased traits updated.');
    } else if (input.dataset.augment !== undefined || input.dataset.augmentGrade !== undefined || input.dataset.roll !== undefined) {
      const index = Number(input.dataset.augment ?? input.dataset.augmentGrade ?? input.dataset.roll);
      const selection = state.equipment[augmentSlot];
      while (selection.augments.length <= index) selection.augments.push({ id: '', grade: 1, roll: 0 });
      const chosen = selection.augments[index] ?? { id: '', grade: 1, roll: 0 };
      if (input.dataset.augment !== undefined) {
        chosen.id = input.value;
        const augment = data.augments.find(candidate => candidate.id === input.value);
        chosen.grade = augment?.minGrade ?? 1;
      } else if (input.dataset.augmentGrade !== undefined) chosen.grade = Number(input.value);
      else {
        const value = Number(input.value);
        if (!input.value || !Number.isFinite(value) || value < 0 || value > 100) { notify('Enter a roll position between 0 and 100.', true); render(); return; }
        chosen.roll = value;
      }
      selection.augments[index] = chosen;
      inspected = augmentSlot; render(); notify('Augmentation updated.');
    }
  });

  $('#gear-search').addEventListener('input', event => { search = event.target.value.trim().toLowerCase(); renderGear(); });
  $('#gear-tier').addEventListener('change', event => { tier = event.target.value; renderGear(); });
  $('#skill-tree').innerHTML = data.tracks.length ? data.skills.map(skill => skill.skillTree).filter((value, index, array) => array.indexOf(value) === index).map(name => option(name, name, tree)).join('') : '';
  $('#skill-tree').addEventListener('change', event => { tree = event.target.value; renderSkills(); });
  $('#inspect-slot').addEventListener('change', event => { inspected = event.target.value; renderStats(); });
  $('#augment-target').addEventListener('change', event => { augmentSlot = event.target.value; renderAugments(); });
  $('#character-level').max = data.characterLevels.at(-1).level;
  $('#character-level').addEventListener('change', event => {
    const value = Number(event.target.value);
    if (!data.characterLevels.some(level => level.level === value)) { event.target.value = state.characterLevel; notify('Choose a character level within the supported range.', true); return; }
    state.characterLevel = value; render(); notify('Skill budget updated.');
  });
  $('#ability-slots').addEventListener('change', event => {
    state.abilitySlots = Number(event.target.value);
    state.abilities = state.abilities.map((id, index) => index < state.abilitySlots ? id : '');
    render(); notify('Unlocked ability slots updated.');
  });
  $('#game-mode').addEventListener('change', event => {
    state = DuneBuild.mode(data, state, event.target.value);
    render(); notify('Game mode updated. Unavailable and disconnected skills removed.');
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.inspect) { inspected = button.dataset.inspect; renderStats(); $('#item-title').focus(); }
    if (button.dataset.view) {
      for (const tab of document.querySelectorAll('[data-view]')) tab.setAttribute('aria-pressed', String(tab === button));
      for (const panel of document.querySelectorAll('[data-panel]')) panel.hidden = panel.dataset.panel !== button.dataset.view;
    }
  });
  $('#reset').addEventListener('click', () => {
    state = DuneBuild.initial(data); search = ''; tier = ''; inspected = 'head'; augmentSlot = 'head';
    $('#gear-search').value = ''; $('#gear-tier').value = ''; $('#character-level').value = 1;
    $('#game-mode').value = 'multiplayer'; $('#ability-slots').value = '3';
    render(); notify('Build reset. Equipment and skills are empty; character level is 1 and specializations are 0.');
  });
  render();
})();
