// HourMatch — emissions map (Leaflet + OpenStreetMap, no API key)

const EMISSION_COLORS = {
  high: "#e4572e",
  medium: "#f3c13a",
  low: "#3cb371",
  clean: "#2f9e44",
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
    html: `<div class="marker-emission" style="width:18px;height:18px;background:${color}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
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
  const radiusKm = Number(document.getElementById("radius").value);
  if (radiusCircle) map.removeLayer(radiusCircle);
  radiusCircle = L.circle([center.lat, center.lng], {
    radius: radiusKm * 1000,
    color: "#5aa9e6",
    weight: 1,
    fillColor: "#5aa9e6",
    fillOpacity: 0.08,
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

// Per-surface gradient ramps: low -> high. Gives real color separation across
// small value differences instead of one flat tint fading only in opacity.
const RAMPS = {
  ej_burden:     [[59,76,192],[120,180,120],[240,220,90],[217,79,112]],
  air_fossil:    [[40,60,120],[90,180,160],[245,200,70],[228,70,46]],
  energy_demand: [[35,40,90],[70,160,200],[243,193,58],[233,120,40]],
  water_stress:  [[10,30,70],[40,120,200],[90,200,230],[180,240,255]],
  noise:         [[30,20,60],[120,80,200],[176,132,243],[240,210,255]],
};

function rampColor(id, v) {
  const r = RAMPS[id] || [[40,40,60],[240,80,60]];
  const n = r.length - 1;
  const x = Math.min(0.999, Math.max(0, v)) * n;
  const i = Math.floor(x), f = x - i;
  const a = r[i], b = r[Math.min(i + 1, n)];
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f];
}

// paint one surface grid to a data-URL canvas using the gradient ramp
function surfaceDataUrl(surf) {
  const { nx, ny } = SURF;
  const cv = document.createElement("canvas");
  cv.width = nx; cv.height = ny;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(nx, ny);
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      const v = surf.grid[(ny - 1 - y) * nx + x];
      const [r, g, b] = rampColor(surf.id, v);
      const i = (y * nx + x) * 4;
      img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b;
      // steep alpha curve: low values stay faint, mid/high separate strongly
      img.data[i + 3] = Math.round(Math.pow(v, 0.5) * 225);
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
  const bounds = [[lat0, lon0], [lat1, lon1]];
  const ov = L.imageOverlay(surfaceDataUrl(surf), bounds, {
    opacity: 0, interactive: false, className: "surf-overlay",
  });
  surfOverlays[surf.id] = ov;
}

function toggleSurface(id, on) {
  surfOn[id] = on;
  const ov = surfOverlays[id];
  if (!ov) return;
  if (on) {
    ov.addTo(map);
    requestAnimationFrame(() => ov.setOpacity(0.82));
  } else {
    ov.setOpacity(0);
    setTimeout(() => map.removeLayer(ov), 500);
  }
}

function buildLayerControl() {
  const list = document.getElementById("layerList");
  list.innerHTML = "";
  SURF.surfaces.forEach((surf, i) => {
    buildSurface(surf);
    const on = i === 0; // EJ wave on by default
    const row = document.createElement("label");
    row.className = "lc-row";
    row.innerHTML = `
      <input type="checkbox" ${on ? "checked" : ""} data-id="${surf.id}" />
      <span class="lc-swatch" style="background:${surf.color}"></span>
      <span class="lc-label">${surf.label}</span>
      <span class="lc-tag ${surf.kind}">${surf.kind}</span>`;
    row.querySelector("input").addEventListener("change", (e) =>
      toggleSurface(surf.id, e.target.checked));
    list.appendChild(row);
    if (on) toggleSurface(surf.id, true);
  });
}

async function loadLayers() {
  try {
    const res = await fetch("/api/surfaces");
    SURF = await res.json();
    buildLayerControl();
  } catch (e) {
    console.warn("surfaces unavailable", e);
  }
}

// ---- init ------------------------------------------------------------------

async function init() {
  const res = await fetch("/api/facilities");
  DATA = await res.json();

  const r0 = DATA.regions[0];
  map = L.map("map").setView([r0.center.lat, r0.center.lng], r0.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  facilityLayer = L.layerGroup().addTo(map);
  drawAllMarkers();

  await loadLayers();

  map.on("click", (e) => selectLocation({ lat: e.latlng.lat, lng: e.latlng.lng }));

  populateControls();

  // Select the first city by default so the user sees the indicator immediately.
  const firstCity = DATA.cities.find((c) => c.region === r0.id);
  if (firstCity) selectLocation({ lat: firstCity.lat, lng: firstCity.lng });
}

init();
