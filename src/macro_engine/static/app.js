const horizonNames = {
  structural: ["Long term", "6–18 months · policy & regime"],
  intermediate: ["Medium term", "1–6 months · data momentum"],
  tactical: ["Short term", "2–8 weeks · catalysts & flows"]
};

const pretty = value => value.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const signed = value => `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
const scoreColor = value => value >= 0 ? "var(--green)" : "var(--red)";

function horizonCard(horizon, labels) {
  const [title, subtitle] = horizonNames[horizon.horizon];
  const active = horizon.factors.filter(f => f.confidence > 0);
  const drivers = [...active]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 3);
  const needle = Math.max(-80, Math.min(80, horizon.score * .8));
  return `<article class="horizon-card">
    <div class="card-top"><div><h2>${title}</h2><p>${subtitle}</p></div>
      <span class="score-tag" style="color:${scoreColor(horizon.score)}">${signed(horizon.score)}</span></div>
    <div class="gauge"><div class="gauge-track"></div><div class="needle" style="--needle:${needle}deg"></div>
      <div class="gauge-labels"><span>BEAR</span><span>BULL</span></div></div>
    <div class="direction" style="color:${scoreColor(horizon.score)}">${pretty(horizon.direction)}</div>
    <div class="card-confidence">confidence ${Math.round(horizon.confidence * 100)}% · ${active.length}/${horizon.factors.length} active factors</div>
    <div class="driver-list"><span>TOP DRIVERS</span>
      ${drivers.length ? drivers.map(f => `<div class="driver"><b>${labels[f.factor] || pretty(f.factor)}</b><em style="color:${scoreColor(f.score)}">${f.score >= 0 ? "▲" : "▼"} ${signed(f.score)}</em></div>`).join("") : '<div class="empty-state">No evidence for this horizon</div>'}
    </div></article>`;
}

function render(data) {
  const { assessment, asset, factors, evidence, data_status: dataStatus } = data;
  const labels = Object.fromEntries(factors.map(f => [f.id, f.label]));
  document.querySelector("#asset-chip").textContent = asset.id.replace("USD", " · USD");
  document.querySelector("#summary").textContent = assessment.horizons.map(h => `${horizonNames[h.horizon][0]} ${pretty(h.direction).toLowerCase()}`).join(" · ");
  document.querySelector("#overall-score").textContent = signed(assessment.overall_score);
  document.querySelector("#overall-direction").textContent = pretty(assessment.direction).toUpperCase();
  document.querySelector("#overall-direction").style.color = scoreColor(assessment.overall_score);
  document.querySelector(".score-orbit").style.setProperty("--score-angle", `${Math.max(0, Math.min(360, (assessment.overall_score + 100) * 1.8))}deg`);
  document.querySelector("#generated").textContent = `GENERATED ${new Date(assessment.generated_at).toLocaleString()}`;
  document.querySelector("#pack-version").textContent = `ASSET PACK v${assessment.pack_version}`;
  const dataMode = document.querySelector("#data-mode");
  const isSample = dataStatus.mode === "sample";
  dataMode.classList.toggle("sample", isSample || dataStatus.mode === "live-partial");
  dataMode.innerHTML = `<span></span>${isSample ? "SAMPLE DATA" : dataStatus.mode === "live-partial" ? "LIVE · PARTIAL" : "LIVE DATA"}`;
  const errors = (dataStatus.errors || []).join(" | ");
  dataMode.title = `${dataStatus.message}${errors ? ` · ${errors}` : ""}`;
  document.querySelector("#horizon-grid").innerHTML = assessment.horizons.map(h => horizonCard(h, labels)).join("");
  document.querySelector("#thesis").textContent = assessment.narrative;
  document.querySelector("#confidence").textContent = `${Math.round(assessment.overall_confidence * 100)}%`;
  document.querySelector("#confidence-bar").style.width = `${assessment.overall_confidence * 100}%`;
  document.querySelector("#contradictions").innerHTML = assessment.contradictions.length
    ? assessment.contradictions.map(c => `<div class="conflict-item">${c}</div>`).join("")
    : '<div class="empty-state">No material contradictions detected.</div>';

  const latestByFactor = Object.fromEntries(evidence.map(e => [e.factor, e]));
  const factorResults = assessment.horizons.flatMap(h => h.factors);
  document.querySelector("#factor-list").innerHTML = factors.map(config => {
    const results = factorResults.filter(r => r.factor === config.id && r.confidence > 0);
    const score = results.length ? results.reduce((sum, r) => sum + r.score, 0) / results.length : 0;
    const item = latestByFactor[config.id];
    const width = Math.min(50, Math.abs(score) / 2);
    const positive = score >= 0;
    return `<div class="factor-row">
      <div class="factor-name"><strong>${config.label}</strong><small>${pretty(config.category)} · half-life ${config.decay_half_life_days}d</small></div>
      <div class="factor-bar"><span style="--width:${width}%;--left:${positive ? 50 : 50 - width}%;--bar-color:${scoreColor(score)}"></span></div>
      <div class="factor-value" style="--bar-color:${scoreColor(score)}">${item ? signed(score) : "NO DATA"}</div>
      ${item ? `<div class="factor-note">${item.summary} · ${new Date(item.observed_at).toLocaleDateString()}</div>` : ""}
    </div>`;
  }).join("");
}

async function load(force = false) {
  const button = document.querySelector("#refresh");
  const error = document.querySelector("#error");
  button.disabled = true;
  button.textContent = "↻ LOADING";
  error.style.display = "none";
  try {
    const response = await fetch(`/api/assessment${force ? "?refresh=1" : ""}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    render(data);
  } catch (err) {
    error.textContent = `Dashboard could not load: ${err.message}`;
    error.style.display = "block";
  } finally {
    button.disabled = false;
    button.textContent = "↻ REFRESH";
  }
}

document.querySelector("#refresh").addEventListener("click", () => load(true));
load();
