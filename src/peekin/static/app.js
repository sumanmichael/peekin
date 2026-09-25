"use strict";

const $ = (sel) => document.querySelector(sel);
const ICON = { dir: "folder", image: "image", video: "film", audio: "music", pdf: "file-text", code: "file-code", markdown: "book-open", text: "file-type", other: "file" };
const state = {
  path: null, root: "", entries: [], thumbs: false, filter: "",
  sort: localStorage.getItem("sort") || "name",
  view: localStorage.getItem("view") || (matchMedia("(max-width: 640px)").matches ? "list" : "grid"),
  mdMode: "rendered",
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

function icon(name, cls = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `icon ${cls}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/icons.svg#${name}`);
  svg.append(use);
  return svg;
}
const kindIcon = (kind) => icon(ICON[kind] || ICON.other, `kind kind-${kind}`);

const q = encodeURIComponent;
const enc = (p) => p.split("/").map(q).join("/");
const href = (p, view = false) => "#/" + enc(p) + (view ? "?view" : "");
const parent = (p) => p.split("/").slice(0, -1).join("/");
const rawUrl = (p) => `/raw?path=${q(p)}`;

// Resolve a relative link from a document in `dir`; null when it climbs above the shared folder.
function join(dir, rel) {
  const parts = dir ? dir.split("/") : [];
  for (const seg of rel.split("/")) {
    if (seg === "..") { if (!parts.length) return null; parts.pop(); }
    else if (seg && seg !== ".") parts.push(seg);
  }
  return parts.join("/");
}

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
  if (r.status === 401) { location.href = "/login"; throw new Error("Log in to continue."); }
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
  parts.forEach((p, i) => crumbs.append(h("span", { class: "sep", "aria-hidden": "true" }, "/"), h("a", { href: href(parts.slice(0, i + 1).join("/")) }, p)));
  crumbs.scrollLeft = crumbs.scrollWidth;
  document.title = `${parts.at(-1) || state.root} - peekin`;
}

function item(e) {
  const kind = e.type === "dir" ? "dir" : e.kind;
  const link = { class: "item", href: href(e.path, e.type !== "dir") };
  const name = h("span", { class: kind === "dir" ? "name dirname" : "name", title: e.name }, e.name);
  if (state.view === "list") {
    return h("a", link, kindIcon(kind), name,
      h("span", { class: "meta" }, e.type === "dir" ? "" : size(e.size)),
      h("span", { class: "meta date" }, day(e.mtime)));
  }
  const ext = e.type === "dir" ? "" : (e.name.match(/\.([^.]{1,8})$/) || [])[1];
  const inside = state.thumbs && kind === "image"
    ? [h("img", { loading: "lazy", alt: "", src: `/thumb?path=${q(e.path)}`, onerror: (ev) => ev.target.replaceWith(kindIcon(kind)) })]
    : [kindIcon(kind), ext ? h("span", { class: "ext" }, ext.toLowerCase()) : null];
  return h("a", link, h("span", { class: `mount mount-${kind}` }, ...inside), name);
}

function renderList() {
  const list = $("#list");
  const items = visible();
  list.className = state.view;
  list.replaceChildren(...items.map(item));
  if (!items.length) {
    list.append(h("p", { class: "empty" }, state.filter ? `No files match "${state.filter}".` : "Nothing in this folder."));
  }
  const next = state.view === "grid" ? "list" : "layout-grid";
  $("#view").replaceChildren(icon(next));
  $("#view").setAttribute("aria-label", state.view === "grid" ? "Show as list" : "Show as grid");
}

function openViewer(path) {
  const entry = state.entries.find((e) => e.path === path);
  if (!entry) return showError("That file is no longer in this folder.");
  const seq = visible().filter((e) => e.kind === "image" || e.kind === "video");
  state.seq = seq.some((e) => e.path === path) ? seq : [entry];
  state.index = state.seq.findIndex((e) => e.path === path);
  const opening = $("#viewer").hidden;
  $("#viewer").hidden = false;
  document.body.classList.add("viewing");
  renderViewer(opening);
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

// `opening` plays the fade-in once; swiping between photos must swap instantly, not blink.
function renderViewer(opening = false) {
  const e = state.seq[state.index];
  const raw = rawUrl(e.path);
  $("#v-name").textContent = e.name;
  $("#v-count").textContent = state.seq.length > 1 ? `${state.index + 1} / ${state.seq.length}` : "";
  $("#v-close").href = href(state.path);
  $("#v-open").href = raw;
  $("#v-download").href = raw + "&download=1";
  $("#v-prev").hidden = state.index <= 0;
  $("#v-next").hidden = state.index >= state.seq.length - 1;
  $("#v-mode").hidden = e.kind !== "markdown";
  $("#v-rendered").setAttribute("aria-pressed", String(state.mdMode === "rendered"));
  $("#v-source").setAttribute("aria-pressed", String(state.mdMode === "source"));
  $("#stage").replaceChildren(content(e, raw, opening));
  for (const d of [-1, 1]) {
    const n = state.seq[state.index + d];
    if (n && n.kind === "image") new Image().src = rawUrl(n.path);
  }
}

function info(e, note, ...extra) {
  return h("div", { class: "info" },
    kindIcon(e.kind),
    h("h2", {}, e.name),
    h("p", { class: "muted" }, `${size(e.size)}, modified ${new Date(e.mtime * 1000).toLocaleString()}`),
    note ? h("p", {}, note) : null,
    ...extra,
    h("a", { class: "btn", href: rawUrl(e.path) + "&download=1" }, icon("download"), "Download"));
}

function codeView(e) {
  const box = h("div", { class: "paper codeview" }, h("p", { class: "note" }, "Loading..."));
  api(`/api/code?path=${q(e.path)}`).then((d) => {
    if (d.binary) return box.replaceWith(info(e, "This is a binary file, so there's no text preview."));
    box.innerHTML = d.html;  // produced server-side by pygments or html.escape
    if (d.truncated) box.prepend(h("p", { class: "note" }, "Showing the first 1 MB. Download the file to see all of it."));
  }).catch((err) => box.replaceChildren(h("p", { class: "note" }, err.message)));
  return box;
}

// Point relative links and images inside a rendered document at peekin itself.
function wireDocument(article, dir) {
  const external = /^[a-z][a-z0-9+.-]*:|^\/\//i;
  for (const img of article.querySelectorAll("img")) {
    const src = img.getAttribute("src") || "";
    const target = external.test(src) || src.startsWith("/") ? null : join(dir, decodeURIComponent(src.split(/[?#]/)[0]));
    if (target === null) img.replaceWith(h("span", { class: "missing-img" }, img.alt || "(external image)"));
    else img.src = rawUrl(target);
  }
  for (const a of article.querySelectorAll("a[href]")) {
    const link = a.getAttribute("href");
    if (external.test(link)) { a.target = "_blank"; a.rel = "noopener noreferrer"; continue; }
    if (link.startsWith("#")) { a.removeAttribute("href"); continue; }  // in-page anchors: headings have no ids
    const target = link.startsWith("/") ? null : join(dir, decodeURIComponent(link.split(/[?#]/)[0]));
    if (target === null) { a.removeAttribute("href"); continue; }
    const isFile = /\.[^/]+$/.test(target);
    a.href = href(target, isFile);
  }
}

function markdownView(e) {
  const box = h("div", { class: "paper" }, h("p", { class: "note" }, "Loading..."));
  api(`/api/markdown?path=${q(e.path)}`).then((d) => {
    // Parse into an inert template (markdown-it with raw HTML disabled; see preview.py) so no image
    // starts loading before wireDocument has pointed it at the shared folder.
    const tpl = h("template");
    tpl.innerHTML = d.html;
    wireDocument(tpl.content, parent(e.path));
    box.replaceChildren(h("article", { class: "md" }, tpl.content));
    if (d.truncated) box.prepend(h("p", { class: "note" }, "This file is over 1 MB, so it's shown as plain text."));
  }).catch((err) => box.replaceChildren(h("p", { class: "note" }, err.message)));
  return box;
}

function content(e, raw, opening) {
  switch (e.kind) {
    case "image":
      return h("img", { class: opening ? "media develop" : "media", src: raw, alt: e.name, draggable: "false" });
    case "video":
    case "audio": {
      const media = h(e.kind, { class: "media", src: raw, controls: true, preload: "metadata", playsinline: true });
      media.addEventListener("error", () => media.replaceWith(info(e, "Your browser can't play this format. Download it to open it in another app.")));
      return media;
    }
    case "pdf":
      return matchMedia("(pointer: coarse)").matches
        ? info(e, "", h("a", { class: "btn", href: raw, target: "_blank", rel: "noopener" }, icon("external-link"), "Open PDF"))
        : h("iframe", { class: "pdf", src: raw, title: e.name });
    case "markdown":
      return state.mdMode === "rendered" ? markdownView(e) : codeView(e);
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
    if (!ev.isPrimary || ev.target.closest(".paper, .info")) return;
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

function setMdMode(mode) {
  if (state.mdMode === mode) return;
  state.mdMode = mode;
  renderViewer();
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
  $("#search-toggle").addEventListener("click", () => {
    const open = $("#bar").classList.toggle("searching");
    $("#search-toggle").setAttribute("aria-expanded", String(open));
    if (open) $("#filter").focus();
  });
  $("#v-prev").addEventListener("click", () => go(-1));
  $("#v-next").addEventListener("click", () => go(1));
  $("#v-rendered").addEventListener("click", () => setMdMode("rendered"));
  $("#v-source").addEventListener("click", () => setMdMode("source"));
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
