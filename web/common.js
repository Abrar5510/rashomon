/* Shared by index.html (app.js) and fn.html (fn.js): load, render, guess. */
"use strict";

let DATA = null;

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&", "<": "<", ">": ">", '"': """ }[c]));

const CHIP_CLASS = { "Clear": "good", "Scattered": "muted", "Confusing": "bad", "Consensus misread": "bad" };
const chipClass = (label) => CHIP_CLASS[label] || "muted";

/* Metric explanations for tooltips */
const METRIC_EXPLANATIONS = {
  "misread-rate": "Percentage of predictions that were wrong. Abstentions (empty guesses) count as wrong.",
  "ci": "Wilson score interval (95% confidence). If the lower bound exceeds 20%, the function is statistically confusing.",
  "disagreement": "Average number of distinct answers per probe. Higher means the 5 readers disagreed more.",
  "clean": "Number of readers who got EVERY probe right (out of 5 total readers).",
  "bugfixes": "Git commits whose subject matches fix/bug/patch/resolve and whose diff actually changed this function."
};

function getMetricExplanation(key) {
  return METRIC_EXPLANATIONS[key] || "";
}

function meta() {
  if (!DATA || !$("#meta")) return;
  const f = DATA.functions;
  const misread = f.reduce((s, x) => s + x.misreads, 0);
  const preds = f.reduce((s, x) => s + x.predictions, 0);
  const session =
    DATA.session === "recorded"
      ? " · RECORDED witness session (offline replay, not a live model run)"
      : DATA.session === "live"
      ? " · live witness run"
      : "";
  $("#meta").textContent =
    `${DATA.n_functions} functions · ${preds} predictions by ${DATA.personas.length} independent readers · ` +
    `${misread} wrong (${preds ? Math.round((misread / preds) * 100) : 0}%) · generated ${DATA.generated_at}${session}`;
  if ($("#foot")) {
    $("#foot").textContent =
      `${DATA.tool}. Bug fixes come from git history: commits whose subject matches fix/bug/patch/resolve ` +
      `and whose diff actually changed that function.`;
  }
}

async function loadData() {
  const res = await fetch("./data.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  DATA = await res.json();
  return DATA;
}

function argText(p) {
  const args = JSON.stringify(p.input?.args ?? []);
  const kw = p.input?.kwargs || {};
  return Object.keys(kw).length ? `${args} **${JSON.stringify(kw)}` : args;
}

/* ---- guessing: mirror rashomon.score.same in the browser ---- */

function pyParse(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return { empty: true };
  let i = 0;
  const ws = () => {
    while (i < s.length && " \t\n\r".includes(s[i])) i++;
  };
  const peek = () => {
    ws();
    return s[i];
  };
  const fail = () => {
    throw new SyntaxError("not a python literal");
  };
  const word = (w) => {
    if (s.startsWith(w, i) && !/[\w]/.test(s[i + w.length] ?? "")) {
      i += w.length;
      return true;
    }
    return false;
  };
  const HEX = "0123456789abcdefABCDEF";

  function parseStr() {
    const q = s[i++];
    let out = "";
    while (i < s.length && s[i] !== q) {
      if (s[i] === "\\") {
        i++;
        const e = s[i++];
        if (e === "n") out += "\n";
        else if (e === "t") out += "\t";
        else if (e === "r") out += "\r";
        else if (e === "0") out += "\0";
        else if (e === "x") {
          const h = s.slice(i, i + 2);
          if (h.length < 2 || ![...h].every((c) => HEX.includes(c))) fail();
          out += String.fromCharCode(parseInt(h, 16));
          i += 2;
        } else if (e === "u") {
          const h = s.slice(i, i + 4);
          if (h.length < 4 || ![...h].every((c) => HEX.includes(c))) fail();
          out += String.fromCharCode(parseInt(h, 16));
          i += 4;
        } else if (e === "\n") {
        } else out += e;
      } else out += s[i++];
    }
    if (s[i] !== q) fail();
    i++;
    return { t: "str", v: out };
  }

  function parseNum() {
    const m = /^[-+]?(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][-+]?\d[\d_]*)?/.exec(s.slice(i));
    if (!m || !m[0]) fail();
    const t = m[0];
    i += t.length;
    const clean = t.replace(/_/g, "");
    return /[.eE]/.test(clean) ? { t: "float", v: parseFloat(clean) } : { t: "int", v: parseInt(clean, 10) };
  }

  function parseSeq(close, allowTuple) {
    const items = [];
    let sawComma = false;
    for (;;) {
      const c = peek();
      if (c === close) {
        i++;
        break;
      }
      if (c === undefined) fail();
      items.push(parseValue());
      if (peek() === ",") {
        i++;
        sawComma = true;
      } else if (peek() === close) {
        i++;
        break;
      } else fail();
    }
    if (!allowTuple) return { t: "list", v: items };
    if (items.length === 1 && !sawComma) return items[0];
    return { t: "tuple", v: items };
  }

  function parseBrace() {
    if (peek() === "}") {
      i++;
      return { t: "dict", v: [] };
    }
    const first = parseValue();
    if (peek() === ":") {
      i++;
      const pairs = [[first, parseValue()]];
      for (;;) {
        if (peek() === ",") i++;
        if (peek() === "}") {
          i++;
          break;
        }
        const k = parseValue();
        if (peek() !== ":") fail();
        i++;
        pairs.push([k, parseValue()]);
      }
      return { t: "dict", v: pairs };
    }
    const vals = [first];
    for (;;) {
      if (peek() === ",") i++;
      if (peek() === "}") {
        i++;
        break;
      }
      vals.push(parseValue());
    }
    return { t: "set", v: vals };
  }

  function parseValue() {
    const c = peek();
    if (c === undefined) fail();
    if (c === "'" || c === '"') return parseStr();
    if (c === "[") {
      i++;
      return parseSeq("]", false);
    }
    if (c === "(") {
      i++;
      return parseSeq(")", true);
    }
    if (c === "{") {
      i++;
      return parseBrace();
    }
    if (word("True")) return { t: "bool", v: true };
    if (word("False")) return { t: "bool", v: false };
    if (word("None")) return { t: "none" };
    return parseNum();
  }

  try {
    const v = parseValue();
    ws();
    if (i < s.length) return null;
    return { v };
  } catch (e) {
    return null;
  }
}

function litEq(a, b) {
  if (a.t === "bool" || b.t === "bool") return a.t === b.t && a.v === b.v;
  if ((a.t === "int" || a.t === "float") && (b.t === "int" || b.t === "float")) return a.v === b.v;
  if (a.t !== b.t) return false;
  if (a.t === "none") return true;
  if (a.t === "str") return a.v === b.v;
  if (a.t === "list" || a.t === "tuple")
    return a.v.length === b.v.length && a.v.every((x, j) => litEq(x, b.v[j]));
  if (a.t === "set") {
    if (a.v.length !== b.v.length) return false;
    const used = b.v.map(() => false);
    return a.v.every((x) => {
      const j = b.v.findIndex((y, idx) => !used[idx] && litEq(x, y));
      if (j < 0) return false;
      used[j] = true;
      return true;
    });
  }
  if (a.t === "dict") {
    if (a.v.length !== b.v.length) return false;
    const used = b.v.map(() => false);
    return a.v.every(([k, v]) => {
      const j = b.v.findIndex(([k2, v2], idx) => !used[idx] && litEq(k, k2) && litEq(v, v2));
      if (j < 0) return false;
      used[j] = true;
      return true;
    });
  }
  return false;
}

function pyRepr(x) {
  switch (x.t) {
    case "none":
      return "None";
    case "bool":
      return x.v ? "True" : "False";
    case "int":
      return String(x.v);
    case "float":
      return Number.isInteger(x.v) && Number.isFinite(x.v) ? `${x.v}.0` : String(x.v);
    case "str": {
      const q = x.v.includes("'") && !x.v.includes('"') ? '"' : "'";
      let out = "";
      for (const ch of x.v) {
        if (ch === "\\") out += "\\\\";
        else if (ch === q) out += "\\" + q;
        else if (ch === "\n") out += "\\n";
        else if (ch === "\t") out += "\\t";
        else if (ch === "\r") out += "\\r";
        else out += ch;
      }
      return q + out + q;
    }
    case "list":
      return `[${x.v.map(pyRepr).join(", ")}]`;
    case "set":
      return `{${x.v.map(pyRepr).join(", ")}}`;
    case "tuple":
      return x.v.length === 1 ? `(${pyRepr(x.v[0])},)` : `(${x.v.map(pyRepr).join(", ")})`;
    case "dict":
      return `{${x.v.map(([k, v]) => `${pyRepr(k)}: ${pyRepr(v)}`).join(", ")}}`;
    default:
      return String(x.v);
  }
}

function sameAnswer(guess, actual) {
  const g = String(guess ?? "").trim();
  const a = String(actual ?? "").trim();
  if (!g || !a) return false;
  const pa = pyParse(g);
  const pb = pyParse(a);
  if (pa?.empty || pb?.empty) return false;
  const aHas = pa && pa.v;
  const bHas = pb && pb.v;
  if (aHas && bHas) return litEq(pa.v, pb.v);
  const norm = (s) => s.replace(/\s+/g, " ").trim();
  if (aHas) return pyRepr(pa.v) === norm(a);
  if (bHas) return pyRepr(pb.v) === norm(g);
  return norm(g) === norm(a);
}

/* ---- detail render (drawer on index, whole page on fn.html) ---- */

function probeSectionHTML(f, p, i) {
  const cards = p.cards
    .map(
      (c, j) => `
    <div class="card ${c.correct ? "ok" : "no"}" style="--d:${(i * 5 + j) * 55}ms">
      <div class="face back"><span class="who">${esc(c.witness)}</span><span class="hint">reader has not spoken</span></div>
      <div class="face front">
        <span class="who">${esc(c.witness)}</span>
        <span class="val">${esc(c.prediction || "(no answer)")}</span>
        <span class="verdict">${c.correct ? "MATCHES THE RUN" : "MISREAD"}</span>
      </div>
    </div>`
    )
    .join("");
  const distinct = new Set(p.cards.map((c) => c.prediction)).size;
  return `
  <section class="probe" data-probe="${i}">
    <div class="probe-head">
      <div class="input mono">${esc(f.qualname.split(".").pop())}(${esc(argText(p))})</div>
      <span class="metric">${p.distinct_answers || distinct} distinct answers</span>
    </div>
    <div class="guess">
      <input class="guess-input mono" type="text" spellcheck="false"
        placeholder="your prediction — a Python literal, e.g. 5400 or 'abc'" aria-label="your prediction" />
      <button class="guess-btn" type="button">check</button>
      <span class="guess-result" hidden></span>
    </div>
    <div class="reveal" hidden><span class="actual mono"> → ${esc(p.actual)}</span></div>
    <div class="cards">${cards}</div>
  </section>`;
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
    <div class="sub">${esc(f.path)} · ${f.misreads}/${f.predictions} predictions wrong · 95% CI ${(f.ci_lo * 100).toFixed(0)}–${(f.ci_hi * 100).toFixed(0)}% · ${esc(f.label || "")} · ${f.witnesses_correct}/${f.n_witnesses} readers clean</div>
    <div class="sixth" id="sixth" hidden></div>
    <pre>${esc(f.source)}</pre>
    <p class="guess-lead">Be the 6th witness: predict what the interpreter returns before you look.
      The five cards flip only after you check — an empty guess counts as an abstention, and abstentions count as misreads.</p>
    ${probes}
    <h4 class="detail-h">What the readers said it did</h4>
    <ul class="summary">${summaries || "<li>(none recorded)</li>"}</ul>
    <h4 class="detail-h">Bug-fix history (${f.history?.bug_fixes || 0})</h4>
    <ul class="summary">${fixes || "<li>no fix commits touch this function</li>"}</ul>
    <a class="share" href="./fn.html?id=${encodeURIComponent(f.key)}">shareable page for this function ↗</a>`;
}

function flipCards(scope, baseDelay = 120) {
  scope.querySelectorAll(".card").forEach((c) => {
    if (c.classList.contains("flip")) return;
    const d = Number.parseInt(c.style.getPropertyValue("--d"), 10) || 0;
    setTimeout(() => c.classList.add("flip"), baseDelay + d);
  });
}

function bindGuesses(root, f) {
  const tally = { checked: 0, right: 0 };
  const sixth = root.querySelector("#sixth");
  root.querySelectorAll(".probe").forEach((sec) => {
    const i = Number(sec.dataset.probe);
    const p = f.probes[i];
    if (!p) return;
    const input = sec.querySelector(".guess-input");
    const btn = sec.querySelector(".guess-btn");
    const out = sec.querySelector(".guess-result");
    const reveal = sec.querySelector(".reveal");
    const done = () => {
      if (sec.dataset.done) return;
      sec.dataset.done = "1";
      const guess = input.value;
      const right = sameAnswer(guess, p.actual);
      tally.checked += 1;
      if (right) tally.right += 1;
      out.hidden = false;
      out.className = "guess-result " + (right ? "ok" : "no");
      out.textContent = !guess.trim()
        ? "abstention — unanswered predictions count as misreads"
        : right
        ? "you matched the run"
        : "you misread it";
      reveal.hidden = false;
      sec.classList.add("revealed");
      flipCards(sec);
      if (sixth) {
        sixth.hidden = false;
        sixth.textContent = `you are the 6th witness · ${tally.right}/${tally.checked} right`;
      }
    };
    btn.addEventListener("click", done);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") done();
    });
  });
}
