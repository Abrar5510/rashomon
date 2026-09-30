async function boot() {
  try {
    await loadData();
  } catch (e) {
    const err = $("#fn-error");
    err.hidden = false;
    err.innerHTML = `<div class="empty-state">
      <div class="empty-icon">⚠️</div>
      <h3>Could not load data</h3>
      <p>This is a live demo of the Rashomon pipeline. The leaderboard shows 30 functions from the <code>boltons</code> library analyzed by 5 independent Gemini readers.</p>
      <p>To run locally: <code>python3 scripts/build_leaderboard.py</code> then <code>npx serve web</code></p>
    </div>`;
    return;
  }
  meta();
  const id = new URLSearchParams(location.search).get("id");
  const f = DATA.functions.find((x) => x.key === id);
  const err = $("#fn-error");
  if (!f) {
    err.hidden = false;
    err.innerHTML = id
      ? `<div class="empty-state">
           <div class="empty-icon">🔍</div>
           <h3>Function not found</h3>
           <p>No function with id <code>${esc(id)}</code> in this build.</p>
           <p><a href="./" class="link-btn">← Back to the leaderboard</a></p>
         </div>`
      : `<div class="empty-state">
           <div class="empty-icon">🔍</div>
           <h3>Missing function ID</h3>
           <p>Missing <code>?id=…</code> parameter.</p>
           <p><a href="./" class="link-btn">← Back to the leaderboard</a></p>
         </div>`;
    return;
  }
  document.title = `${f.qualname} — Rashomon`;
  $("#fn-title").innerHTML = `${esc(f.qualname)}${f.label ? `<span class="chip ${chipClass(f.label)}">${esc(f.label)}</span>` : ""}`;
  const body = $("#fn-body");
  body.hidden = false;
  
  // Use enhanced detailHTML with card legend
  const probes = f.probes.map((p, i) => probeSectionHTML(f, p, i)).join("");
  const summaries = [...new Set(f.probes.flatMap((p) => p.cards.map((c) => c.summary).filter(Boolean)))]
    .map((s) => `<li>${esc(s)}</li>`)
    .join("");
  const fixes = (f.history?.fix_commits || [])
    .map((c) => `<li><span class="mono">${esc(c.sha)}</span> ${esc(c.subject)}</li>`)
    .join("");
    
  body.insertAdjacentHTML("beforeend", `
    <div class="sub">${esc(f.path)} · ${f.misreads}/${f.predictions} predictions wrong · 95% CI ${(f.ci_lo * 100).toFixed(0)}–${(f.ci_hi * 100).toFixed(0)}% · ${esc(f.label || "")} · ${f.witnesses_correct}/${f.n_witnesses} readers clean</div>
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
  `);
  bindGuesses(body, f);
}

boot();
