
function _lucide(){ try{ if(window.lucide) lucide.createIcons(); }catch(e){} }
// HourMatch — emissions map (Leaflet + OpenStreetMap, no API key)

const EMISSION_COLORS = {
  high: "#FF4D3D",
  medium: "#FFB020",
  low: "#2EF2C4",
  clean: "#2EF2C4",
};

let DATA = null;          // loaded from /api/facilities
let map, radiusCircle;
let facilityLayer;        // LayerGroup of all facility markers
let selected = null;      // { lat, lng }

// ---- helpers ---------------------------------------------------------------

// Great-circle distance in km (Haversine).
function distanceKm(a, b) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function levelFor(f) {
  if (f.type === "clean_supply") return "clean";
  const t = DATA.thresholds;
  const tco2e = f.emissions_tco2e;
  if (tco2e <= t.low_max) return "low";
  if (tco2e <= t.medium_max) return "medium";
  return "high";
}

function levelLabel(level) {
  return { high: "High", medium: "Medium", low: "Low", clean: "Clean supply" }[level];
}

// The HourMatch meter block — the one thing that makes this HourMatch.
function meterHtml(f) {
  if (f.type !== "data_center" || f.hourly_match_pct == null) return "";
  return `
    <div class="meter">
      <div class="meter-head">On paper vs. by the hour</div>
      <div class="meter-row">
        <span class="meter-annual">Annual ${f.annual_match_pct}%</span>
        <span class="meter-arrow">→</span>
        <span class="meter-hourly">Hourly ${f.hourly_match_pct}%</span>
      </div>
      <div class="meter-bar"><div class="meter-fill" style="width:${f.hourly_match_pct}%"></div></div>
      <div class="meter-sub">${f.peak_mw} MW · ${f.water_mgal_yr}M gal/yr water (est.)</div>
    </div>`;
}

function fmt(n) {
  return n.toLocaleString("en-US");
}

function markerIcon(level) {
  const color = EMISSION_COLORS[level];
  return L.divIcon({
    className: "",
    html: `<div class="marker-emission" style="width:16px;height:16px;background:${color};color:${color};animation:dcpulse 2.4s ease-in-out infinite"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  });
}

// ---- rendering -------------------------------------------------------------

function popupHtml(f, level) {
  const src = f.source_url
    ? `<a href="${f.source_url}" target="_blank" rel="noopener">source</a>`
    : f.source || "source n/a";
  const typeLabel = f.type === "data_center" ? "Data center"
    : f.type === "clean_supply" ? "Clean supply" : "Industry";
  const value = f.type === "clean_supply"
    ? `<b>${f.mw_operating ?? "?"}</b> MW operating solar`
    : `<span class="pill ${level}">${levelLabel(level)}</span>&nbsp;<b>${fmt(f.emissions_tco2e)}</b> tCO₂e/yr`;
  return `
    <div class="pop-title">${f.name}</div>
    <div class="pop-meta">${typeLabel} · ${f.city}</div>
    <div>${value}</div>
    ${meterHtml(f)}
    <div class="pop-meta" style="margin-top:4px">${src}</div>
  `;
}

function drawAllMarkers() {
  facilityLayer.clearLayers();
  DATA.facilities.forEach((f) => {
    const level = levelFor(f);
    const m = L.marker([f.lat, f.lng], { icon: markerIcon(level) });
    m.bindPopup(popupHtml(f, level));
    m._facility = f;
    facilityLayer.addLayer(m);
  });
}

function renderPanel(center, radiusKm) {
  const titleEl = document.getElementById("panelTitle");
  const subEl = document.getElementById("panelSub");
  const list = document.getElementById("results");
  list.innerHTML = "";

  const nearby = DATA.facilities
    .map((f) => ({ f, d: distanceKm(center, { lat: f.lat, lng: f.lng }) }))
    .filter((x) => x.d <= radiusKm)
    .sort((a, b) => b.f.emissions_tco2e - a.f.emissions_tco2e);

  titleEl.textContent = `${nearby.length} facilit${nearby.length === 1 ? "y" : "ies"} within ${radiusKm} km`;
  subEl.textContent = `Around ${center.lat.toFixed(3)}, ${center.lng.toFixed(3)}`;

  if (nearby.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="muted">No data centers or industries in range. Widen the radius or pick another location.</span>`;
    list.appendChild(li);
    return;
  }

  nearby.forEach(({ f, d }) => {
    const level = levelFor(f);
    const li = document.createElement("li");
    const typeBadge = f.type === "data_center" ? "data center"
      : f.type === "clean_supply" ? "clean supply" : "industry";
    const valueLine = f.type === "clean_supply"
      ? `<div class="value"><b>${f.mw_operating ?? "?"}</b> MW operating solar</div>`
      : `<div class="value"><b>${fmt(f.emissions_tco2e)}</b> tCO₂e / year</div>`;
    const meterLine = (f.type === "data_center" && f.hourly_match_pct != null)
      ? `<div class="meter-inline">Annual <b>${f.annual_match_pct}%</b> → Hourly <b style="color:#e4572e">${f.hourly_match_pct}%</b></div>`
      : "";
    li.innerHTML = `
      <div class="row">
        <span class="pill ${level}">${levelLabel(level)}</span>
        <span class="name">${f.name}</span>
        <span class="badge-type">${typeBadge}</span>
      </div>
      <div class="meta">${f.city} · ${d.toFixed(1)} km away · ${f.status}</div>
      ${meterLine}
      ${valueLine}
    `;
    li.addEventListener("click", () => {
      map.setView([f.lat, f.lng], Math.max(map.getZoom(), 10));
      facilityLayer.eachLayer((m) => {
        if (m._facility === f) m.openPopup();
      });
    });
    list.appendChild(li);
  });
}

function selectLocation(center) {
  selected = center;
  renderHoverReadout(center.lat, center.lng);
  const radiusKm = Number(document.getElementById("radius").value);
  // NOTE: the radius circle is drawn ONLY for a dropped data center (see the
  // drop module), not on every map click — a plain click just reads nearby
  // facilities, it does not place a site.
  renderPanel(center, radiusKm);
}

// ---- controls --------------------------------------------------------------

function populateControls() {
  // Region/Location selectors were removed — the drop-a-data-center tool and
  // map clicks replaced them. Only the Nearby-radius slider remains.
  const radius = document.getElementById("radius");
  if (radius) {
    radius.addEventListener("input", () => {
      const lbl = document.getElementById("radiusLabel");
      if (lbl) lbl.textContent = radius.value;
      if (selected) selectLocation(selected);
    });
  }
}

// ---- impact SURFACES — statewide smooth "pollution wave" -------------------
// Each surface is a full grid (every cell has a value). We paint it to a canvas,
// tint by the variable's color, and lay it over MA as a smooth image overlay
// that fades in/out on toggle. This is the continuous wave, not markers.

let SURF = null;                 // from /api/surfaces
const surfOverlays = {};         // id -> L.imageOverlay
const surfOn = {};
const surfBase = {};             // id -> pristine grid (Array) before any DC bloom

// Add a dropped data center's contribution as a growing bloom into the surface
// grids, so the MAP ITSELF darkens around the site (no radius circles). `frac`
// 0..1 is how much of the data center's load is online (ramps during play).
window.applyDataCenterBloom = function (lat, lng, frac) {
  if (!SURF) return;
  const { nx, ny, bbox } = SURF;
  const [lon0, lat0, lon1, lat1] = bbox;
  // which surfaces a data center actually pushes on, and how hard
  const push = { air_fossil: 1.6, energy_demand: 1.8, water_stress: 1.6, noise: 1.6, ej_burden: 0 };
  // site position in grid coords
  const gx = ((lng - lon0) / (lon1 - lon0)) * (nx - 1);
  const gy = ((lat - lat0) / (lat1 - lat0)) * (ny - 1);
  const sigma = 3 + 7 * frac;          // tighter, punchier bloom that widens as it ramps
  SURF.surfaces.forEach((s) => {
    if (!surfBase[s.id]) surfBase[s.id] = s.grid.slice();
    const base = surfBase[s.id];
    const amp = (push[s.id] ?? 0) * frac;
    const g = base.slice();
    if (amp > 0) {
      for (let y = 0; y < ny; y++) {
        for (let x = 0; x < nx; x++) {
          const d2 = (x - gx) ** 2 + (y - gy) ** 2;
          const add = amp * Math.exp(-d2 / (2 * sigma * sigma));
          const i = y * nx + x;
          g[i] = Math.min(1, g[i] + add);
        }
      }
    }
    s.grid = g;
    if (surfOn[s.id] && surfOverlays[s.id]) {
      surfOverlays[s.id].setUrl(surfaceDataUrl(s));
    }
  });
};

// Reset surfaces to their pristine state (remove any data-center bloom).
window.clearDataCenterBloom = function () {
  if (!SURF) return;
  SURF.surfaces.forEach((s) => {
    if (surfBase[s.id]) {
      s.grid = surfBase[s.id].slice();
      if (surfOn[s.id] && surfOverlays[s.id]) surfOverlays[s.id].setUrl(surfaceDataUrl(s));
    }
  });
};

function hexRGB(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// Per-surface gradient ramps: low -> high. Gives real color separation across
// small value differences instead of one flat tint fading only in opacity.
const RAMP = [[18,34,38],[46,242,196],[255,176,32],[255,77,61]]; // clean->warn->bad
const RAMPS = {
  ej_burden: RAMP, air_fossil: RAMP, energy_demand: RAMP,
  water_stress: RAMP, noise: RAMP,
  // placement: high = GOOD, so flip — red(bad)->amber->green(good)
  placement: [[255,77,61],[255,176,32],[46,242,196],[46,242,196]],
};

function rampColor(id, v) {
  const r = RAMPS[id] || [[40,40,60],[240,80,60]];
  const n = r.length - 1;
  const x = Math.min(0.999, Math.max(0, v)) * n;
  const i = Math.floor(x), f = x - i;
  const a = r[i], b = r[Math.min(i + 1, n)];
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f];
}

// CSS linear-gradient string for a surface's ramp — used in the scale legend.
function rampGradientCss(id) {
  const r = RAMPS[id] || [[40,40,60],[240,80,60]];
  const stops = r.map((c, i) =>
    `rgb(${c[0]},${c[1]},${c[2]}) ${Math.round((i / (r.length - 1)) * 100)}%`);
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

// Sample a surface's normalized value (0..1) at a map lat/lng, or null if off-grid.
function sampleSurface(surf, lat, lng) {
  const [lon0, lat0, lon1, lat1] = SURF.bbox;
  if (lat < lat0 || lat > lat1 || lng < lon0 || lng > lon1) return null;
  const { nx, ny } = SURF;
  const fx = (lng - lon0) / (lon1 - lon0);
  const fy = (lat - lat0) / (lat1 - lat0);
  const ix = Math.min(nx - 1, Math.max(0, Math.round(fx * (nx - 1))));
  const iy = Math.min(ny - 1, Math.max(0, Math.round(fy * (ny - 1))));
  return surf.grid[iy * nx + ix];
}

function valueBucket(v) {
  if (v <= 0.33) return "Low";
  if (v <= 0.66) return "Medium";
  return "High";
}

// Render the color-scale legend for every active surface (Low -> High + unit).
function renderScaleLegend() {
  const box = document.getElementById("scaleLegend");
  if (!box || !SURF) return;
  const active = SURF.surfaces.filter((s) => surfOn[s.id]);
  if (active.length === 0) { box.innerHTML = ""; box.style.display = "none"; return; }
  box.style.display = "block";
  box.innerHTML = `<div class="sl-head">What the colors mean</div>` +
    active.map((s) => {
      const meta = SURF_META[s.id] || { title: s.label };
      return `
        <div class="sl-item">
          <div class="sl-top">
            <span class="sl-name">${meta.title}</span>
            <span class="sl-unit">${s.unit}</span>
          </div>
          <div class="sl-bar" style="background:${rampGradientCss(s.id)}"></div>
          <div class="sl-ends"><span>Low</span><span>High</span></div>
          <div class="sl-src">${s.source}</div>
        </div>`;
    }).join("");
}

// Live readout of surface values at the cursor position.
function renderHoverReadout(lat, lng) {
  const box = document.getElementById("hoverReadout");
  if (!box || !SURF) return;
  const active = SURF.surfaces.filter((s) => surfOn[s.id]);
  if (active.length === 0) { box.style.display = "none"; return; }
  const rows = active.map((s) => {
    const v = sampleSurface(s, lat, lng);
    const meta = SURF_META[s.id] || { title: s.label };
    if (v == null) return `<div class="hr-row"><span>${meta.title}</span><span class="hr-muted">—</span></div>`;
    const pct = Math.round(v * 100);
    const [r, g, b] = rampColor(s.id, v);
    return `<div class="hr-row">
      <span class="hr-dot" style="background:rgb(${r},${g},${b})"></span>
      <span class="hr-name">${meta.title}</span>
      <span class="hr-val">${valueBucket(v)} · ${pct}%</span>
    </div>`;
  }).join("");
  box.innerHTML = `<div class="hr-head">Intensity here</div>${rows}`;
  box.style.display = "block";
}

// paint one surface grid to a data-URL canvas using the gradient ramp
function surfaceDataUrl(surf) {
  const { nx, ny } = SURF;
  const cv = document.createElement("canvas");
  cv.width = nx; cv.height = ny;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(nx, ny);
  // Edge feather: fade alpha to 0 toward the rectangle border so the overlay
  // has no visible straight edge — it dissolves into the map instead.
  const featherX = nx * 0.14, featherY = ny * 0.14;
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const v = surf.grid[(ny - 1 - y) * nx + x];
      const [r, g, b] = rampColor(surf.id, v);
      const i = (y * nx + x) * 4;
      img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b;
      // distance from nearest edge, normalized 0 (edge) .. 1 (interior)
      const ex = Math.min(x, nx - 1 - x) / featherX;
      const ey = Math.min(y, ny - 1 - y) / featherY;
      const edge = Math.min(1, ex) * Math.min(1, ey);
      // steep alpha curve: low values stay faint, mid/high separate strongly
      img.data[i + 3] = Math.round(Math.pow(v, 0.5) * 225 * edge);
    }
  }
  ctx.putImageData(img, 0, 0);
  // upscale smoothly for a soft continuous wave
  const cv2 = document.createElement("canvas");
  cv2.width = nx * 6; cv2.height = ny * 6;
  const c2 = cv2.getContext("2d");
  c2.imageSmoothingEnabled = true;
  c2.imageSmoothingQuality = "high";
  c2.drawImage(cv, 0, 0, cv2.width, cv2.height);
  return cv2.toDataURL();
}

function buildSurface(surf) {
  const [lon0, lat0, lon1, lat1] = SURF.bbox;
  // Bleed the overlay beyond the data bbox so the gradient's rectangular edge
  // sits off-screen and the wash reaches the screen edges continuously.
  const padLat = (lat1 - lat0) * 0.25;
  const padLon = (lon1 - lon0) * 0.25;
  const bounds = [[lat0 - padLat, lon0 - padLon], [lat1 + padLat, lon1 + padLon]];
  const ov = L.imageOverlay(surfaceDataUrl(surf), bounds, {
    opacity: 0, interactive: false, className: "surf-overlay",
  });
  surfOverlays[surf.id] = ov;
}

function toggleSurface(id, on) {
  surfOn[id] = on;
  const ov = surfOverlays[id];
  if (ov) {
    if (on) {
      ov.addTo(map);
      requestAnimationFrame(() => ov.setOpacity(0.7));
    } else {
      ov.setOpacity(0);
      setTimeout(() => map.removeLayer(ov), 500);
    }
  }
  renderScaleLegend();
}

// Friendly metadata per surface: an icon + a plain-language one-liner.
// Keyed by surface id so it survives label changes in the data.
const SURF_META = {
  ej_burden: {
    icon: '<span data-lucide="users"></span>',
    title: "People",
    desc: "Who lives nearby — environmental-justice population density.",
  },
  air_fossil: {
    icon: '<span data-lucide="factory"></span>',
    title: "Air",
    desc: "Fossil-plant intensity — dirtier air where plants run.",
  },
  energy_demand: {
    icon: '<span data-lucide="zap"></span>',
    title: "Energy",
    desc: "Grid demand pressure across the state.",
  },
  water_stress: {
    icon: '<span data-lucide="droplet"></span>',
    title: "Water",
    desc: "Cooling-water demand (modeled estimate).",
  },
  noise: {
    icon: '<span data-lucide="volume-2"></span>',
    title: "Noise",
    desc: "Generator & cooling noise (modeled estimate).",
  },
};

function updateLayerCount() {
  const n = Object.values(surfOn).filter(Boolean).length;
  const el = document.getElementById("lcCount");
  if (el) el.textContent = n ? `${n} on` : "none on";
}

function buildLayerControl() {
  const list = document.getElementById("layerList");
  list.innerHTML = "";
  SURF.surfaces.forEach((surf, i) => {
    buildSurface(surf);
    const on = i === 0; // EJ wave on by default
    const meta = SURF_META[surf.id] || { icon: "◆", title: surf.label, desc: "" };

    const row = document.createElement("label");
    row.className = "lc-row";
    row.dataset.on = on ? "1" : "0";
    row.style.setProperty("--swatch", surf.color);
    row.innerHTML = `
      <span class="lc-icon" style="background:${surf.color}22;color:${surf.color}">${meta.icon}</span>
      <span class="lc-text">
        <span class="lc-title-row">
          <span class="lc-label">${meta.title}</span>
          <span class="lc-tag ${surf.kind}">${surf.kind}</span>
        </span>
        <span class="lc-desc">${meta.desc}</span>
      </span>
      <span class="lc-toggle" aria-hidden="true"><span class="lc-knob"></span></span>
      <input type="checkbox" class="lc-check" ${on ? "checked" : ""} data-id="${surf.id}" />`;

    const input = row.querySelector("input");
    input.addEventListener("change", (e) => {
      toggleSurface(surf.id, e.target.checked);
      row.dataset.on = e.target.checked ? "1" : "0";
      updateLayerCount();
    });

    list.appendChild(row);
    if (on) toggleSurface(surf.id, true);
  });
  updateLayerCount();
  _lucide();
}

function wireCollapse() {
  const btn = document.getElementById("lcCollapse");
  const control = document.getElementById("layerControl");
  if (!btn || !control) return;
  // Stop scroll/click over the panel from zooming/panning the map underneath.
  if (window.L && L.DomEvent) {
    L.DomEvent.disableScrollPropagation(control);
    L.DomEvent.disableClickPropagation(control);
  }
  btn.addEventListener("click", () => {
    const collapsed = control.classList.toggle("collapsed");
    btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  });
}

// Draw the Massachusetts state boundary as an outline. Stays visible at all
// zoom levels (it's vector, not tied to the gradient overlay).
let stateOutline = null;
async function drawStateOutline() {
  try {
    const res = await fetch("/ma_boundary.geojson");
    const geo = await res.json();
    stateOutline = L.geoJSON(geo, {
      interactive: false,
      style: {
        color: "#eaf2ff",     // light border line
        weight: 2,
        opacity: 0.9,
        fill: false,          // outline only, no fill tint
        dashArray: "4 3",
      },
    }).addTo(map);
    stateOutline.bringToFront();
  } catch (e) {
    console.warn("MA boundary unavailable", e);
  }
}

// Lock the view to the gradient (surface) extent: fit it to fill the screen,
// cap zoom-out at that fit, and stop panning into empty map around it.
function lockViewToSurfaces() {
  if (!SURF || !SURF.bbox) return;
  const [lon0, lat0, lon1, lat1] = SURF.bbox;
  const bounds = L.latLngBounds([lat0, lon0], [lat1, lon1]);

  // Make sure Leaflet knows its real pixel size before measuring zoom.
  map.invalidateSize();

  // Fit the whole state with generous margin. Round DOWN and then subtract one
  // more level so Massachusetts never sits flush against the frame.
  const padded = bounds.pad(0.18);
  const fitZoom = Math.max(1, Math.floor(map.getBoundsZoom(padded, true)) - 1);
  map.setMinZoom(fitZoom);
  map.setView(bounds.getCenter(), fitZoom, { animate: false });

  // Can't pan into empty map around the region.
  map.setMaxBounds(padded.pad(0.4));
  map.options.maxBoundsViscosity = 1.0; // hard stop at the edges
}

async function loadLayers() {
  try {
    const res = await fetch("/api/surfaces");
    SURF = await res.json();
    buildLayerControl();
    wireCollapse();
    lockViewToSurfaces();
  } catch (e) {
    console.warn("surfaces unavailable", e);
  }
}

// ---- init ------------------------------------------------------------------

async function init() {
  const res = await fetch("/api/facilities");
  DATA = await res.json();

  const r0 = DATA.regions[0];
  map = L.map("map", { zoomControl: false }).setView([r0.center.lat, r0.center.lng], r0.zoom);

  const cartoTiles = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  });
  cartoTiles.addTo(map);

  facilityLayer = L.layerGroup().addTo(map);
  drawAllMarkers();

  await loadLayers();

  // MA state outline, drawn above the gradient so the border stays crisp.
  await drawStateOutline();

  map.on("click", (e) => selectLocation({ lat: e.latlng.lat, lng: e.latlng.lng }));

  // Live value readout of active surfaces under the cursor. On mouse-out,
  // fall back to the last selected location so the box stays populated.
  map.on("mousemove", (e) => renderHoverReadout(e.latlng.lat, e.latlng.lng));
  map.on("mouseout", () => {
    if (selected) renderHoverReadout(selected.lat, selected.lng);
  });

  // Collapsible right panel
  const panel = document.getElementById("panel");
  const panelToggle = document.getElementById("panelToggle");
  panelToggle.addEventListener("click", () => {
    const collapsed = panel.classList.toggle("collapsed");
    panelToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    panelToggle.title = collapsed ? "Open panel" : "Collapse panel";
    // Let Leaflet re-measure after the width transition.
    setTimeout(() => map.invalidateSize(), 280);
  });

  populateControls();

  // Select the first city by default so the user sees the indicator immediately.
  const firstCity = DATA.cities.find((c) => c.region === r0.id);
  if (firstCity) selectLocation({ lat: firstCity.lat, lng: firstCity.lng });
}

init();
setTimeout(() => { try { if (window.lucide) lucide.createIcons(); } catch (e) {} }, 300);

// ---- Drop-a-data-center + play buildout timeline ---------------------------
(function () {
  let dropMode = false, dropMarker = null, ringLayers = [], playTimer = null, lastPlayed = false;

  function onReady(fn) {
    if (typeof map !== "undefined" && map) fn();
    else setTimeout(() => onReady(fn), 200);
  }

  onReady(() => {
    const dropBtn = document.getElementById("dropBtn");
    const controls = document.getElementById("dropControls");
    const playBtn = document.getElementById("playBtn");
    const readout = document.getElementById("playReadout");
    if (!dropBtn) return;

    dropBtn.addEventListener("click", () => {
      dropMode = !dropMode;
      dropBtn.classList.toggle("armed", dropMode);
      dropBtn.textContent = dropMode ? "Click the map…" : "Drop a data center";
    });

    const bestBtn = document.getElementById("bestSiteBtn");
    let top5Markers = [];
    if (bestBtn) bestBtn.addEventListener("click", async () => {
      bestBtn.textContent = "Finding…";
      try {
        const res = await fetch("/api/bestsite?n=5&spacing=30");
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const sites = data.sites || [];
        // clear any previous top-5 markers
        top5Markers.forEach((m) => map.removeLayer(m));
        top5Markers = [];
        // turn on the placement layer
        const pc = document.querySelector('.lc-row input[data-id="placement"]');
        if (pc && !pc.checked) { pc.checked = true; pc.dispatchEvent(new Event("change")); }
        // drop a numbered marker for each spaced site
        sites.forEach((st, idx) => {
          const m = L.marker([st.lat, st.lon], {
            icon: L.divIcon({ className: "", iconSize: [22, 22], iconAnchor: [11, 11],
              html: `<div class="best-pin">${idx + 1}</div>` }),
          }).addTo(map);
          m.bindTooltip(`#${idx + 1} · score ${st.score}`, { direction: "top" });
          top5Markers.push(m);
        });
        // fit the map to show all five
        if (sites.length) {
          map.fitBounds(L.latLngBounds(sites.map((s) => [s.lat, s.lon])).pad(0.3));
        }
        // list them in the Impact tab
        const rows = sites.map((st, i) =>
          `<div class="best-row"><span class="best-no">${i + 1}</span>
             <span class="num">${st.lat.toFixed(2)}, ${st.lon.toFixed(2)}</span>
             <span class="best-score">score ${st.score}</span></div>`).join("");
        if (window.showImpact) window.showImpact(
          "Top 5 sites · 30+ mi apart",
          "Best places to build — fewest people, cleanest, most grid room.",
          `<div class="best-list">${rows}</div>` +
          `<p class="muted" style="margin-top:8px">Higher score = better. Spaced ≥30 mi so they're real alternatives, not one cluster.</p>`,
          true);
        bestBtn.innerHTML = '<span data-lucide="target"></span> Top 5 sites found';
        if (window.lucide) lucide.createIcons();
      } catch (e) { bestBtn.textContent = "Error finding sites"; }
    });

    const removeBtn = document.getElementById("removeDcBtn");
    if (removeBtn) removeBtn.addEventListener("click", () => {
      if (playTimer) { clearInterval(playTimer); playTimer = null; }
      if (dropMarker) { map.removeLayer(dropMarker); dropMarker = null; }
      clearRings();                                  // removes bloom + any rings
      lastData = null; lastPlayed = false;
      controls.style.display = "none";
      removeBtn.style.display = "none";
      if (readout) readout.innerHTML = "";
      if (playBtn) playBtn.textContent = "Play buildout";
      if (window.showImpact) window.showImpact(
        "Drop or click a site",
        "Pick a preset, drop a data center, or find the best site.",
        "", false);
    });

    map.on("click", (e) => {
      if (!dropMode) return;
      dropMode = false;
      dropBtn.classList.remove("armed");
      dropBtn.textContent = "Move the pin";
      placePin(e.latlng.lat, e.latlng.lng);
      controls.style.display = "block";
      refreshImpact();           // show impact immediately on drop
    });

    function placePin(lat, lng) {
      if (dropMarker) map.removeLayer(dropMarker);
      dropMarker = L.marker([lat, lng], { draggable: true }).addTo(map);
      dropMarker._ll = { lat, lng };
      dropMarker.bindTooltip("Drag me anywhere", { direction: "top" });
      const rm = document.getElementById("removeDcBtn");
      if (rm) rm.style.display = "block";   // show Remove once a pin exists
      dropMarker.on("drag", (ev) => {
        const p = ev.target.getLatLng();
        dropMarker._ll = { lat: p.lat, lng: p.lng };
      });
      dropMarker.on("dragend", () => refreshImpact()); // recompute at new spot
    }

    function clearRings() {
      ringLayers.forEach((l) => map.removeLayer(l));
      ringLayers = [];
      if (window.clearDataCenterBloom) window.clearDataCenterBloom();
    }

    // The MAP itself darkens around the site (surface layers bloom), no circles.
    function drawRings(ll, yearData) {
      // make sure an impact layer is ON so the change is visible
      ensureImpactLayerVisible();
      const frac = (yearData.mw_online / (lastData ? lastData.target_mw : yearData.mw_online)) || 1;
      if (window.applyDataCenterBloom) window.applyDataCenterBloom(ll.lat, ll.lng, frac);
    }

    // Turn on at least one impact surface so the bloom is visible when playing.
    function ensureImpactLayerVisible() {
      if (typeof surfOn === "undefined") return;
      // a data center only blooms air/energy/water/noise — NOT people.
      // If none of those bloomable layers is on, turn Air on so play is visible.
      const bloomable = ["air_fossil", "energy_demand", "water_stress", "noise"];
      const anyBloomOn = bloomable.some((id) => surfOn[id]);
      if (!anyBloomOn) {
        const cb = document.querySelector('.lc-row input[data-id="air_fossil"]');
        if (cb && !cb.checked) { cb.checked = true; cb.dispatchEvent(new Event("change")); }
      }
    }

    function cardHtml(y) {
      const r25 = y.rings[y.rings.length - 1];
      const f = y.factors || {};
      const maxY = lastData ? lastData.years[lastData.years.length - 1] : y;
      const fin = maxY.factors || {};
      // scale each factor's bar vs its own full-buildout value
      const bar = (cur, max, color) => {
        const pct = max ? Math.min(100, Math.round(100 * cur / max)) : 0;
        return pct;
      };
      // severity color on OUR palette only (teal ok, amber watch, red high)
      const sev = (p) => p >= 66 ? "var(--bad)" : p >= 33 ? "var(--warn)" : "var(--clean)";
      const F = (icon, label, fac, finFac) => {
        if (!fac) return "";
        const p = bar(fac.value, finFac ? finFac.value : fac.value);
        const c = sev(p);
        const [num, ...rest] = String(fac.value.toLocaleString()).split(" ");
        return `<div class="factor-card">
           <div class="factor-row">
             <span class="factor-ico">${icon}</span>
             <span class="factor-name">${label}</span>
             <span class="factor-val"><b style="color:${c}">${fac.value.toLocaleString()}</b> <span class="factor-unit">${fac.unit}</span></span>
           </div>
           <div class="grow-bar"><div style="width:${Math.max(4,p)}%;background:${c}"></div></div>
           <div class="factor-note">${fac.note}</div>
         </div>`;
      };
      return (
        `<div class="year-badge">Year ${y.year} of ${lastData ? lastData.buildout_years : "?"}</div>` +
        `<div class="meter"><div class="meter-head">On paper vs by the hour</div>` +
        `<div class="meter-row"><span class="meter-annual">100%<small>annual</small></span>` +
        `<span class="meter-arrow">→</span><span class="meter-hourly">${y.hourly_match_pct}%<small>hourly</small></span></div>` +
        `<div class="meter-bar"><div class="meter-fill" style="width:${y.hourly_match_pct}%"></div></div></div>` +
        `<div class="factor-head">Impact by factor</div>` +
        F("<span data-lucide=\"factory\"></span>", "Air · CO₂", f.air, fin.air) +
        F("<span data-lucide=\"zap\"></span>", "Energy", f.energy, fin.energy) +
        F("<span data-lucide=\"droplet\"></span>", "Water", f.water, fin.water) +
        F("<span data-lucide=\"volume-2\"></span>", "Noise", f.noise, fin.noise) +
        `<div class="impact-stat" style="margin-top:8px"><span data-lucide="users"></span> <b>${r25.pop_within.toLocaleString()}</b> people within 25 km · ${r25.minority_pct}% minority</div>` +
        `<p class="muted" style="margin-top:6px">Predicted — shapes are real physics, coefficients modeled. Not measured.</p>`
      );
    }

    // Fetch the timeline once and show the FINAL-year impact card + rings.
    // Called on drop and on drag-end so the card always reflects the pin.
    let lastData = null;
    async function refreshImpact() {
      if (!dropMarker) return;
      const ll = dropMarker._ll;
      const mw = Number(document.getElementById("dropMw").value) || 274;
      const yrs = Number(document.getElementById("dropYears").value) || 5;
      if (readout) readout.innerHTML = '<span class="muted">Computing…</span>';
      try {
        const res = await fetch(`/api/timeline?lat=${ll.lat}&lon=${ll.lng}&mw=${mw}&years=${yrs}`);
        lastData = await res.json();
        if (lastData.error) throw new Error(lastData.error);
      } catch (err) { if (readout) readout.textContent = "Error: " + err.message; return; }
      const finalY = lastData.years[lastData.years.length - 1];
      drawRings(ll, finalY);
      const html = cardHtml(finalY);
      // left panel shows only a short pointer; the full card lives in Impact tab
      if (readout) readout.innerHTML = '<span class="muted">See the Impact tab →</span>';
      if (window.showImpact) window.showImpact(
        `Dropped site · ${finalY.mw_online} MW`, "Predicted impact at full buildout", html, true);
    }
    window._refreshImpact = refreshImpact;  // expose for preset buttons

    playBtn.addEventListener("click", async () => {
      if (!dropMarker) { if (readout) readout.textContent = "Drop a pin first."; return; }
      if (playTimer) { clearInterval(playTimer); playTimer = null; playBtn.textContent = "Play buildout"; return; }
      const ll = dropMarker._ll;
      const mw = Number(document.getElementById("dropMw").value) || 274;
      const yrs = Number(document.getElementById("dropYears").value) || 5;
      let data = lastData;
      // re-fetch if inputs changed or nothing cached yet
      if (!data || data.target_mw !== mw || data.buildout_years !== yrs) {
        if (readout) readout.textContent = "Computing…";
        try {
          const res = await fetch(`/api/timeline?lat=${ll.lat}&lon=${ll.lng}&mw=${mw}&years=${yrs}`);
          data = await res.json();
          if (data.error) throw new Error(data.error);
          lastData = data;
        } catch (err) { if (readout) readout.textContent = "Error: " + err.message; return; }
      }

      const impBtn = document.querySelector('.tab-btn[data-tab="impact"]');
      if (impBtn) impBtn.click();
      playBtn.textContent = "Stop";
      let i = 0;
      const step = () => {
        const y = data.years[i];
        drawRings(ll, y);
        const html = cardHtml(y);
        if (readout) readout.innerHTML = `<span class="muted">Year ${y.year} — see Impact tab →</span>`;
        if (window.showImpact) window.showImpact(
          `Dropped site · ${y.mw_online} MW (year ${y.year})`,
          "Predicted — projected buildout", html, false);
        i++;
        if (i >= data.years.length) { clearInterval(playTimer); playTimer = null; playBtn.textContent = "Replay"; lastPlayed = true; }
      };
      step();
      playTimer = setInterval(step, 1400);
    });

    // changing MW or years re-computes the card immediately
    ["dropMw", "dropYears"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", () => { if (dropMarker) refreshImpact(); });
    });
  });
})();

// ---- Right-panel tabs: Impact | Nearby | Model -----------------------------
(function () {
  function ready(fn){ if (document.querySelector(".tab-bar")) fn(); else setTimeout(()=>ready(fn),150); }
  ready(() => {
    const btns = [...document.querySelectorAll(".tab-btn")];
    const panes = [...document.querySelectorAll(".tab-pane")];
    btns.forEach((b) => b.addEventListener("click", () => {
      const t = b.dataset.tab;
      btns.forEach((x) => x.classList.toggle("active", x === b));
      panes.forEach((p) => {
        const on = p.dataset.pane === t;
        p.classList.toggle("active", on);
        p.hidden = !on;
      });
    }));

    // Fill the Model tab from /api/... importances baked into the page.
    const mb = document.getElementById("modelBody");
    if (mb) {
      const fi = [["Cheap electricity",46,"#e4572e"],["Cool climate",34,"#f0a202"],
                  ["Grid carbon",9,"#5aa9e6"],["Near a city",9,"#5aa9e6"],["People nearby",2,"#868e96"]];
      mb.innerHTML = fi.map(([k,v,c]) =>
        `<div class="fi-row"><span class="fi-label">${k}</span>
           <span class="fi-bar"><span style="width:${v}%;background:${c}"></span></span>
           <b>${v}%</b></div>`).join("") +
        `<p class="muted" style="margin-top:8px">Data centers chase cheap power & cool air —
         not carbon or people. That's the gap a town's approval has to fill.</p>`; _lucide();
    }
  });

  // Expose a helper the drop/click code can call to fill the Impact tab.
  window.showImpact = function (title, sub, html, openTab) {
    const t = document.getElementById("impactTitle");
    const s = document.getElementById("impactSub");
    const b = document.getElementById("impactBody");
    if (t) t.textContent = title;
    if (s) s.textContent = sub;
    if (b) b.innerHTML = html; _lucide();
    if (openTab) {
      const btn = document.querySelector('.tab-btn[data-tab="impact"]');
      if (btn) btn.click();
    }
  };
})();
