const STORAGE_KEY = "acme_clipper_session";

const loginSection = document.getElementById("login-section");
const dashboard = document.getElementById("dashboard");
const loginForm = document.getElementById("login-form");
const logoutBtn = document.getElementById("logout-btn");
const addItemForm = document.getElementById("add-item-form");
const syncListBtn = document.getElementById("sync-list-btn");
const refreshMatchesBtn = document.getElementById("refresh-matches-btn");
const clipMatchingBtn = document.getElementById("clip-matching-btn");
const clipAllBtn = document.getElementById("clip-all-btn");
const groceryListEl = document.getElementById("grocery-list");
const matchListEl = document.getElementById("match-list");
const emptyListEl = document.getElementById("empty-list");
const matchSummaryEl = document.getElementById("match-summary");
const clipResultEl = document.getElementById("clip-result");
const toastEl = document.getElementById("toast");

let session = loadSession();

function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch {
    return null;
  }
}

function saveSession(data) {
  session = data;
  if (data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  setTimeout(() => toastEl.classList.add("hidden"), 3200);
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (session?.token) {
    headers.Authorization = `Bearer ${session.token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }
  return data;
}

function setLoading(button, loading, label) {
  button.disabled = loading;
  button.dataset.label = button.dataset.label || button.textContent;
  button.textContent = loading ? label : button.dataset.label;
}

function renderGroceryList(items) {
  groceryListEl.innerHTML = "";
  if (!items.length) {
    emptyListEl.classList.remove("hidden");
    return;
  }

  emptyListEl.classList.add("hidden");
  for (const item of items) {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = item;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", async () => {
      const next = items.filter((entry) => entry !== item);
      await saveGroceryList(next);
    });
    li.append(name, removeBtn);
    groceryListEl.appendChild(li);
  }
}

function renderMatches(matches) {
  matchListEl.innerHTML = "";
  if (!matches.length) {
    matchSummaryEl.textContent = "No matching coupons found for your list right now.";
    return;
  }

  matchSummaryEl.textContent = `${matches.length} coupon${matches.length === 1 ? "" : "s"} match your grocery list.`;
  for (const match of matches) {
    const li = document.createElement("li");
    const content = document.createElement("div");
    const title = document.createElement("div");
    title.className = "coupon-title";
    title.textContent = match.name || match.brand || "Coupon";
    const meta = document.createElement("div");
    meta.className = "coupon-meta";
    meta.textContent = `${match.description} • matched: ${match.matched_terms.join(", ")}`;
    content.append(title, meta);

    const badge = document.createElement("span");
    badge.className = `badge${match.is_clipped ? " clipped" : ""}`;
    badge.textContent = match.is_clipped ? "Clipped" : `${Math.round(match.score * 100)}%`;

    li.append(content, badge);
    matchListEl.appendChild(li);
  }
}

async function saveGroceryList(items) {
  const data = await api("/api/list", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
  renderGroceryList(data.items);
  await refreshMatches();
}

async function refreshMatches() {
  const data = await api("/api/coupons/matches");
  renderMatches(data.matches || []);
}

function showDashboard() {
  loginSection.classList.add("hidden");
  dashboard.classList.remove("hidden");
  document.getElementById("user-email").textContent = session.email;
  document.getElementById("user-store").textContent = session.store_id;
}

function showLogin() {
  dashboard.classList.add("hidden");
  loginSection.classList.remove("hidden");
}

async function bootstrap() {
  if (!session?.token) {
    showLogin();
    return;
  }

  try {
    const list = await api("/api/list");
    showDashboard();
    renderGroceryList(list.items || []);
    await refreshMatches();
  } catch (error) {
    saveSession(null);
    showLogin();
    showToast(error.message);
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const loginBtn = document.getElementById("login-btn");
  setLoading(loginBtn, true, "Signing in...");

  try {
    const payload = {
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
      store_id: document.getElementById("store-id").value.trim(),
    };

    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    saveSession(data);
    showDashboard();
    document.getElementById("user-email").textContent = data.email;
    document.getElementById("user-store").textContent = data.store_id;

    const list = await api("/api/list");
    renderGroceryList(list.items || []);
    await refreshMatches();
    showToast("Signed in successfully");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(loginBtn, false);
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {
    // ignore logout errors
  }
  saveSession(null);
  showLogin();
});

addItemForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("new-item");
  const value = input.value.trim();
  if (!value) return;

  const list = await api("/api/list");
  const next = [...(list.items || []), value];
  input.value = "";
  await saveGroceryList(next);
});

syncListBtn.addEventListener("click", async () => {
  setLoading(syncListBtn, true, "Syncing...");
  try {
    const data = await api("/api/list/sync", { method: "POST" });
    renderGroceryList(data.items || []);
    await refreshMatches();
    showToast(`Synced ${data.imported_from_acme?.length || 0} items from ACME`);
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(syncListBtn, false);
  }
});

refreshMatchesBtn.addEventListener("click", async () => {
  setLoading(refreshMatchesBtn, true, "Refreshing...");
  try {
    await refreshMatches();
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(refreshMatchesBtn, false);
  }
});

clipMatchingBtn.addEventListener("click", async () => {
  setLoading(clipMatchingBtn, true, "Clipping...");
  try {
    const data = await api("/api/coupons/clip", {
      method: "POST",
      body: JSON.stringify({}),
    });
    clipResultEl.classList.remove("hidden");
    clipResultEl.textContent = `Clipped ${data.clipped} of ${data.requested} matching coupons.`;
    if (data.errors?.length) {
      clipResultEl.textContent += `\n\nSome errors:\n${data.errors.join("\n")}`;
    }
    await refreshMatches();
    showToast(`Clipped ${data.clipped} coupons`);
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(clipMatchingBtn, false);
  }
});

clipAllBtn.addEventListener("click", async () => {
  if (!confirm("Clip every available coupon on your account? This can take a minute.")) {
    return;
  }

  setLoading(clipAllBtn, true, "Clipping all...");
  try {
    const data = await api("/api/coupons/clip", {
      method: "POST",
      body: JSON.stringify({ clip_all: true }),
    });
    clipResultEl.classList.remove("hidden");
    clipResultEl.textContent = `Clipped ${data.clipped} of ${data.requested} available coupons.`;
    await refreshMatches();
    showToast(`Clipped ${data.clipped} coupons`);
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(clipAllBtn, false);
  }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  });
}

bootstrap();
