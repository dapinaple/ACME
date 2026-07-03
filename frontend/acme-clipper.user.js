// ==UserScript==
// @name         ACME Coupon Clipper
// @namespace    https://github.com/dapinaple/ACME
// @version      1.0.0
// @description  Clip ACME digital coupons from your grocery list while logged in on acmemarkets.com
// @match        https://www.acmemarkets.com/*
// @match        https://acmemarkets.com/*
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-idle
// ==/UserScript==

(function () {
  const STORAGE_KEY = "acme_clipper_grocery_list";
  const PANEL_ID = "acme-clipper-panel";

  const STOP_WORDS = new Set([
    "a", "an", "and", "any", "for", "from", "in", "of", "on", "or", "the", "to", "with",
    "oz", "lb", "ct", "pkg", "size", "select", "varieties", "when", "you", "buy", "save", "off", "free",
  ]);

  function loadList() {
    try {
      if (typeof GM_getValue === "function") {
        return JSON.parse(GM_getValue(STORAGE_KEY, "[]"));
      }
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveList(items) {
    const payload = JSON.stringify(items);
    if (typeof GM_setValue === "function") {
      GM_setValue(STORAGE_KEY, payload);
    }
    localStorage.setItem(STORAGE_KEY, payload);
  }

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function keywords(text) {
    return new Set(
      normalize(text)
        .split(" ")
        .filter((word) => word.length > 2 && !STOP_WORDS.has(word))
    );
  }

  function couponText(card) {
    return normalize(card.innerText || card.textContent || "");
  }

  function isClipped(card) {
    const text = (card.innerText || "").toLowerCase();
    if (text.includes("clipped") || text.includes("added") || text.includes("loaded to card")) {
      return true;
    }
    const disabled = card.querySelector("button[disabled], .coupon-clipped-container, [aria-pressed='true']");
    return Boolean(disabled);
  }

  function clipButton(card) {
    const selectors = [
      "button.grid-coupon-btn",
      "button[aria-label*='Clip' i]",
      "button[aria-label*='Add' i]",
      "button",
    ];
    for (const selector of selectors) {
      const buttons = [...card.querySelectorAll(selector)];
      for (const button of buttons) {
        const label = (button.innerText || button.getAttribute("aria-label") || "").toLowerCase();
        if (button.disabled) continue;
        if (label.includes("clip") || label.includes("add") || label.includes("load")) {
          return button;
        }
      }
    }
    return null;
  }

  function couponCards() {
    const selectors = [
      "[class*='coupon']",
      "[class*='offer']",
      "[data-offer-id]",
      "[data-coupon-id]",
      "article",
      "li",
    ];
    const seen = new Set();
    const cards = [];
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        if (seen.has(node) || node.closest(`#${PANEL_ID}`)) continue;
        const text = couponText(node);
        if (text.length < 12 || text.length > 1200) continue;
        if (!clipButton(node) && !/save|off|\$\d/.test(text)) continue;
        seen.add(node);
        cards.push(node);
      }
    }
    return cards;
  }

  function matchingCards(listItems) {
    const listKeys = new Set();
    for (const item of listItems) {
      for (const word of keywords(item)) listKeys.add(word);
    }
    if (!listKeys.size) return [];

    return couponCards().filter((card) => {
      if (isClipped(card)) return false;
      const overlap = [...keywords(couponText(card))].filter((word) => listKeys.has(word));
      return overlap.length > 0;
    });
  }

  async function clickLoadMore(maxRounds = 8) {
    for (let i = 0; i < maxRounds; i += 1) {
      const button = document.querySelector("button.load-more, button[class*='load-more'], button[aria-label*='Load more' i]");
      if (!button || button.disabled) break;
      button.click();
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }

  async function clipCards(cards, statusEl) {
    let clipped = 0;
    for (const card of cards) {
      const button = clipButton(card);
      if (!button || isClipped(card)) continue;
      button.click();
      clipped += 1;
      statusEl.textContent = `Clipped ${clipped}...`;
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
    return clipped;
  }

  function renderPanel() {
    if (document.getElementById(PANEL_ID)) return;

    const panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <style>
        #${PANEL_ID} {
          position: fixed;
          right: 12px;
          bottom: 12px;
          width: min(360px, calc(100vw - 24px));
          max-height: 70vh;
          overflow: auto;
          z-index: 2147483646;
          background: #fff;
          border: 1px solid #d9e0e6;
          border-radius: 16px;
          box-shadow: 0 12px 40px rgba(0,0,0,.18);
          font: 14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          color: #1a1f24;
        }
        #${PANEL_ID} header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 14px;
          border-bottom: 1px solid #eee;
          background: #c8102e;
          color: #fff;
          border-radius: 16px 16px 0 0;
        }
        #${PANEL_ID} header button {
          background: transparent;
          border: none;
          color: #fff;
          font-size: 18px;
        }
        #${PANEL_ID} .body { padding: 12px 14px; }
        #${PANEL_ID} textarea, #${PANEL_ID} input {
          width: 100%;
          box-sizing: border-box;
          border: 1px solid #d9e0e6;
          border-radius: 10px;
          padding: 10px;
          margin: 8px 0;
        }
        #${PANEL_ID} .actions { display: grid; gap: 8px; margin-top: 8px; }
        #${PANEL_ID} .btn {
          border: none;
          border-radius: 10px;
          padding: 10px 12px;
          font-weight: 600;
          cursor: pointer;
        }
        #${PANEL_ID} .btn-primary { background: #c8102e; color: #fff; }
        #${PANEL_ID} .btn-secondary { background: #eef2f6; color: #1a1f24; }
        #${PANEL_ID} .status { color: #5f6b76; font-size: 12px; margin-top: 8px; }
        #${PANEL_ID} .hint { color: #5f6b76; font-size: 12px; }
        #${PANEL_ID} .fab {
          position: fixed;
          right: 16px;
          bottom: 16px;
          z-index: 2147483645;
          width: 56px;
          height: 56px;
          border-radius: 999px;
          border: none;
          background: #c8102e;
          color: #fff;
          font-weight: 800;
          box-shadow: 0 8px 24px rgba(0,0,0,.2);
        }
      </style>
      <header>
        <strong>ACME Clipper</strong>
        <button type="button" id="acme-clipper-close" aria-label="Close">×</button>
      </header>
      <div class="body">
        <p class="hint">You're logged in on ACME's site — no extra password needed. Open the Coupons/Deals page, add your list, then clip.</p>
        <label>Grocery list <span class="hint">(one item per line)</span></label>
        <textarea id="acme-clipper-list" rows="5" placeholder="milk&#10;chicken&#10;cereal"></textarea>
        <div class="actions">
          <button class="btn btn-primary" id="acme-clipper-match" type="button">Clip Matching Coupons</button>
          <button class="btn btn-secondary" id="acme-clipper-all" type="button">Clip All On Page</button>
          <button class="btn btn-secondary" id="acme-clipper-more" type="button">Load More Coupons</button>
        </div>
        <p class="status" id="acme-clipper-status"></p>
      </div>
    `;

    const fab = document.createElement("button");
    fab.className = "fab";
    fab.type = "button";
    fab.textContent = "A";
    fab.title = "Open ACME Clipper";

    document.body.appendChild(fab);
    document.body.appendChild(panel);

    const listEl = panel.querySelector("#acme-clipper-list");
    const statusEl = panel.querySelector("#acme-clipper-status");
    listEl.value = loadList().join("\n");

    const hidePanel = () => {
      panel.style.display = "none";
      fab.style.display = "block";
    };
    const showPanel = () => {
      panel.style.display = "block";
      fab.style.display = "none";
    };

    panel.querySelector("#acme-clipper-close").addEventListener("click", hidePanel);
    fab.addEventListener("click", showPanel);
    hidePanel();

    listEl.addEventListener("change", () => {
      const items = listEl.value.split("\n").map((line) => line.trim()).filter(Boolean);
      saveList(items);
    });

    panel.querySelector("#acme-clipper-more").addEventListener("click", async () => {
      statusEl.textContent = "Loading more coupons...";
      await clickLoadMore();
      statusEl.textContent = `Found ${couponCards().length} coupon cards on page.`;
    });

    panel.querySelector("#acme-clipper-match").addEventListener("click", async () => {
      const items = listEl.value.split("\n").map((line) => line.trim()).filter(Boolean);
      saveList(items);
      if (!items.length) {
        statusEl.textContent = "Add groceries to your list first.";
        return;
      }
      statusEl.textContent = "Loading coupons and matching...";
      await clickLoadMore(3);
      const matches = matchingCards(items);
      const clipped = await clipCards(matches, statusEl);
      statusEl.textContent = `Matched ${matches.length}, clipped ${clipped}.`;
    });

    panel.querySelector("#acme-clipper-all").addEventListener("click", async () => {
      statusEl.textContent = "Loading coupons...";
      await clickLoadMore(5);
      const cards = couponCards().filter((card) => !isClipped(card));
      const clipped = await clipCards(cards, statusEl);
      statusEl.textContent = `Clipped ${clipped} coupons on this page.`;
    });
  }

  renderPanel();
})();
