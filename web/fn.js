async function boot() {
  try {
    await loadData();
  } catch (e) {
    const err = $("#fn-error");
    err.hidden = false;
    err.innerHTML = `Could not load <code>data.json</code>. Run <code>python3 scripts/build_leaderboard.py</code> first.`;
    return;
  }
  meta();
  const id = new URLSearchParams(location.search).get("id");
  const f = DATA.functions.find((x) => x.key === id);
  const err = $("#fn-error");
  if (!f) {
    err.hidden = false;
    err.innerHTML = id
      ? `No function with id <code>${esc(id)}</code> in this build. <a href="./">Back to the leaderboard.</a>`
      : `Missing <code>?id=…</code>. <a href="./">Back to the leaderboard.</a>`;
    return;
  }
  document.title = `${f.qualname} — Rashomon`;
  $("#fn-title").innerHTML = `${esc(f.qualname)}${f.label ? `<span class="chip ${chipClass(f.label)}">${esc(f.label)}</span>` : ""}`;
  const body = $("#fn-body");
  body.hidden = false;
  body.insertAdjacentHTML("beforeend", detailHTML(f));
  bindGuesses(body, f);
}

boot();
