"use strict";

const $ = (sel) => document.querySelector(sel);
const LABEL = { dir: "DIR", image: "IMG", video: "VID", audio: "AUD", pdf: "PDF", code: "</>", text: "TXT", other: "FILE" };
const state = {
  path: null, root: "", entries: [], thumbs: false, filter: "",
  sort: localStorage.getItem("sort") || "name",
  view: localStorage.getItem("view") || (matchMedia("(max-width: 600px)").matches ? "list" : "grid"),
  seq: [], index: 0,
};

// Build DOM nodes; strings become text nodes, so file names are never parsed as HTML.
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

const q = encodeURIComponent;
const enc = (p) => p.split("/").map(q).join("/");
const href = (p, view = false) => "#/" + enc(p) + (view ? "?view" : "");
const parent = (p) => p.split("/").slice(0, -1).join("/");
const rawUrl = (p) => `/raw?path=${q(p)}`;

function parseHash() {
  let raw = location.hash.slice(1) || "/";
  const view = raw.endsWith("?view");
  if (view) raw = raw.slice(0, -5);
  let path = "";
  try { path = decodeURIComponent(raw); } catch { /* malformed hash: go home */ }
  return { path: path.replace(/^\/+|\/+$/g, ""), view };
}

async function api(url) {
  const r = await fetch(url, { credentials: "same-origin" });
  if (r.status === 401) { location.href = "/login"; throw new Error("login required"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

let errorTimer;
function showError(message) {
  const el = $("#error");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(errorTimer);
  errorTimer = setTimeout(() => { el.hidden = true; }, 4000);
}

function size(n) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(1) : n) + " " + units[i];
}
const day = (t) => new Date(t * 1000).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
const badge = (kind) => h("span", { class: `badge ${kind}` }, LABEL[kind] || LABEL.other);

async function loadDir(path) {
  if (state.path === path) return true;
  try {
    const data = await api(`/api/list?path=${q(path)}`);
    Object.assign(state, { path, root: data.root, entries: data.entries, thumbs: data.thumbs, filter: "" });
    $("#filter").value = "";
    $("#logout").hidden = !data.auth;
  } catch (e) {
    showError(e.message);
    return false;
  }
  renderCrumbs();
  renderList();
  return true;
}

function visible() {
  const f = state.filter.toLowerCase();
  const cmp = {
    name: (a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }),
    date: (a, b) => b.mtime - a.mtime,
    size: (a, b) => b.size - a.size,
  }[state.sort];
  return state.entries
    .filter((e) => e.name.toLowerCase().includes(f))
    .sort((a, b) => (a.type === b.type ? cmp(a, b) : a.type === "dir" ? -1 : 1));
}

function renderCrumbs() {
  const parts = state.path ? state.path.split("/") : [];
  const crumbs = $("#crumbs");
  crumbs.replaceChildren(h("a", { href: href("") }, state.root || "Home"));
  parts.forEach((p, i) => crumbs.append(h("span", { class: "sep" }, "/"), h("a", { href: href(parts.slice(0, i + 1).join("/")) }, p)));
  crumbs.scrollLeft = crumbs.scrollWidth;
  document.title = `${parts.at(-1) || state.root} - peekin`;
}

function item(e) {
  const kind = e.type === "dir" ? "dir" : e.kind;
  const icon = state.view === "grid" && state.thumbs && kind === "image"
    ? h("img", { class: "thumb", loading: "lazy", alt: "", src: `/thumb?path=${q(e.path)}`, onerror: (ev) => ev.target.replaceWith(badge(kind)) })
    : badge(kind);
  return h("a", { class: "item", href: href(e.path, e.type !== "dir") },
    icon,
    h("span", { class: "name" }, e.name),
    h("span", { class: "meta" }, e.type === "dir" ? "" : size(e.size)),
    h("span", { class: "meta date" }, day(e.mtime)));
}

function renderList() {
  const list = $("#list");
  const items = visible();
  list.className = state.view;
  list.replaceChildren(...items.map(item));
  if (!items.length) list.append(h("p", { class: "empty" }, state.filter ? "No matches." : "This folder is empty."));
  $("#view").textContent = state.view === "grid" ? "List" : "Grid";
}

function openViewer(path) {
  const entry = state.entries.find((e) => e.path === path);
  if (!entry) return showError("File not found.");
  const seq = visible().filter((e) => e.kind === "image" || e.kind === "video");
  state.seq = seq.some((e) => e.path === path) ? seq : [entry];
  state.index = state.seq.findIndex((e) => e.path === path);
  $("#viewer").hidden = false;
  document.body.classList.add("viewing");
  renderViewer();
}

function closeViewer() {
  if ($("#viewer").hidden) return;
  $("#viewer").hidden = true;
  $("#stage").replaceChildren();
  document.body.classList.remove("viewing");
}

function go(delta) {
  const next = state.seq[state.index + delta];
  if (next) location.replace(href(next.path, true));  // replace: Back returns to the folder
}

function renderViewer() {
  const e = state.seq[state.index];
  const raw = rawUrl(e.path);
  $("#v-name").textContent = e.name;
  $("#v-count").textContent = state.seq.length > 1 ? `${state.index + 1} / ${state.seq.length}` : "";
  $("#v-close").href = href(state.path);
  $("#v-open").href = raw;
  $("#v-download").href = raw + "&download=1";
  $("#v-prev").hidden = state.index <= 0;
  $("#v-next").hidden = state.index >= state.seq.length - 1;
  $("#stage").replaceChildren(content(e, raw));
  for (const d of [-1, 1]) {
    const n = state.seq[state.index + d];
    if (n && n.kind === "image") new Image().src = rawUrl(n.path);
  }
}

function info(e, note, ...extra) {
  return h("div", { class: "info" },
    badge(e.kind),
    h("h2", {}, e.name),
    h("p", { class: "muted" }, `${size(e.size)} - ${new Date(e.mtime * 1000).toLocaleString()}`),
    note ? h("p", {}, note) : null,
    ...extra,
    h("a", { class: "btn", href: rawUrl(e.path) + "&download=1" }, "Download"));
}

function codeView(e) {
  const box = h("div", { class: "codeview" }, h("p", { class: "muted" }, "Loading..."));
  api(`/api/code?path=${q(e.path)}`).then((d) => {
    if (d.binary) return box.replaceWith(info(e, "Binary file, no preview."));
    box.innerHTML = d.html;  // produced server-side by pygments or html.escape
    if (d.truncated) box.prepend(h("p", { class: "muted" }, "Showing the first 1 MB. Download for the full file."));
  }).catch((err) => box.replaceChildren(h("p", { class: "muted" }, err.message)));
  return box;
}

function content(e, raw) {
  switch (e.kind) {
    case "image":
      return h("img", { class: "media", src: raw, alt: e.name, draggable: "false" });
    case "video":
    case "audio": {
      const media = h(e.kind, { class: "media", src: raw, controls: true, preload: "metadata", playsinline: true });
      media.addEventListener("error", () => media.replaceWith(info(e, "Your browser can't play this format.")));
      return media;
    }
    case "pdf":
      return matchMedia("(pointer: coarse)").matches
        ? info(e, "", h("a", { class: "btn", href: raw, target: "_blank", rel: "noopener" }, "Open PDF"))
        : h("iframe", { class: "pdf", src: raw, title: e.name });
    case "code":
    case "text":
      return codeView(e);
    default:
      return info(e);
  }
}

function setupSwipe() {
  const stage = $("#stage");
  let start = null;
  stage.addEventListener("pointerdown", (ev) => {
    if (!ev.isPrimary || ev.target.closest(".codeview, .info")) return;
    const t = ev.target;
    if (t.tagName === "VIDEO" || t.tagName === "AUDIO") {
      const r = t.getBoundingClientRect();
      if (ev.clientY > r.top + r.height * 0.6) return;  // leave the native controls alone
    }
    start = { x: ev.clientX, y: ev.clientY, t: Date.now() };
  });
  stage.addEventListener("pointerup", (ev) => {
    if (!start) return;
    const dx = ev.clientX - start.x, dy = ev.clientY - start.y, quick = Date.now() - start.t < 300;
    start = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) go(dx < 0 ? 1 : -1);
    else if (quick && Math.abs(dx) < 10 && Math.abs(dy) < 10 && (ev.target === stage || ev.target.tagName === "IMG")) {
      $("#viewer").classList.toggle("bare");
    }
  });
  stage.addEventListener("pointercancel", () => { start = null; });
}

function setup() {
  const sort = $("#sort");
  sort.value = state.sort;
  sort.addEventListener("change", () => { state.sort = sort.value; localStorage.setItem("sort", sort.value); renderList(); });
  $("#view").addEventListener("click", () => {
    state.view = state.view === "grid" ? "list" : "grid";
    localStorage.setItem("view", state.view);
    renderList();
  });
  $("#filter").addEventListener("input", (ev) => { state.filter = ev.target.value; renderList(); });
  $("#v-prev").addEventListener("click", () => go(-1));
  $("#v-next").addEventListener("click", () => go(1));
  document.addEventListener("keydown", (ev) => {
    if ($("#viewer").hidden || ["INPUT", "VIDEO", "AUDIO"].includes(ev.target.tagName)) return;
    if (ev.key === "ArrowLeft") go(-1);
    else if (ev.key === "ArrowRight") go(1);
    else if (ev.key === "Escape") location.hash = href(state.path);
  });
  setupSwipe();
  addEventListener("hashchange", route);
}

async function route() {
  const { path, view } = parseHash();
  if (!view) {
    closeViewer();
    return loadDir(path);
  }
  if (await loadDir(parent(path))) openViewer(path);
}

setup();
route();
