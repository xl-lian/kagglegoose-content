import { words } from "./words.js";

const paths = {
  feed: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  book:
    '<path d="M3 5c4-1 6-.5 9 1.5C15 4.5 17 4 21 5v14c-4-1-6-.5-9 1.5C9 18.5 7 18 3 19z"/><path d="M12 6.5v14"/>',
  flag: '<path d="M5 21V4c5-4 9 4 14 0v10c-5 4-9-4-14 0"/>',
  study: '<path d="m2 9 10-5 10 5-10 5zM6 11v5c3 3 9 3 12 0v-5M21 10v6"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
  award: '<circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/>',
  bookmark: '<path d="M6 4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17l-6-4-6 4z"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  search: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/>',
  layers: '<path d="m3 8 9-5 9 5-9 5zm0 5 9 5 9-5m-18 5 9 5 9-5"/>',
  spark: '<path d="m12 2 2.5 6.5L21 11l-6.5 2.5L12 20l-2.5-6.5L3 11l6.5-2.5z"/>',
  score: '<path d="M4 3v17h17M7 15l4-5 4 2 5-7"/>',
  link: '<path d="m10 13 4-4M8 10l-2 2a4 4 0 0 0 6 6l2-2m-4-8 2-2a4 4 0 0 1 6 6l-2 2"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
};
const icon = (name) => '<svg aria-hidden="true" viewBox="0 0 24 24" class="icon">' + paths[name] + "</svg>";
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );
const route = (page, id) => "#/" + page + (id == null ? "" : "/" + encodeURIComponent(id));
const href = (page, id) => esc(route(page, id));
const main = document.querySelector("main");
const DAY = 86400000;
const dbKey = "kagglegoose.study.v1";
let data, competitions, lessons, english = false, model;
let storyFilter = "all", feedLimit = 10;
const filters = {
  library: { category: "", search: "", kind: "readable" },
  competitions: { category: "", search: "", kind: "all" },
};
let studyFilter = "reading";
function readModel() {
  let value;
  try {
    value = JSON.parse(localStorage.getItem(dbKey));
  } catch {}
  return { lessons: value?.lessons || {}, following: value?.following || {}, days: value?.days || {} };
}
model = readModel();
try {
  english = localStorage.getItem("kagglegoose.language") === "en";
} catch {}
const tr = (zh, en) => english ? en : zh;
const word = (key) => english ? words[key] || key : key;
const copy = (item, key) => english ? item[key + "EN"] || word(item[key]) : item[key];
const bilingual = (item) => item?.[english ? "en" : "zh"] || item?.zh;
const language = () => english ? "en-US" : "zh-CN";
const date = (raw, opts = { month: "short", day: "numeric" }) => {
  const d = new Date(raw);
  return Number.isFinite(+d) ? d.toLocaleDateString(language(), opts) : "—";
};
const fullDate = (raw) => date(raw, { year: "numeric", month: "short", day: "numeric" });
const active = (c) => Date.parse(c.start) <= Date.now() && Date.parse(c.deadline) > Date.now();
const readable = (l) => !l.awaitingExplanation && !l.stale && l.steps.length > 0;
const fresh = (l) =>
  !l.stale && (l.evidence.kind === "final" || Date.now() - Date.parse(l.evidence.checked) < 1.5 * DAY);
const byPublished = (a, b) => Date.parse(b.published) - Date.parse(a.published) || a.id.localeCompare(b.id);
const record = (id) => model.lessons[id] || {};
const stepKey = (l, s) => JSON.stringify([l.sources[s.source]?.url, s.reference, s.title]);
const done = (l) => l.steps.filter((s) => record(l.id).steps?.includes(stepKey(l, s))).length;
const finished = (l) => readable(l) && done(l) === l.steps.length;
function save(change) {
  model = readModelOrMemory();
  change(model);
  try {
    localStorage.setItem(dbKey, JSON.stringify(model));
    return true;
  } catch {
    storageFailed = true;
    return false;
  }
}
let storageFailed = false;
function readModelOrMemory() {
  return storageFailed ? model : readModel();
}
function editLesson(id, change) {
  return save((m) => change(m.lessons[id] ||= {}));
}
function getRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  try {
    return { page: parts[0] || "feed", id: decodeURIComponent(parts.slice(1).join("/")) };
  } catch {
    return { page: "missing", id: "" };
  }
}
const names = () => ({
  feed: tr("竞赛动态", "Feed"),
  library: tr("方案库", "Library"),
  competitions: tr("竞赛", "Competitions"),
  study: tr("我的学习", "My study"),
});
const symbols = { feed: "feed", library: "book", competitions: "flag", study: "study" };
function chrome(page) {
  document.documentElement.lang = language();
  const nav = document.querySelector("#nav");
  nav.setAttribute("aria-label", tr("主导航", "Main navigation"));
  nav.innerHTML = Object.entries(names()).map(([p, n]) => {
    const current = page === p || (p === "library" && ["lesson", "method"].includes(page)) ||
      (p === "competitions" && page === "competition");
    return '<a class="nav-link' + (current ? ' active" aria-current="page' : "") + '" href="' + href(p) +
      '">' + icon(symbols[p]) + n + "</a>";
  }).join("");
  const lang = document.querySelector("#language");
  lang.innerHTML = icon("globe") + tr("English", "中文");
  lang.setAttribute("aria-label", tr("Switch to English", "切换到中文"));
  const theme = document.querySelector("#theme");
  if (theme) {
    theme.setAttribute("aria-label", tr("外观主题", "Appearance"));
    const labels = { system: tr("跟随系统", "System"), light: tr("浅色", "Light"), dark: tr("暗色", "Dark") };
    for (const option of theme.options) option.textContent = labels[option.value];
  }
  document.querySelector(".skip").textContent = tr("跳到内容", "Skip to content");
  document.querySelector("#catalog-link").textContent = tr("公开内容目录", "Public catalog");
}
function heading(title, subtitle, stats = []) {
  return '<div class="page-head"><div><h1>' + esc(title) + '</h1><p class="sub">' + subtitle + "</p></div>" +
    (stats.length
      ? '<div class="stats">' + stats.map(([n, label]) =>
        '<div class="stat"><strong>' + esc(n) + "</strong><span>" + esc(label) + "</span></div>"
      ).join("") + "</div>"
      : "") +
    "</div>";
}
const blank = (message) => '<p class="blank">' + esc(message) + "</p>";
const section = (title) => '<div class="section-head"><h2>' + esc(title) + "</h2></div>";
const link = (page, id, label, cls = "text-link") =>
  '<a class="' + cls + '" href="' + href(page, id) + '">' + esc(label) + "</a>";
function action(name, label, pressed = null, ico = "") {
  return '<button type="button" class="secondary" data-action="' + name + '"' +
    (pressed === null ? "" : ' aria-pressed="' + pressed + '"') + ">" + (ico ? icon(ico) : "") + esc(label) +
    "</button>";
}
function safeURL(raw) {
  try {
    const u = new URL(raw);
    return u.protocol === "https:" ? esc(u.href) : "";
  } catch {
    return "";
  }
}
function external(raw, label, cls = "source") {
  const url = safeURL(raw);
  return url
    ? '<a class="' + cls + '" href="' + url + '" target="_blank" rel="noopener noreferrer">' + esc(label) +
      icon("link") + "</a>"
    : esc(label);
}
function timeLeft(c) {
  const days = (Date.parse(c.deadline) - Date.now()) / DAY;
  if (!Number.isFinite(days)) return tr("日期未知", "Date unknown");
  if (days <= 0) return tr("已结束", "Ended");
  if (days > 400) return tr("长期开放", "Open-ended");
  if (days < 1) {
    const h = Math.max(1, Math.floor(days * 24));
    return tr("剩 " + h + " 小时", h + " h left");
  }
  const n = Math.floor(days);
  return tr("剩 " + n + " 天", n + (n === 1 ? " day left" : " days left"));
}
function evidence(l) {
  if (!fresh(l)) return tr("上次核验记录", "Previously verified");
  if (l.evidence.kind === "final") {
    return tr("最终第 " + l.evidence.rank + " 名", "Final rank #" + l.evidence.rank);
  }
  return tr("公开榜前 10%", "Public top 10%");
}
function tags(items, counted = false) {
  return '<div class="tags">' + items.map((item) => {
    const [tag, count] = counted ? item : [item, null];
    return '<a class="tag" href="' + href("method", tag) + '">' + esc(word(tag)) +
      (count === null ? "" : "<b>" + count + "</b>") + "</a>";
  }).join("") + "</div>";
}
const methodsOf = (l) =>
  l.tags.filter((tag) =>
    !["Writeup", "Notebook", ...competitions.get(l.competitionID).categories].includes(tag)
  );
function methods(items) {
  const counts = new Map();
  for (const l of items.filter(readable)) {
    for (const tag of methodsOf(l)) counts.set(tag, (counts.get(tag) || 0) + 1);
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
const storyInfo = () => ({
  all: [tr("全部", "All"), "feed"],
  new: [tr("新开赛", "New competitions"), "flag"],
  score: [tr("赛中高分", "Public scores"), "score"],
  writeup: [tr("赛后复盘", "Writeups"), "book"],
  soon: [tr("即将截止", "Closing soon"), "clock"],
});
function stories() {
  const rows = [];
  for (const c of data.competitions.filter(active)) {
    rows.push({ kind: "new", c, when: c.start });
    if (Date.parse(c.deadline) - Date.now() <= 7 * DAY) rows.push({ kind: "soon", c, when: c.deadline });
  }
  for (const l of data.lessons) {
    const c = competitions.get(l.competitionID);
    if (!fresh(l) || Date.parse(l.published) > Date.now() || (l.evidence.kind !== "final" && !active(c))) {
      continue;
    }
    rows.push({ kind: l.evidence.kind === "final" ? "writeup" : "score", l, c, when: l.published });
  }
  return rows.sort((a, b) =>
    a.kind === "soon" && b.kind === "soon"
      ? Date.parse(a.when) - Date.parse(b.when)
      : (b.kind === "soon") - (a.kind === "soon") || Date.parse(b.when) - Date.parse(a.when)
  );
}
function chip(actionName, value, label, selected) {
  return '<button type="button" class="chip' + (selected ? " active" : "") + '" aria-pressed="' + selected +
    '" data-action="' + actionName + '" data-value="' + esc(value) + '">' + esc(label) + "</button>";
}
function feedStream() {
  const info = storyInfo();
  const rows = stories().filter((row) => storyFilter === "all" || row.kind === storyFilter);
  const filterBar = '<div class="filters">' +
    Object.keys(info).map((kind) => chip("story-filter", kind, info[kind][0], kind === storyFilter)).join(
      "",
    ) + "</div>";
  const contents = rows.slice(0, feedLimit).map(({ kind, l, c, when }) =>
    '<a class="story" href="' + (l ? href("lesson", l.id) : href("competition", c.id)) +
    '"><span class="story-icon tone-' + kind + '">' + icon(info[kind][1]) +
    '</span><div><span class="story-type">' + info[kind][0] + '</span><span class="story-title">' +
    esc(l ? copy(l, "title") : c.title) + '</span><span class="meta">' +
    esc(l ? c.title : copy(c, "summary")) + '</span></div><time datetime="' + esc(when) + '">' + date(when) +
    "</time></a>"
  ).join("");
  return section(tr("最新动向", "Latest updates")) + filterBar +
    (contents
      ? '<div class="collection">' + contents + "</div>"
      : blank(tr("暂时没有这类动态。", "No updates in this category yet."))) +
    (rows.length > feedLimit
      ? '<button type="button" class="more" data-action="more">' + tr("查看更多动态", "Show more updates") +
        "</button>"
      : "");
}
function hero() {
  const bird = lessons.get("w-11537");
  const l = bird && readable(bird) ? bird : data.lessons.find(readable);
  if (!l) return "";
  const c = competitions.get(l.competitionID);
  return '<article class="hero">' +
    (l === bird ? '<img src="./assets/birdclef.jpg" alt="" fetchpriority="high">' : "") +
    '<div class="hero-body"><div class="hero-kicker">' + icon("book") +
    tr("方案精读", "Featured walkthrough") + '</div><div class="hero-meta">' + esc(c.title) + " · " +
    esc(evidence(l)) + "</div><h2>" + esc(copy(l, "title")) + "</h2><p>" + esc(copy(l, "summary")) +
    '</p><a class="hero-cta" href="' + href("lesson", l.id) + '">' + icon("book") +
    tr("阅读讲解", "Read walkthrough") + "</a></div></article>";
}
function deadlines() {
  const upcoming = data.competitions.filter((c) =>
    active(c) && Date.parse(c.deadline) - Date.now() <= 400 * DAY
  ).sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline)).slice(0, 3);
  return '<aside class="panel deadlines"><div class="panel-head"><h2 class="title-with-icon">' +
    icon("calendar") + tr("临近截止", "Upcoming deadlines") + "</h2>" +
    link("competitions", null, tr("全部竞赛", "View all")) + '</div><div class="dead-list">' +
    (upcoming.map((c) =>
      '<a class="dead-row" href="' + href("competition", c.id) + '"><span class="date-tile"><small>' +
      date(c.deadline, { month: "short" }) + "</small><b>" + new Date(c.deadline).getDate() +
      "</b></span><div><strong>" + esc(c.title) + '</strong><span class="meta">' + esc(timeLeft(c)) + " · " +
      esc(c.categories.map(word).join(" / ")) + "</span></div></a>"
    ).join("") || '<p class="sub">' + tr("暂无临近截止的比赛。", "No upcoming deadlines.") + "</p>") +
    "</div></aside>";
}
function progressBar(l) {
  const n = done(l);
  return '<div class="bar" aria-hidden="true"><span style="width:' +
    Math.round(100 * n / Math.max(l.steps.length, 1)) + '%"></span></div><span class="meta">' +
    tr("已复现 " + n + " / " + l.steps.length + " 步", n + " of " + l.steps.length + " steps reproduced") +
    "</span>";
}
function feed() {
  const inProgress = data.lessons.filter((l) => readable(l) && record(l.id).opened && !finished(l)).sort((
    a,
    b,
  ) => record(b.id).opened - record(a.id).opened);
  const resume = inProgress[0];
  let side = '<aside class="panel"><div class="panel-head"><h2 class="title-with-icon">' + icon("layers") +
    tr("热门方法", "Popular methods") + "</h2></div>" + tags(methods(data.lessons).slice(0, 10), true) +
    "</aside>";
  if (resume) {
    side = '<a class="panel resume" href="' + href("lesson", resume.id) + '"><span class="badge">' +
      icon("bookmark") + tr("继续阅读", "Continue reading") + "</span><strong>" + esc(copy(resume, "title")) +
      "</strong>" + progressBar(resume) + "</a>" + side;
  }
  const updated = new Date(data.updated).toLocaleString(language(), {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return heading(names().feed, icon("clock") + esc(tr("目录更新于 ", "Catalog updated ") + updated), [[
    data.competitions.filter(active).length,
    tr("进行中", "Active"),
  ], [data.lessons.filter(readable).length, tr("方案讲解", "Walkthroughs")]]) +
    '<div class="dashboard">' + hero() + deadlines() + '<section id="feed-stream" class="feed-stream">' +
    feedStream() + '</section><div class="side-stack">' + side + "</div></div>";
}
function lessonCard(l) {
  const c = competitions.get(l.competitionID);
  const status = finished(l)
    ? tr("已学完", "Completed")
    : record(l.id).saved
    ? tr("已收藏", "Saved")
    : record(l.id).opened
    ? tr("在读", "Reading")
    : "";
  return '<a class="list-card" href="' + href("lesson", l.id) + '"><span class="badge">' +
    icon(l.evidence.kind === "final" ? "award" : "score") + esc(evidence(l)) +
    '</span><span class="list-title">' + esc(copy(l, "title")) + "</span><p>" + esc(copy(l, "summary")) +
    '</p><span class="meta card-foot">' + esc(c.title) + (status ? " · " + esc(status) : "") + "</span></a>";
}
function competitionCard(c) {
  return '<a class="list-card" href="' + href("competition", c.id) + '"><span class="badge">' + icon("flag") +
    esc(timeLeft(c)) + '</span><span class="list-title">' + esc(c.title) + "</span><p>" +
    esc(copy(c, "summary")) + '</p><span class="meta card-foot">' + esc(c.categories.map(word).join(" / ")) +
    (model.following[c.id] ? " · " + tr("已关注", "Following") : "") + "</span></a>";
}
function grid(items, card, empty) {
  return items.length ? '<div class="card-grid">' + items.map(card).join("") + "</div>" : blank(empty);
}
const noMatches = () => tr("没有符合条件的结果。", "No matching results.");
function select(name, label, options, current) {
  return '<span class="select-wrap"><select aria-label="' + esc(label) + '" data-select="' + name + '">' +
    options.map(([v, n]) =>
      '<option value="' + esc(v) + '"' + (v === current ? " selected" : "") + ">" + esc(n) + "</option>"
    ).join("") + "</select>" + icon("down") + "</span>";
}
function collection(page, id) {
  const isLibrary = page !== "competitions";
  const state = filters[isLibrary ? "library" : "competitions"];
  const title = page === "method" ? word(id) : names()[page];
  const categories = [...new Set(data.competitions.flatMap((c) => c.categories))].sort();
  const scopes = isLibrary
    ? [
      ["readable", tr("方案讲解", "Walkthroughs")],
      ["all", tr("含待讲解记录", "Include result records")],
      ["final", tr("获奖复盘", "Final writeups")],
      ["code", tr("源码导读", "Notebook guides")],
      ["saved", tr("已收藏", "Saved")],
    ]
    : [["all", tr("全部赛程", "All schedules")], ["active", tr("进行中", "Active")], [
      "ended",
      tr("已结束", "Ended"),
    ], ["following", tr("已关注", "Following")]];
  const prompt = isLibrary
    ? tr("搜索竞赛、作者或方法", "Search competitions, authors or methods")
    : tr("搜索竞赛", "Search competitions");
  const back = page === "method"
    ? '<div class="crumb">' + link("library", null, names().library) + " / " + tr("方法索引", "Methods") +
      "</div>"
    : "";
  return back +
    heading(
      title,
      esc(
        isLibrary
          ? tr("从榜单成绩出发，读懂每一步做法。", "Explore methods with leaderboard evidence.")
          : tr("查看赛程、评估指标与相关方案。", "Browse schedules, metrics and related walkthroughs."),
      ),
    ) +
    '<div class="catalog-controls"><label class="search">' + icon("search") +
    '<input type="search" id="search" aria-label="' + esc(prompt) + '" placeholder="' + esc(prompt) +
    '" value="' + esc(state.search) + '"></label>' +
    select("category", tr("任务类型", "Task type"), [
      ["", tr("全部任务", "All tasks")],
      ...categories.map((v) => [v, word(v)]),
    ], state.category) +
    select("kind", tr("内容筛选", "Filter results"), scopes, state.kind) + '</div><div id="results">' +
    collectionResults(page, id) + "</div>";
}
function collectionResults(page, id) {
  const isLibrary = page !== "competitions";
  const state = filters[isLibrary ? "library" : "competitions"];
  const q = state.search.trim().toLocaleLowerCase();
  const includes = (parts) => !q || parts.join(" ").toLocaleLowerCase().includes(q);
  const matchesCategory = (c) => !state.category || c.categories.includes(state.category);
  let items;
  if (isLibrary) {
    items = data.lessons.filter((l) => {
      const c = competitions.get(l.competitionID);
      if (!matchesCategory(c) || (page === "method" && !l.tags.includes(id))) return false;
      if (state.kind === "saved" ? !record(l.id).saved : state.kind !== "all" && !readable(l)) return false;
      if (
        state.kind === "final" && l.evidence.kind !== "final" ||
        state.kind === "code" && l.readingMode !== "code"
      ) return false;
      return includes([
        l.title,
        l.titleEN,
        l.author,
        l.summary,
        l.summaryEN,
        c.title,
        ...l.tags,
        ...l.tags.map(word),
        ...c.categories,
        ...c.categories.map(word),
      ]);
    }).sort(byPublished);
  } else {
    items = data.competitions.filter((c) =>
      matchesCategory(c) &&
      includes([c.title, c.summary, c.summaryEN, ...c.categories, ...c.categories.map(word)]) &&
      (state.kind === "all" || state.kind === "active" && active(c) ||
        state.kind === "ended" && Date.parse(c.deadline) <= Date.now() ||
        state.kind === "following" && model.following[c.id])
    )
      .sort((a, b) =>
        Number(active(b)) - Number(active(a)) ||
        (active(a)
          ? Date.parse(a.deadline) - Date.parse(b.deadline)
          : Date.parse(b.deadline) - Date.parse(a.deadline))
      );
  }
  return '<p class="meta result-line" role="status">' +
    tr("共 " + items.length + " 条结果", items.length + " results") + "</p>" +
    grid(items, isLibrary ? lessonCard : competitionCard, noMatches());
}
function crumb(page, title) {
  return '<div class="crumb">' + link(page, null, names()[page]) + "<span>/</span><span>" + esc(title) +
    "</span></div>";
}
const panelTitle = (ico, title) => '<h2 class="title-with-icon">' + icon(ico) + esc(title) + "</h2>";
function metricList(rows) {
  return '<dl class="metrics">' +
    rows.map(([k, v]) => "<div><dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd></div>").join("") + "</dl>";
}
function lessonView(l) {
  const c = competitions.get(l.competitionID);
  const r = record(l.id);
  const e = l.evidence;
  const saveButton = action(
    "save",
    r.saved ? tr("已收藏", "Saved") : tr("收藏方案", "Save solution"),
    !!r.saved,
    "bookmark",
  );
  const top = crumb("library", tr("方案详情", "Solution details")) +
    '<header class="reader-top"><span class="badge">' + icon(e.kind === "final" ? "award" : "score") +
    esc(evidence(l)) + '</span><h1 class="detail-title">' + esc(copy(l, "title")) + '</h1><p class="sub">' +
    link("competition", c.id, c.title) + " · " + esc(l.author) + " · " + esc(fullDate(l.published)) +
    "</p></header>";
  const intro = '<section class="reader-block"><h2>' + tr("一分钟速读", "At a glance") + "</h2><p>" +
    esc(copy(l, "summary")) + "</p>" + tags(methodsOf(l)) + '<div class="actions">' + saveButton +
    "</div></section>";
  const steps = l.steps.map((s, i) => {
    const source = l.sources[s.source];
    const checked = r.steps?.includes(stepKey(l, s)) || false;
    const mark = checked
      ? tr("取消复现标记", "Unmark reproduced step")
      : tr("标记已复现", "Mark step as reproduced");
    return '<div class="step"><button class="step-check" data-action="step" data-index="' + i +
      '" aria-label="' + esc(mark + " · " + copy(s, "title")) + '" aria-pressed="' + checked + '">' +
      (checked ? icon("check") : i + 1) + "</button><div><h3>" + esc(copy(s, "title")) + "</h3><p>" +
      esc(copy(s, "body")) + "</p>" +
      (source ? external(source.url, s.reference || word(source.title), "text-link under") : "") +
      "</div></div>";
  }).join("");
  const walkthrough = readable(l)
    ? '<section class="reader-block"><h2>' + tr("逐步拆解", "Step by step") + "</h2>" + progressBar(l) +
      steps + "</section>"
    : '<section class="reader-block"><p>' +
      tr("这条成绩记录可通过下方来源核查。", "Use the sources below to check this result.") +
      "</p></section>";
  const exercise = readable(l) && (l.takeaway || l.exercise)
    ? '<section class="reader-block"><h2>' + tr("复现实验", "Reproduction exercise") + "</h2><p>" +
      esc(copy(l, "takeaway")) + "</p>" + (l.exercise ? "<p>" + esc(bilingual(l.exercise)) + "</p>" : "") +
      "</section>"
    : "";
  const sources = '<section class="reader-block"><h2>' + tr("来源与代码", "Sources and code") + "</h2>" +
    l.sources.map((s) => external(s.url, word(s.title))).join("") + "</section>";
  const proof = '<aside class="panel">' + panelTitle("award", tr("榜单凭据", "Leaderboard evidence")) +
    metricList([
      [tr("榜单", "Leaderboard"), e.kind === "final" ? tr("最终榜", "Final") : tr("公开榜", "Public")],
      [tr("名次 / 队伍数", "Rank / teams"), e.rank + " / " + e.teams],
      [tr("分数", "Score"), e.score || "—"],
      [tr("核验日期", "Verified"), fullDate(e.checked)],
    ]) + "</aside>";
  const note = '<aside class="panel"><h2><label for="note">' + tr("我的笔记", "My notes") +
    '</label></h2><textarea id="note" placeholder="' +
    tr("记下想复现的设置或实验结果…", "Record settings or experiment results…") + '">' + esc(r.note || "") +
    '</textarea><p class="notes-status" id="note-status" aria-live="polite">' +
    tr("笔记保存在当前浏览器", "Notes are stored in this browser") + "</p></aside>";
  return top + '<div class="reader-layout"><div class="flow">' + intro + walkthrough + exercise + sources +
    '</div><div class="side-stack">' + proof + note + "</div></div>";
}
const topicFamilies = [
  ["birdclef", "birdcall"],
  ["molecule-id-mass-spectra", "bms-molecular-translation", "champs-scalar-coupling"],
  ["squares-in-squares", "santa-2025"],
  ["nfl-big-data-bowl"],
  ["house-prices", "home-data-for-ml-course"],
  ["connectx", "lux-ai", "ptcg-ai-battle"],
  ["name-that-llm", "llm-classification-finetuning"],
  ["gemma-4-developer-agent"],
  ["arc-prize"],
];
function related(c) {
  const families = topicFamilies.filter((list) => list.some((s) => c.id.toLowerCase().includes(s)));
  return data.competitions.filter((candidate) => candidate.id !== c.id).map((candidate) => {
    const subject = families.filter((list) =>
      list.some((s) => candidate.id.toLowerCase().includes(s))
    ).length;
    const category =
      candidate.categories.filter((key) => key !== "其他" && c.categories.includes(key)).length;
    return { candidate, score: subject * 10 + category };
  }).filter((row) => row.score).sort((a, b) =>
    b.score - a.score || b.candidate.start.localeCompare(a.candidate.start)
  ).map((row) => row.candidate);
}
function competitionView(c) {
  const follow = !!model.following[c.id];
  const top = crumb("competitions", tr("竞赛详情", "Competition details")) +
    '<header class="reader-top"><span class="badge">' + icon("calendar") + esc(timeLeft(c)) +
    '</span><h1 class="detail-title">' + esc(c.title) + '</h1><p class="sub">' + esc(copy(c, "summary")) +
    "</p></header>";
  const details = '<section class="reader-block"><h2>' + tr("竞赛导读", "Competition guide") + "</h2>" +
    (c.guide ? "<p>" + esc(bilingual(c.guide)) + "</p>" : "") + '<div class="actions">' +
    action(
      "follow",
      follow ? tr("已关注", "Following") : tr("关注竞赛", "Follow competition"),
      follow,
      "flag",
    ) + external(c.url, tr("在 Kaggle 查看", "View on Kaggle"), "secondary") + "</div></section>";
  const own = data.lessons.filter((l) => l.competitionID === c.id && !l.stale).sort((a, b) =>
    Number(readable(b)) - Number(readable(a)) || byPublished(a, b)
  );
  const row = (l) => link("lesson", l.id, copy(l, "title"), "rel-link");
  const solutions = '<section class="reader-block"><h2>' + tr("方案与成绩记录", "Solutions and results") +
    "</h2>" +
    (own.map(row).join("") ||
      '<p class="meta">' +
        tr(
          "目前还没有收录这场比赛的公开方案。",
          "No public solutions have been collected for this competition yet.",
        ) + "</p>") +
    "</section>";
  const similar = related(c);
  const ids = new Set([c.id, ...similar.map((v) => v.id)]);
  const comparisons = (data.comparisons || []).filter((v) =>
    v.lessonIDs.every((id) =>
      lessons.has(id) && readable(lessons.get(id)) && ids.has(lessons.get(id).competitionID)
    )
  );
  const knowledge = comparisons.length
    ? '<section class="reader-block"><h2>' + tr("同领域方案对照", "Compare related methods") + "</h2>" +
      comparisons.map((v) =>
        '<div class="shelf-group"><h3>' + esc(word(v.topic)) + "</h3><p>" + esc(copy(v, "text")) + "</p>" +
        v.lessonIDs.map((id) => row(lessons.get(id))).join("") + "</div>"
      ).join("") + "</section>"
    : "";
  const schedule = '<aside class="panel">' + panelTitle("calendar", tr("赛程与指标", "Schedule and metric")) +
    metricList([[tr("开赛", "Opened"), fullDate(c.start)], [tr("截止", "Deadline"), fullDate(c.deadline)], [
      tr("任务类型", "Task type"),
      c.categories.map(word).join(" / "),
    ], [tr("评估指标", "Metric"), c.metric || "—"]]) + "</aside>";
  const relatedPanel = similar.length
    ? '<aside class="panel">' + panelTitle("layers", tr("同领域竞赛", "Related competitions")) +
      similar.map((item) => link("competition", item.id, item.title, "rel-link")).join("") + "</aside>"
    : "";
  return top + '<div class="reader-layout"><div class="flow">' + details + solutions + knowledge +
    '</div><div class="side-stack">' + schedule + relatedPanel + "</div></div>";
}
function calendarKey(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}
function streak() {
  const cursor = new Date();
  const previousDay = () => cursor.setDate(cursor.getDate() - 1);
  if (!model.days[calendarKey(cursor)]) previousDay();
  let count = 0;
  while (model.days[calendarKey(cursor)]) {
    count++;
    previousDay();
  }
  return count;
}
function dailyPick() {
  const key = calendarKey();
  const available = data.lessons.filter((l) =>
    readable(l) && (!finished(l) || record(l.id).finishedDay === key)
  ).sort((a, b) => a.id.localeCompare(b.id));
  const guided = available.filter((l) => l.exercise);
  const pool = guided.length ? guided : available;
  let hash = 5381;
  for (const character of key) hash = (hash * 33 ^ character.charCodeAt(0)) >>> 0;
  return pool.length ? pool[hash % pool.length] : undefined;
}
function studyView() {
  const recent = data.lessons.filter((l) => readable(l) && record(l.id).opened).sort((a, b) =>
    record(b.id).opened - record(a.id).opened
  );
  const lists = {
    reading: [tr("继续阅读", "Continue reading"), recent.filter((l) => !finished(l))],
    saved: [tr("已收藏", "Saved"), data.lessons.filter((l) => record(l.id).saved).sort(byPublished)],
    done: [tr("已学完", "Completed"), recent.filter(finished)],
    following: [tr("关注的竞赛", "Following"), data.competitions.filter((c) => model.following[c.id])],
  };
  const list = lists[studyFilter];
  const empty = {
    reading: tr("打开一篇方案后，就可以在这里继续阅读。", "Open a walkthrough to return to it here."),
    saved: tr("在方案详情中点「收藏方案」，即可在这里找到它。", "Save a solution to find it here."),
    done: tr(
      "标记一篇方案的全部复现步骤后，它会出现在这里。",
      "Mark all steps in a walkthrough to add it here.",
    ),
    following: tr(
      "打开竞赛详情并点「关注竞赛」，即可在这里查看赛程。",
      "Follow a competition to see its schedule here.",
    ),
  };
  const daily = dailyPick();
  const pick = daily
    ? '<div class="panel daily"><div><span class="badge">' + icon("book") +
      tr("今日一课", "Today’s walkthrough") + "</span><h2>" + esc(copy(daily, "title")) +
      '</h2><p class="meta">' + esc(competitions.get(daily.competitionID).title) + "</p></div>" +
      link("lesson", daily.id, tr("阅读讲解", "Read walkthrough"), "primary") + "</div>"
    : "";
  return heading(
    names().study,
    esc(
      tr(
        "收藏、笔记和复现进度保存在当前浏览器。",
        "Bookmarks, notes and progress are stored in this browser.",
      ),
    ),
    [[streak(), tr("连续学习天数", "Day streak")]],
  ) + pick +
    '<div class="filters">' +
    Object.entries(lists).map(([key, [title, items]]) =>
      chip("study-filter", key, title + " · " + items.length, key === studyFilter)
    ).join("") + "</div>" +
    grid(list[1], studyFilter === "following" ? competitionCard : lessonCard, empty[studyFilter]) +
    (!list[1].length
      ? '<div class="actions" style="margin-top:15px">' + (studyFilter === "following"
        ? link("competitions", null, tr("浏览竞赛", "Browse competitions"), "primary")
        : link("library", null, tr("浏览方案库", "Browse library"), "primary")) +
        "</div>"
      : "");
}
function render() {
  const { page, id } = getRoute();
  chrome(page);
  if (!data) return;
  let view, title = names()[page];
  if (page === "feed") view = feed();
  if (["library", "competitions", "method"].includes(page)) {
    view = collection(page, id);
    title ||= word(id);
  }
  if (page === "study") view = studyView();
  if (page === "lesson" && lessons.has(id)) {
    const l = lessons.get(id);
    view = lessonView(l);
    title = copy(l, "title");
  }
  if (page === "competition" && competitions.has(id)) {
    const c = competitions.get(id);
    view = competitionView(c);
    title = c.title;
  }
  if (!view) {
    title = tr("未找到内容", "Page not found");
    view = blank(title) + "<p>" + link("feed", null, names().feed) + "</p>";
  }
  main.innerHTML = view;
  document.title = title + " · KaggleGoose";
}
function navigate(reset = true) {
  const { page, id } = getRoute();
  if (page === "lesson" && lessons?.has(id) && readable(lessons.get(id))) {
    save((m) => {
      (m.lessons[id] ||= {}).opened = Date.now();
      m.days[calendarKey()] = true;
    });
  }
  if (page === "method") {
    filters.library.search = "";
    filters.library.category = "";
    filters.library.kind = "readable";
  }
  render();
  if (reset) {
    window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }
}
document.querySelector(".skip").addEventListener("click", (event) => {
  event.preventDefault();
  main.focus();
  main.scrollIntoView();
});
document.querySelector("#language").addEventListener("click", () => {
  english = !english;
  try {
    localStorage.setItem("kagglegoose.language", english ? "en" : "zh");
  } catch {}
  if (data) render();
  else loadCatalog();
});
main.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const name = button.dataset.action, value = button.dataset.value;
  const { page, id } = getRoute();
  if (name === "retry") {
    loadCatalog();
    return;
  }
  if (name === "more" || name === "story-filter") {
    if (name === "more") feedLimit += 15;
    else {
      storyFilter = value;
      feedLimit = 10;
    }
    const stream = document.querySelector("#feed-stream");
    const previousLength = stream.querySelectorAll(".story").length;
    stream.innerHTML = feedStream();
    if (name === "more") stream.querySelectorAll(".story")[previousLength]?.focus({ preventScroll: true });
    else stream.querySelector('[aria-pressed="true"]').focus({ preventScroll: true });
    return;
  }
  if (name === "study-filter") studyFilter = value;
  if (page === "competition" && name === "follow") {
    save((m) => {
      if (m.following[id]) delete m.following[id];
      else m.following[id] = true;
    });
  }
  if (page === "lesson" && name === "save") {
    editLesson(id, (r) => {
      r.saved = !r.saved;
    });
  }
  if (page === "lesson" && name === "step") {
    const l = lessons.get(id), s = l?.steps[Number(button.dataset.index)];
    if (!s) return;
    const key = stepKey(l, s);
    editLesson(id, (r) => {
      const keys = new Set(r.steps || []);
      if (keys.has(key)) keys.delete(key);
      else keys.add(key);
      r.steps = [...keys];
      r.finishedDay = l.steps.every((step) => keys.has(stepKey(l, step))) ? calendarKey() : null;
      model.days[calendarKey()] = true;
    });
  }
  const selector = '[data-action="' + name + '"]' +
    (button.dataset.index != null
      ? '[data-index="' + button.dataset.index + '"]'
      : name === "study-filter"
      ? '[aria-pressed="true"]'
      : "");
  render();
  main.querySelector(selector)?.focus({ preventScroll: true });
});
main.addEventListener("input", (event) => {
  const { page, id } = getRoute();
  if (event.target.id === "note" && page === "lesson") {
    const saved = editLesson(id, (r) => {
      r.note = event.target.value;
    });
    document.querySelector("#note-status").textContent = saved
      ? tr("已保存到当前浏览器", "Saved in this browser")
      : tr("浏览器存储不可用，笔记仅在本页保留。", "Storage unavailable. Notes last for this session.");
  }
  if (event.target.id === "search") {
    filters[page === "competitions" ? "competitions" : "library"].search = event.target.value;
    document.querySelector("#results").innerHTML = collectionResults(page, id);
  }
});
main.addEventListener("change", (event) => {
  if (!event.target.dataset.select) return;
  const { page, id } = getRoute();
  filters[page === "competitions" ? "competitions" : "library"][event.target.dataset.select] =
    event.target.value;
  document.querySelector("#results").innerHTML = collectionResults(page, id);
});
window.addEventListener("hashchange", () => navigate());
window.addEventListener("storage", (event) => {
  if (event.key === dbKey) {
    model = readModel();
    if (document.activeElement?.id !== "note") render();
  }
});
async function loadCatalog() {
  chrome(getRoute().page);
  main.innerHTML = '<p role="status">' + tr("正在载入竞赛目录…", "Loading the catalog…") + "</p>";
  try {
    const response = await fetch("./v1/catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("Catalog unavailable");
    const value = await response.json();
    if (value.version !== 1 || !Array.isArray(value.lessons) || !Array.isArray(value.competitions)) {
      throw new Error("Unknown catalog");
    }
    competitions = new Map(value.competitions.map((c) => [c.id, c]));
    value.lessons = value.lessons.filter((l) => competitions.has(l.competitionID));
    lessons = new Map(value.lessons.map((l) => [l.id, l]));
    data = value;
    navigate(false);
  } catch {
    main.innerHTML = blank(
      tr(
        "暂时无法载入竞赛目录，请检查网络后重试。",
        "The catalog could not be loaded. Check your connection and retry.",
      ),
    ) + '<button class="primary" data-action="retry">' + tr("重新载入", "Retry") + "</button>";
  }
}
loadCatalog();
