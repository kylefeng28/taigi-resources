// ==UserScript==
// @name         Tweaks for Ministry of Education Dictionary of Frequently-Used Taiwanese Taigi (教育部臺灣台語常用詞辭典)
// @namespace    https://sutian.moe.edu.tw/
// @version      1.0
// @description  Wraps audio play buttons with <a href> links so you can Ctrl-click to download MP3s
// @author       You
// @match        https://sutian.moe.edu.tw/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    const BASE_URL = 'https://sutian.moe.edu.tw';

    // Main search page: https://sutian.moe.edu.tw/zh-hant/tshiau/?lui=tai_su&tsha=辭典
    // Entry details: https://sutian.moe.edu.tw/zh-hant/su/12884/

    function wrapButtonAudio(button) {
        const dataSrc = button.getAttribute('data-src');
        if (!dataSrc || button.querySelector('a')) return;

        // data-src may be a JSON array or a plain path string
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

        // Move all children into the link
        while (button.firstChild) {
            link.appendChild(button.firstChild);
        }

        button.appendChild(link);
    }

    function processButtons() {
        document.querySelectorAll('button.imtong-liua[data-src]').forEach(wrapButtonAudio);
    }

    // Run on initial load
    processButtons();

    // Also handle dynamically loaded content (search results load via JS)
    const observer = new MutationObserver(processButtons);
    observer.observe(document.body, { childList: true, subtree: true });
})();
