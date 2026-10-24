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
let statusFilter = "all"; // display-only: "all" | "operating" | "proposed"

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

function markerIcon(level, isDataCenter) {
  const color = EMISSION_COLORS[level];
  const dc = isDataCenter ? "marker-dc" : "";
  return L.divIcon({
    className: "",
    html: `<div class="marker-emission ${dc}" style="width:16px;height:16px;background:${color};box-shadow:0 0 8px 2px ${color}99;--glow:${color}88"></div>`,
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
    // display-only status filter; does not alter any data or calculation
    if (statusFilter !== "all" && f.status !== statusFilter) return;
    const level = levelFor(f);
    const m = L.marker([f.lat, f.lng], { icon: markerIcon(level, f.type === "data_center") });
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
    .filter((f) => statusFilter === "all" || f.status === statusFilter)
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
      ? `<div class="meter-inline">Annual <b>${f.annual_match_pct}%</b> → Hourly <b style="color:#FF4D3D">${f.hourly_match_pct}%</b></div>`
      : "";
    const confLine = f.confidence
      ? `<div class="conf-note"><span class="conf-dot conf-${f.confidence}"></span>${f.confidence} confidence · ${f.confidence_note || ""}</div>`
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
      ${confLine}
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
  if (radiusCircle) map.removeLayer(radiusCircle);
  radiusCircle = L.circle([center.lat, center.lng], {
    radius: radiusKm * 1000,
    color: "#2EF2C4",
    weight: 1,
    fillColor: "#2EF2C4",
    fillOpacity: 0.06,
  }).addTo(map);
  renderPanel(center, radiusKm);
}

// ---- controls --------------------------------------------------------------

function populateControls() {
  const regionSel = document.getElementById("region");
  const citySel = document.getElementById("city");

  DATA.regions.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.label;
    regionSel.appendChild(opt);
  });

  function fillCities(regionId) {
    citySel.innerHTML = "";
    DATA.cities
      .filter((c) => c.region === regionId)
      .forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.name;
        opt.textContent = c.name;
        citySel.appendChild(opt);
      });
  }

  regionSel.addEventListener("change", () => {
    const region = DATA.regions.find((r) => r.id === regionSel.value);
    fillCities(region.id);
    map.setView([region.center.lat, region.center.lng], region.zoom);
    citySel.dispatchEvent(new Event("change"));
  });

  citySel.addEventListener("change", () => {
    const city = DATA.cities.find((c) => c.name === citySel.value);
    if (!city) return;
    map.setView([city.lat, city.lng], 10);
    selectLocation({ lat: city.lat, lng: city.lng });
  });

  const radius = document.getElementById("radius");
  radius.addEventListener("input", () => {
    document.getElementById("radiusLabel").textContent = radius.value;
    if (selected) selectLocation(selected);
  });

  fillCities(DATA.regions[0].id);
}

// ---- impact SURFACES — statewide smooth "pollution wave" -------------------
// Each surface is a full grid (every cell has a value). We paint it to a canvas,
// tint by the variable's color, and lay it over MA as a smooth image overlay
// that fades in/out on toggle. This is the continuous wave, not markers.

let SURF = null;                 // from /api/surfaces
const surfOverlays = {};         // id -> L.imageOverlay
const surfOn = {};

function hexRGB(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// Per-surface gradient ramps: low -> high. Spec palette only — a single
// clean -> warn -> bad ramp (teal -> amber -> red), no rainbow/purple/pink.
// Water & Noise (modeled) use the same ramp so the whole map speaks one scale.
const SPEC_RAMP = [[46,242,196],[46,242,196],[255,176,32],[255,77,61]];
const RAMPS = {
  ej_burden:     SPEC_RAMP,
  air_fossil:    SPEC_RAMP,
  energy_demand: SPEC_RAMP,
  water_stress:  SPEC_RAMP,
  noise:         SPEC_RAMP,
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
      requestAnimationFrame(() => ov.setOpacity(0.45));
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
    icon: "users",
    title: "People",
    desc: "Who lives nearby — environmental-justice population density.",
  },
  air_fossil: {
    icon: "factory",
    title: "Air",
    desc: "Fossil-plant intensity — dirtier air where plants run.",
  },
  energy_demand: {
    icon: "zap",
    title: "Energy",
    desc: "Grid demand pressure across the state.",
  },
  water_stress: {
    icon: "droplet",
    title: "Water",
    desc: "Cooling-water demand (modeled estimate).",
  },
  noise: {
    icon: "volume-2",
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
    const meta = SURF_META[surf.id] || { icon: "layers", title: surf.label, desc: "" };

    const row = document.createElement("label");
    row.className = "lc-row";
    row.dataset.on = on ? "1" : "0";
    row.dataset.kind = surf.kind; // "measured" | "modeled" -> dashed border for modeled
    row.style.setProperty("--swatch", surf.color);
    row.innerHTML = `
      <span class="lc-icon"><i data-lucide="${meta.icon}"></i></span>
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
}

function wireCollapse() {
  const btn = document.getElementById("lcCollapse");
  const control = document.getElementById("layerControl");
  if (!btn || !control) return;
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
        color: "#7D8A99",     // dim border line (spec --text-dim)
        weight: 1,
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

  // Zoom at which the whole data extent just fits the viewport. getBoundsZoom
  // returns a fractional value; with the default zoomSnap of 1 that would still
  // allow one level of zoom-out, so round UP to a hard integer floor.
  const fitZoom = Math.ceil(map.getBoundsZoom(bounds, true));
  map.setMinZoom(fitZoom);
  map.setView(bounds.getCenter(), fitZoom, { animate: false });

  // Can't pan into empty map around the region.
  map.setMaxBounds(bounds);
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

// Status filter tabs — display-only. Redraws markers and re-renders the panel
// for the chosen status. No data, thresholds, or calculations are changed.
function wireStatusTabs() {
  const tabs = document.querySelectorAll(".status-tab");
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      statusFilter = btn.dataset.filter;
      tabs.forEach((b) => b.classList.toggle("active", b === btn));
      drawAllMarkers();
      if (selected) renderPanel(selected, Number(document.getElementById("radius").value));
    });
  });
}

// ---- init ------------------------------------------------------------------

async function init() {
  const res = await fetch("/api/facilities");
  DATA = await res.json();

  const r0 = DATA.regions[0];
  map = L.map("map", { zoomControl: false }).setView([r0.center.lat, r0.center.lng], r0.zoom);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  }).addTo(map);

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

  // Status filter tabs (All / Operating / Proposed) — display only.
  wireStatusTabs();

  // Select the first city by default so the user sees the indicator immediately.
  const firstCity = DATA.cities.find((c) => c.region === r0.id);
  if (firstCity) selectLocation({ lat: firstCity.lat, lng: firstCity.lng });
}

init();

// ---- Protected & Recreational OpenSpace (MassGIS) — optional overlay -------
// Fetches real polygons from MassGIS (proxied by the server) and draws them as
// a toggleable green layer. Also checks each facility for intersection and
// flags the ones on protected land. Self-contained; no existing logic touched.
(function () {
  let osLayer = null;
  let osLoaded = false;

  function onReady(fn) {
    if (typeof map !== "undefined" && map) fn();
    else setTimeout(() => onReady(fn), 200);
  }

  async function loadOverlay() {
    const status = document.getElementById("osStatus");
    status.textContent = "Loading MassGIS open space…";
    try {
      const res = await fetch("/api/openspace"); // all-MA bbox default
      const geo = await res.json();
      if (geo.error) throw new Error(geo.error);
      osLayer = L.geoJSON(geo, {
        interactive: true,
        style: {
          color: "#2EF2C4", weight: 1, opacity: 0.8,
          fillColor: "#2EF2C4", fillOpacity: 0.14,
        },
        onEachFeature: (f, lyr) => {
          const p = f.properties || {};
          lyr.bindPopup(
            `<div class="pop-title">${p.SITE_NAME || "Open space"}</div>` +
            `<div class="pop-meta">${p.PRIM_PURP || ""}${p.LEV_PROT ? " · " + p.LEV_PROT : ""}</div>`
          );
        },
      }).addTo(map);
      osLoaded = true;
      status.innerHTML = `<span class="os-ok">${(geo.features || []).length} open-space areas shown</span>`;
      checkFacilities();
    } catch (e) {
      status.innerHTML = `<span class="os-err">Could not load open space: ${e.message}</span>`;
    }
  }

  // Flag facilities whose coordinate sits on protected land.
  async function checkFacilities() {
    if (!window.DATA || !DATA.facilities) return;
    const status = document.getElementById("osStatus");
    const hits = [];
    for (const f of DATA.facilities) {
      try {
        const r = await fetch(`/api/openspace?point=${f.lng},${f.lat}`);
        const j = await r.json();
        if (j.on_protected) {
          hits.push(`${f.name} — ${j.sites[0]?.SITE_NAME || "protected land"}`);
        }
      } catch (_) { /* skip a failed point, keep going */ }
    }
    const base = status.querySelector(".os-ok")?.outerHTML || status.innerHTML;
    status.innerHTML = base + (hits.length
      ? `<div class="os-flag"><b>${hits.length}</b> site(s) on protected land:<br>${hits.join("<br>")}</div>`
      : `<div class="os-clear">No facilities sit on protected open space.</div>`);
  }

  onReady(() => {
    const toggle = document.getElementById("osToggle");
    const row = document.getElementById("osRow");
    if (!toggle) return;
    toggle.addEventListener("change", (e) => {
      const on = e.target.checked;
      row.dataset.on = on ? "1" : "0";
      if (on) {
        if (!osLoaded) loadOverlay();
        else { osLayer.addTo(map); document.getElementById("osStatus").style.display = "block"; }
      } else {
        if (osLayer) map.removeLayer(osLayer);
        document.getElementById("osStatus").style.display = "none";
      }
    });
  });
})();

// ---- Drop-a-data-center + play buildout timeline ---------------------------
(function () {
  let dropMode = false, dropMarker = null, ringLayers = [], playTimer = null;

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
      dropBtn.innerHTML = dropMode
        ? '<i data-lucide="map-pin"></i> Click the map…'
        : '<i data-lucide="map-pin"></i> Drop a data center';
      if (window.lucide) window.lucide.createIcons();
    });

    map.on("click", (e) => {
      if (!dropMode) return;
      dropMode = false;
      dropBtn.classList.remove("armed");
      dropBtn.innerHTML = '<i data-lucide="map-pin"></i> Move the pin';
      if (window.lucide) window.lucide.createIcons();
      placePin(e.latlng.lat, e.latlng.lng);
      controls.style.display = "block";
    });

    function placePin(lat, lng) {
      if (dropMarker) map.removeLayer(dropMarker);
      dropMarker = L.marker([lat, lng]).addTo(map);
      dropMarker._ll = { lat, lng };
    }

    function clearRings() {
      ringLayers.forEach((l) => map.removeLayer(l));
      ringLayers = [];
    }

    function drawRings(ll, yearData) {
      clearRings();
      // outer -> inner so inner sits on top
      [...yearData.rings].reverse().forEach((r) => {
        const alpha = 0.08 + 0.5 * r.intensity;
        const c = L.circle([ll.lat, ll.lng], {
          radius: r.km * 1000, color: "#FF4D3D", weight: 1,
          fillColor: "#FF4D3D", fillOpacity: alpha,
        }).addTo(map);
        ringLayers.push(c);
      });
    }

    playBtn.addEventListener("click", async () => {
      if (!dropMarker) { readout.textContent = "Drop a pin first."; return; }
      if (playTimer) { clearInterval(playTimer); playTimer = null; playBtn.innerHTML = '<i data-lucide="play"></i> Play buildout'; if (window.lucide) window.lucide.createIcons(); return; }
      const ll = dropMarker._ll;
      const mw = Number(document.getElementById("dropMw").value) || 274;
      const yrs = Number(document.getElementById("dropYears").value) || 5;
      readout.textContent = "Computing…";
      let data;
      try {
        const res = await fetch(`/api/timeline?lat=${ll.lat}&lon=${ll.lng}&mw=${mw}&years=${yrs}`);
        data = await res.json();
        if (data.error) throw new Error(data.error);
      } catch (err) { readout.textContent = "Error: " + err.message; return; }

      playBtn.innerHTML = '<i data-lucide="pause"></i> Stop';
      if (window.lucide) window.lucide.createIcons();
      let i = 0;
      const step = () => {
        const y = data.years[i];
        const r25 = y.rings[y.rings.length - 1];
        drawRings(ll, y);
        readout.innerHTML =
          `<b>Year ${y.year}</b> · ${y.mw_online} MW online<br>` +
          `${r25.pop_within.toLocaleString()} people within 25 km<br>` +
          `hidden CO₂ <b>${y.hidden_co2_t.toLocaleString()}</b> t/yr<br>` +
          `<span class="muted">${r25.minority_pct}% minority in footprint · projected buildout</span>`;
        i++;
        if (i >= data.years.length) { clearInterval(playTimer); playTimer = null; playBtn.innerHTML = '<i data-lucide="rotate-ccw"></i> Replay'; if (window.lucide) window.lucide.createIcons(); }
      };
      step();
      playTimer = setInterval(step, 1100);
    });
  });
})();
