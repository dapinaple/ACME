const LIST_KEY = "acme_clipper_local_list";

const groceryListEl = document.getElementById("grocery-list");
const emptyListEl = document.getElementById("empty-list");
const addItemForm = document.getElementById("add-item-form");
const copyListBtn = document.getElementById("copy-list-btn");
const clearListBtn = document.getElementById("clear-list-btn");
const copyScriptUrlBtn = document.getElementById("copy-script-url");
const scriptUrlEl = document.getElementById("script-url");
const toastEl = document.getElementById("toast");

function loadList() {
  try {
    return JSON.parse(localStorage.getItem(LIST_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveList(items) {
  localStorage.setItem(LIST_KEY, JSON.stringify(items));
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  setTimeout(() => toastEl.classList.add("hidden"), 3200);
}

function renderList(items) {
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
    removeBtn.addEventListener("click", () => {
      const next = loadList().filter((entry) => entry !== item);
      saveList(next);
      renderList(next);
    });
    li.append(name, removeBtn);
    groceryListEl.appendChild(li);
  }
}

addItemForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("new-item");
  const value = input.value.trim();
  if (!value) return;
  const next = [...loadList(), value];
  saveList(next);
  renderList(next);
  input.value = "";
});

copyListBtn.addEventListener("click", async () => {
  const items = loadList();
  if (!items.length) {
    showToast("Add items to your list first");
    return;
  }
  const text = items.join("\n");
  try {
    await navigator.clipboard.writeText(text);
    showToast("Copied! Paste into the clipper on acmemarkets.com");
  } catch {
    showToast(text);
  }
});

clearListBtn.addEventListener("click", () => {
  saveList([]);
  renderList([]);
});

copyScriptUrlBtn.addEventListener("click", async () => {
  const url = `${window.location.origin}/static/acme-clipper.user.js`;
  try {
    await navigator.clipboard.writeText(url);
    showToast("Script URL copied");
  } catch {
    showToast(url);
  }
});

scriptUrlEl.textContent = `${window.location.origin}/static/acme-clipper.user.js`;
renderList(loadList());

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  });
}
