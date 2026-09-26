let sortKey = "misread_rate";
let query = "";

const SORTERS = {
  misread_rate: (a, b) => b.misread_rate - a.misread_rate || b.disagreement_max - a.disagreement_max,
  disagreement_mean: (a, b) => b.disagreement_mean - a.disagreement_mean || b.misread_rate - a.misread_rate,
  bug_fixes: (a, b) => (b.history?.bug_fixes || 0) - (a.history?.bug_fixes || 0) || b.misread_rate - a.misread_rate,
  key: (a, b) => a.qualname.localeCompare(b.qualname),
};

function visible() {
  const q = query.trim().toLowerCase();
  return DATA.functions
    .filter((f) => !q || f.qualname.toLowerCase().includes(q) || f.path.toLowerCase().includes(q))
    .slice()
    .sort(SORTERS[sortKey]);
}

function renderList() {
  const rows = visible();
  $("#empty").hidden = rows.length > 0;
  $("#list").innerHTML = rows
    .map((f) => {
      const pct = Math.round(f.misread_rate * 100);
      const cleanCls = f.witnesses_correct <= 1 ? "bad" : f.witnesses_correct >= 5 ? "good" : "";
      const chipCls = chipClass(f.label);
      return `
      <article class="row" data-key="${esc(f.key)}" tabindex="0" role="button" aria-label="open witness cards for ${esc(f.qualname)}">
        <div class="rank">${f.rank}</div>
        <div class="name">${esc(f.qualname)}${f.label ? `<span class="chip ${chipCls}">${esc(f.label)}</span>` : ""}<span class="file">${esc(f.path)} · ${f.n_lines} lines · ${f.history?.bug_fixes || 0} bug-fix commits</span></div>
        <div class="bar" title="${pct}% of predictions wrong, 95% CI ${(f.ci_lo * 100 || 0).toFixed(0)}–${(f.ci_hi * 100 || 0).toFixed(0)}%"><i style="width:${pct}%"></i><span>${f.misreads}/${f.predictions}</span></div>
        <div class="metric ${cleanCls}"><b>${f.witnesses_correct}/${f.n_witnesses}</b> clean</div>
        <div class="metric"><b>${f.disagreement_mean.toFixed(2)}</b> distinct</div>
      </article>`;
    })
    .join("");
  document.querySelectorAll(".row").forEach((el) => {
    el.addEventListener("click", () => openDrawer(el.dataset.key));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") openDrawer(el.dataset.key); });
  });
}

function openDrawer(key) {
  const f = DATA.functions.find((x) => x.key === key);
  if (!f) return;
  $("#drawer").innerHTML = `
    <button class="close" id="close" aria-label="close">✕</button>
    <h3>${esc(f.qualname)}</h3>
    ${detailHTML(f)}`;
  $("#drawer").hidden = false;
  $("#backdrop").hidden = false;
  $("#close").addEventListener("click", closeDrawer);
  bindGuesses($("#drawer"), f);
}

function closeDrawer() {
  $("#drawer").hidden = true;
  $("#backdrop").hidden = true;
}

function renderChart() {
  const f = DATA.functions;
  const W = 1000, H = 200, pad = 42;
  const maxX = Math.max(0.1, ...f.map((d) => d.misread_rate));
  const maxY = Math.max(1, ...f.map((d) => d.history?.bug_fixes || 0));
  const x = (v) => pad + (v / maxX) * (W - pad * 2);
  const y = (v) => H - pad - (v / maxY) * (H - pad * 1.6);
  const pts = f
    .map(
      (d) => `
      <g>
        <circle cx="${x(d.misread_rate)}" cy="${y(d.history?.bug_fixes || 0)}" r="7"
          fill="rgba(124,156,255,.75)" stroke="#0b0d12" stroke-width="2"><title>${esc(d.qualname)}: ${(d.misread_rate * 100).toFixed(0)}% misread, ${d.history?.bug_fixes || 0} fixes</title></circle>
        <text x="${x(d.misread_rate) + 11}" y="${y(d.history?.bug_fixes || 0) + 4}" font-size="11" fill="#8b93a7">${esc(d.qualname)}</text>
      </g>`
    )
    .join("");
  $("#chart").innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="misread rate versus bug-fix count">
      <line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="#262c3d"/>
      <line x1="${pad}" y1="${pad / 2}" x2="${W - pad}" y2="${pad / 2}" stroke="#262c3d"/>
      <text x="${W - pad}" y="${H - pad + 26}" text-anchor="end" font-size="11" fill="#8b93a7">misread rate →</text>
      <text x="${pad - 8}" y="${pad / 2 + 4}" text-anchor="end" font-size="11" fill="#8b93a7">↑ fixes</text>
      <text x="${pad}" y="${H - pad + 26}" font-size="11" fill="#59617a">0%</text>
      <text x="${W - pad}" y="${H - pad + 26}" font-size="11" fill="#59617a" opacity="0">${Math.round(maxX * 100)}%</text>
      ${pts}
    </svg>`;

  const n = f.length;
  const sx = f.map((d) => d.misread_rate);
  const sy = f.map((d) => d.history?.bug_fixes || 0);
  const mean = (a) => a.reduce((s, v) => s + v, 0) / (a.length || 1);
  const mx = mean(sx), my = mean(sy);
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (sx[i] - mx) * (sy[i] - my); dx += (sx[i] - mx) ** 2; dy += (sy[i] - my) ** 2; }
  const r = dx && dy ? num / Math.sqrt(dx * dy) : 0;
  $("#corr").textContent =
    `Pearson r = ${r.toFixed(2)} across ${n} functions (n is small — this is a measurement, not a claim).`;
}

async function boot() {
  try {
    await loadData();
  } catch (e) {
    document.querySelector("main").innerHTML =
      `<p class="empty">Could not load <code>data.json</code>. Run <code>python3 scripts/build_leaderboard.py</code> first.</p>`;
    return;
  }
  meta();
  renderChart();
  renderList();
}

$("#search").addEventListener("input", (e) => { query = e.target.value; renderList(); });
$("#sorts").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  sortKey = b.dataset.sort;
  document.querySelectorAll("#sorts button").forEach((x) => x.classList.toggle("on", x === b));
  renderList();
});
$("#backdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

boot();
