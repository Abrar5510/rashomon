let sortKey = "misread_rate";
let query = "";
let tooltipEl = null;

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
  const listEl = $("#list");
  const emptyEl = $("#empty");
  emptyEl.hidden = rows.length > 0;
  listEl.innerHTML = rows
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

function detailHTML(f) {
  const probes = f.probes.map((p, i) => probeSectionHTML(f, p, i)).join("");
  const summaries = [...new Set(f.probes.flatMap((p) => p.cards.map((c) => c.summary).filter(Boolean)))]
    .map((s) => `<li>${esc(s)}</li>`)
    .join("");
  const fixes = (f.history?.fix_commits || [])
    .map((c) => `<li><span class="mono">${esc(c.sha)}</span> ${esc(c.subject)}</li>`)
    .join("");
  return `
    <div class="drawer-header">
      <div class="drawer-title">
        <h3>${esc(f.qualname)}</h3>
        <div class="sub">${esc(f.path)} · ${f.misreads}/${f.predictions} predictions wrong · 95% CI ${(f.ci_lo * 100).toFixed(0)}–${(f.ci_hi * 100).toFixed(0)}% · ${esc(f.label || "")} · ${f.witnesses_correct}/${f.n_witnesses} readers clean</div>
      </div>
      <a class="drawer-share" href="./fn.html?id=${encodeURIComponent(f.key)}" target="_blank" rel="noopener">Shareable page ↗</a>
    </div>
    <pre>${esc(f.source)}</pre>
    <p class="guess-lead">Be the 6th witness: predict what the interpreter returns before you look.
      The five cards flip only after you check — an empty guess counts as an abstention, and abstentions count as misreads.</p>
    <div class="card-legend" aria-label="Card color legend">
      <span class="card-legend-item"><span class="card-legend-swatch ok" aria-hidden="true"></span>Green = matched actual run</span>
      <span class="card-legend-item"><span class="card-legend-swatch no" aria-hidden="true"></span>Red = misread</span>
    </div>
    <h4 class="detail-h">What the 5 readers predicted for this input</h4>
    ${probes}
    <div class="sixth" id="sixth" hidden></div>
    <h4 class="detail-h">What the readers said it did</h4>
    <ul class="summary">${summaries || "<li>(none recorded)</li>"}</ul>
    <h4 class="detail-h">Bug-fix history (${f.history?.bug_fixes || 0})</h4>
    <ul class="summary">${fixes || "<li>no fix commits touch this function</li>"}</ul>
    <a class="share" href="./fn.html?id=${encodeURIComponent(f.key)}">shareable page for this function ↗</a>`;
}

function openDrawer(key) {
  const f = DATA.functions.find((x) => x.key === key);
  if (!f) return;
  $("#drawer").innerHTML = `
    <button class="close" id="close" aria-label="close">✕</button>
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

/* ---- Tooltip System ---- */
function initTooltips() {
  const template = document.getElementById("tooltipTemplate");
  if (!template) return;
  tooltipEl = template.content.firstElementChild.cloneNode(true);
  document.body.appendChild(tooltipEl);

  const tooltipTexts = {
    "misread-rate": "% of predictions that were wrong (abstentions count as wrong)",
    "ci": "Wilson score interval — lower bound >20% means statistically confusing with 95% confidence",
    "disagreement": "Average number of distinct answers per probe — higher = readers disagree more",
    "clean": "Readers who got EVERY probe right (out of 5 total readers)",
    "bugfixes": "Git commits whose subject matches fix/bug/patch/resolve and whose diff actually changed this function"
  };

  document.querySelectorAll("[data-tooltip]").forEach((el) => {
    const key = el.dataset.tooltip;
    const text = tooltipTexts[key] || "";
    el.addEventListener("mouseenter", (e) => showTooltip(el, text));
    el.addEventListener("mouseleave", hideTooltip);
    el.addEventListener("focus", (e) => showTooltip(el, text));
    el.addEventListener("blur", hideTooltip);
  });
}

function showTooltip(target, text) {
  if (!tooltipEl || !text) return;
  tooltipEl.querySelector(".tooltip-content").textContent = text;
  const rect = target.getBoundingClientRect();
  tooltipEl.style.left = `${rect.left + rect.width / 2}px`;
  tooltipEl.style.top = `${rect.top - 8}px`;
  tooltipEl.dataset.placement = "top";
  tooltipEl.classList.add("visible");
}

function hideTooltip() {
  if (tooltipEl) tooltipEl.classList.remove("visible");
}

/* ---- Guided Tour ---- */
const TOUR_STEPS = [
  {
    target: "#list .row:first-child",
    title: "Leaderboard",
    text: "These are functions ranked by how often readers misread them. Higher misread rate = more confusing code."
  },
  {
    target: "#list .row:first-child",
    title: "Click a row",
    text: "Click any row to see the five readers' predictions for that function's test inputs."
  },
  {
    target: ".drawer",
    title: "Witness cards",
    text: "Cards flip after you make your own prediction. Green = matched the actual run, Red = misread."
  },
  {
    target: ".guess-input",
    title: "Be the 6th witness",
    text: "Predict before you look — type a Python literal (e.g., 42, 'hello', [1,2,3]) and hit Check. Empty guess = abstention = misread."
  }
];

function startTour() {
  if (localStorage.getItem("rashomonTourDone") === "true") return;
  let currentStep = 0;
  const overlay = $("#tourOverlay");
  const stepEl = $("#tourStep");
  const titleEl = $("#tourTitle");
  const textEl = $("#tourText");
  const prevBtn = $("#tourPrev");
  const nextBtn = $("#tourNext");
  const doneBtn = $("#tourDone");
  const closeBtn = stepEl.querySelector(".tour-close");

  function showStep(idx) {
    const step = TOUR_STEPS[idx];
    titleEl.textContent = step.title;
    textEl.textContent = step.text;
    prevBtn.hidden = idx === 0;
    nextBtn.hidden = idx === TOUR_STEPS.length - 1;
    doneBtn.hidden = idx !== TOUR_STEPS.length - 1;

    // Remove previous highlight
    document.querySelectorAll(".tour-target").forEach(el => el.classList.remove("tour-target"));

    // Highlight target
    const target = document.querySelector(step.target);
    if (target) {
      target.classList.add("tour-target");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function nextStep() {
    if (currentStep < TOUR_STEPS.length - 1) {
      currentStep++;
      showStep(currentStep);
    }
  }

  function prevStep() {
    if (currentStep > 0) {
      currentStep--;
      showStep(currentStep);
    }
  }

  function finishTour() {
    localStorage.setItem("rashomonTourDone", "true");
    overlay.hidden = true;
    document.querySelectorAll(".tour-target").forEach(el => el.classList.remove("tour-target"));
  }

  nextBtn.addEventListener("click", nextStep);
  prevBtn.addEventListener("click", prevStep);
  doneBtn.addEventListener("click", finishTour);
  closeBtn.addEventListener("click", finishTour);

  overlay.hidden = false;
  showStep(0);
}

async function boot() {
  try {
    await loadData();
  } catch (e) {
    document.querySelector("main").innerHTML =
      `<section class="empty" id="loadError">
         <div class="empty-state">
           <div class="empty-icon">⚠️</div>
           <h3>Could not load data</h3>
           <p>This is a live demo of the Rashomon pipeline. The leaderboard shows 30 functions from the <code>boltons</code> library analyzed by 5 independent Gemini readers.</p>
           <p>To run locally: <code>python3 scripts/build_leaderboard.py</code> then <code>npx serve web</code></p>
         </div>
       </section>`;
    return;
  }
  meta();
  renderChart();
  renderList();
  initTooltips();

  // Hero dismiss
  const hero = $("#hero");
  const heroDismiss = $("#heroDismiss");
  if (heroDismiss) {
    heroDismiss.addEventListener("click", () => {
      hero.classList.add("dismissed");
      localStorage.setItem("rashomonHeroDismissed", "true");
    });
    if (localStorage.getItem("rashomonHeroDismissed") === "true") {
      hero.classList.add("dismissed");
    }
  }

  // Clear search button
  const clearSearch = $("#clearSearch");
  if (clearSearch) {
    clearSearch.addEventListener("click", () => {
      $("#search").value = "";
      query = "";
      renderList();
    });
  }

  // Start tour after a short delay
  setTimeout(startTour, 500);
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
