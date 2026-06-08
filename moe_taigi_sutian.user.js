// ==UserScript==
// @name         Tweaks for MOE Taigi Dictionary (教育部臺灣台語常用詞辭典)
// @namespace    https://sutian.moe.edu.tw/
// @version      2.0
// @description  Audio download links + Add to Anki via AnkiConnect
// @author       You
// @match        https://sutian.moe.edu.tw/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      127.0.0.1
// ==/UserScript==

(function () {
    'use strict';

    const BASE_URL = 'https://sutian.moe.edu.tw';
    const ANKI_URL = 'http://127.0.0.1:8765';

    // ─── Config ────────────────────────────────────────────────────────────────

    const DEFAULT_CONFIG = {
        deck: '',
        model: '',
        fields: {
            pronunciation: '',  // Tâi-lô romanization with 文/白 markers
            hanzi: '',
            definition: '',
            audio: '',
        }
    };

    async function loadConfig() {
        const raw = await GM_getValue('anki_config', null);
        return raw ? { ...DEFAULT_CONFIG, ...JSON.parse(raw) } : { ...DEFAULT_CONFIG };
    }

    async function saveConfig(config) {
        await GM_setValue('anki_config', JSON.stringify(config));
    }

    // ─── AnkiConnect ──────────────────────────────────────────────────────────

    function ankiRequest(action, params = {}) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: ANKI_URL,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify({ action, version: 6, params }),
                onload(response) {
                    try {
                        const { result, error } = JSON.parse(response.responseText);
                        if (error) reject(new Error(error));
                        else resolve(result);
                    } catch {
                        reject(new Error('Invalid response from AnkiConnect'));
                    }
                },
                onerror() {
                    reject(new Error('Cannot connect to AnkiConnect. Is Anki running?'));
                }
            });
        });
    }

    // ─── Page data extraction (entry detail pages only) ───────────────────────

    function isEntryPage() {
        return /\/zh-hant\/su\/\d+\/?$/.test(location.pathname);
    }

    function extractEntryData() {
        // Hanzi: main <h1>
        const hanzi = document.querySelector('h1')?.textContent.trim() ?? '';

        // Pronunciation: <dt> elements with 文/白 markers, followed by <dd> with romanization
        const readings = [];
        document.querySelectorAll('dt').forEach(dt => {
            const marker = dt.textContent.trim();
            if (marker !== '文' && marker !== '白') return;
            const dd = dt.nextElementSibling;
            if (!dd || dd.tagName !== 'DD') return;
            const clone = dd.cloneNode(true);
            clone.querySelectorAll('button').forEach(el => el.remove());
            const rom = clone.textContent.replace(/\s+/g, ' ').trim();
            if (rom) readings.push(`[${marker}] ${rom}`);
        });
        const pronunciation = readings.join('; ');

        // Definition: <ol> following the <h2> that contains 釋義
        let definition = '';
        for (const h2 of document.querySelectorAll('h2')) {
            if (!h2.textContent.includes('釋義')) continue;
            const ol = h2.nextElementSibling;
            if (ol) {
                const items = [];
                ol.querySelectorAll('li').forEach(li => {
                    const clone = li.cloneNode(true);
                    clone.querySelectorAll('button').forEach(el => el.remove());
                    const text = clone.textContent.replace(/\s+/g, ' ').trim();
                    if (text) items.push(text);
                });
                definition = items.length > 1
                    ? items.map((t, i) => `${i + 1}. ${t}`).join('<br>')
                    : (items[0] ?? '');
            }
            break;
        }

        // Audio: first button whose visually-hidden label contains 播放音讀
        let audioUrl = null;
        for (const btn of document.querySelectorAll('button.imtong-liua[data-src]')) {
            const label = btn.querySelector('.visually-hidden')?.textContent ?? '';
            if (!label.includes('播放音讀')) continue;
            const raw = btn.getAttribute('data-src');
            let src;
            try {
                const parsed = JSON.parse(raw);
                src = Array.isArray(parsed) ? parsed[0] : parsed;
            } catch {
                src = raw;
            }
            audioUrl = src.startsWith('http') ? src : BASE_URL + src;
            break;
        }

        return { hanzi, pronunciation, definition, audioUrl };
    }

    // ─── Audio link wrapping ──────────────────────────────────────────────────

    function wrapButtonAudio(button) {
        const dataSrc = button.getAttribute('data-src');
        if (!dataSrc || button.querySelector('a')) return;
        let src;
        try {
            const parsed = JSON.parse(dataSrc);
            src = Array.isArray(parsed) ? parsed[0] : parsed;
        } catch {
            src = dataSrc;
        }
        const href = src.startsWith('http') ? src : BASE_URL + src;
        const link = document.createElement('a');
        link.href = href;
        while (button.firstChild) link.appendChild(button.firstChild);
        button.appendChild(link);
    }

    function processButtons() {
        document.querySelectorAll('button.imtong-liua[data-src]').forEach(wrapButtonAudio);
    }

    // ─── Styles ───────────────────────────────────────────────────────────────

    function injectStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #sutian-anki-btn {
                margin: 8px 0;
                padding: 6px 14px;
                background: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            #sutian-anki-btn:hover { background: #357abd; }
            #sutian-anki-btn:disabled { background: #aaa; cursor: default; }
            #sutian-settings-btn {
                position: fixed;
                bottom: 16px;
                right: 16px;
                z-index: 9999;
                width: 40px;
                height: 40px;
                background: #555;
                color: white;
                border: none;
                border-radius: 50%;
                cursor: pointer;
                font-size: 18px;
                line-height: 40px;
                text-align: center;
            }
            #sutian-settings-btn:hover { background: #333; }
            #sutian-modal-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.5);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            #sutian-modal {
                background: white;
                border-radius: 8px;
                padding: 24px;
                min-width: 420px;
                max-width: 90vw;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                font-family: sans-serif;
            }
            #sutian-modal h2 { margin: 0 0 16px; font-size: 18px; }
            #sutian-modal label {
                display: block;
                margin-bottom: 4px;
                font-weight: bold;
                font-size: 13px;
                color: #444;
            }
            #sutian-modal select {
                width: 100%;
                padding: 6px 8px;
                margin-bottom: 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
            }
            #sutian-modal .field-mappings {
                border-top: 1px solid #eee;
                padding-top: 12px;
                margin-top: 4px;
            }
            #sutian-modal .field-mappings p {
                margin: 0 0 12px;
                font-size: 13px;
                color: #666;
            }
            #sutian-modal .btn-row {
                display: flex;
                gap: 8px;
                justify-content: flex-end;
                margin-top: 8px;
                border-top: 1px solid #eee;
                padding-top: 16px;
            }
            #sutian-modal button {
                padding: 6px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            #sutian-modal .btn-primary { background: #4a90e2; color: white; }
            #sutian-modal .btn-primary:hover { background: #357abd; }
            #sutian-modal .btn-secondary { background: #e0e0e0; color: #333; }
            #sutian-modal .btn-secondary:hover { background: #ccc; }
            #sutian-status {
                margin-top: 6px;
                font-size: 13px;
                min-height: 18px;
            }
            #sutian-status.success { color: #2a7a2a; }
            #sutian-status.error { color: #c0392b; }
        `;
        document.head.appendChild(style);
    }

    // ─── Settings modal ───────────────────────────────────────────────────────

    function populateSelect(select, options, selected) {
        select.innerHTML = '<option value="">— none —</option>';
        for (const opt of options) {
            const el = document.createElement('option');
            el.value = opt;
            el.textContent = opt;
            if (opt === selected) el.selected = true;
            select.appendChild(el);
        }
    }

    async function openSettingsModal(config) {
        document.getElementById('sutian-modal-overlay')?.remove();

        const overlay = document.createElement('div');
        overlay.id = 'sutian-modal-overlay';
        overlay.innerHTML = `
            <div id="sutian-modal">
                <h2>Anki Settings</h2>
                <label>Deck</label>
                <select id="sm-deck"><option>Loading…</option></select>
                <label>Note Type</label>
                <select id="sm-model"><option>Loading…</option></select>
                <div class="field-mappings">
                    <p>Map dictionary data to note fields:</p>
                    <label>Pronunciation (Tâi-lô romanization)</label>
                    <select id="sm-f-pronunciation"></select>
                    <label>Hanzi (Chinese characters)</label>
                    <select id="sm-f-hanzi"></select>
                    <label>Definition (釋義)</label>
                    <select id="sm-f-definition"></select>
                    <label>Audio</label>
                    <select id="sm-f-audio"></select>
                </div>
                <div class="btn-row">
                    <button class="btn-secondary" id="sm-cancel">Cancel</button>
                    <button class="btn-primary" id="sm-save">Save</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const deckSel = document.getElementById('sm-deck');
        const modelSel = document.getElementById('sm-model');
        const fieldSelects = {
            pronunciation: document.getElementById('sm-f-pronunciation'),
            hanzi:         document.getElementById('sm-f-hanzi'),
            definition:    document.getElementById('sm-f-definition'),
            audio:         document.getElementById('sm-f-audio'),
        };

        let decks, models;
        try {
            [decks, models] = await Promise.all([
                ankiRequest('deckNames'),
                ankiRequest('modelNames'),
            ]);
        } catch (e) {
            deckSel.innerHTML = `<option value="">${e.message}</option>`;
            modelSel.innerHTML = '';
            return;
        }

        populateSelect(deckSel, [...decks].sort(), config.deck);
        populateSelect(modelSel, [...models].sort(), config.model);

        async function refreshFields() {
            for (const sel of Object.values(fieldSelects)) {
                sel.innerHTML = '<option value="">— none —</option>';
            }
            const model = modelSel.value;
            if (!model) return;
            let fields;
            try {
                fields = await ankiRequest('modelFieldNames', { modelName: model });
            } catch {
                return;
            }
            populateSelect(fieldSelects.pronunciation, fields, config.fields.pronunciation);
            populateSelect(fieldSelects.hanzi,         fields, config.fields.hanzi);
            populateSelect(fieldSelects.definition,    fields, config.fields.definition);
            populateSelect(fieldSelects.audio,         fields, config.fields.audio);
        }

        await refreshFields();
        modelSel.addEventListener('change', refreshFields);

        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        document.getElementById('sm-cancel').addEventListener('click', () => overlay.remove());
        document.getElementById('sm-save').addEventListener('click', async () => {
            await saveConfig({
                deck: deckSel.value,
                model: modelSel.value,
                fields: {
                    pronunciation: fieldSelects.pronunciation.value,
                    hanzi:         fieldSelects.hanzi.value,
                    definition:    fieldSelects.definition.value,
                    audio:         fieldSelects.audio.value,
                }
            });
            overlay.remove();
        });
    }

    // ─── Add to Anki ──────────────────────────────────────────────────────────

    async function addToAnki(btn, statusEl) {
        const config = await loadConfig();
        if (!config.deck || !config.model) {
            statusEl.textContent = 'Configure Anki settings first (⚙ button, bottom right).';
            statusEl.className = 'error';
            return;
        }

        btn.disabled = true;
        statusEl.textContent = '';
        statusEl.className = '';

        const { hanzi, pronunciation, definition, audioUrl } = extractEntryData();

        const fields = {};
        if (config.fields.pronunciation) fields[config.fields.pronunciation] = pronunciation;
        if (config.fields.hanzi)         fields[config.fields.hanzi]         = hanzi;
        if (config.fields.definition)    fields[config.fields.definition]    = definition;

        if (audioUrl && config.fields.audio) {
            try {
                statusEl.textContent = 'Storing audio…';
                const filename = audioUrl.split('/').pop();
                // AnkiConnect fetches the URL itself — no need to download it here
                await ankiRequest('storeMediaFile', { filename, url: audioUrl });
                fields[config.fields.audio] = `[sound:${filename}]`;
            } catch (e) {
                statusEl.textContent = `Audio error: ${e.message}`;
                statusEl.className = 'error';
                btn.disabled = false;
                return;
            }
        }

        try {
            statusEl.textContent = 'Adding note…';
            await ankiRequest('addNote', {
                note: {
                    deckName: config.deck,
                    modelName: config.model,
                    fields,
                    tags: ['sutian'],
                    options: { allowDuplicate: false, duplicateScope: 'deck' }
                }
            });
            statusEl.textContent = `✓ Added "${hanzi}" to Anki.`;
            statusEl.className = 'success';
        } catch (e) {
            statusEl.textContent = `Anki error: ${e.message}`;
            statusEl.className = 'error';
            btn.disabled = false;
        }
    }

    function injectAnkiButton() {
        if (!isEntryPage()) return;
        const h1 = document.querySelector('h1');
        if (!h1) return;

        const wrapper = document.createElement('div');
        const btn = document.createElement('button');
        btn.id = 'sutian-anki-btn';
        btn.textContent = 'Add to Anki';
        const status = document.createElement('div');
        status.id = 'sutian-status';
        btn.addEventListener('click', () => addToAnki(btn, status));
        wrapper.appendChild(btn);
        wrapper.appendChild(status);
        h1.insertAdjacentElement('afterend', wrapper);
    }

    function injectSettingsButton() {
        const btn = document.createElement('button');
        btn.id = 'sutian-settings-btn';
        btn.title = 'Anki Settings';
        btn.textContent = '⚙';
        btn.addEventListener('click', async () => openSettingsModal(await loadConfig()));
        document.body.appendChild(btn);
    }

    // ─── Init ─────────────────────────────────────────────────────────────────

    injectStyles();
    processButtons();
    injectAnkiButton();
    injectSettingsButton();

    const observer = new MutationObserver(processButtons);
    observer.observe(document.body, { childList: true, subtree: true });
})();
