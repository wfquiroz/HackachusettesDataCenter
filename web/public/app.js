// HourMatch — emissions map (Leaflet + OpenStreetMap, no API key)

const EMISSION_COLORS = {
  high: "#e4572e",
  medium: "#f3c13a",
  low: "#3cb371",
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

function levelFor(tco2e) {
  const t = DATA.thresholds;
  if (tco2e <= t.low_max) return "low";
  if (tco2e <= t.medium_max) return "medium";
  return "high";
}

function levelLabel(level) {
  return { high: "High", medium: "Medium", low: "Low" }[level];
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
  return `
    <div class="pop-title">${f.name}</div>
    <div class="pop-meta">${f.type === "data_center" ? "Data center" : "Industry"} · ${f.city}</div>
    <div><span class="pill ${level}">${levelLabel(level)}</span>
      &nbsp;<b>${fmt(f.emissions_tco2e)}</b> tCO₂e/yr</div>
    <div class="pop-meta" style="margin-top:4px">${src}</div>
  `;
}

function drawAllMarkers() {
  facilityLayer.clearLayers();
  DATA.facilities.forEach((f) => {
    const level = levelFor(f.emissions_tco2e);
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
    const level = levelFor(f.emissions_tco2e);
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="row">
        <span class="pill ${level}">${levelLabel(level)}</span>
        <span class="name">${f.name}</span>
        <span class="badge-type">${f.type === "data_center" ? "data center" : "industry"}</span>
      </div>
      <div class="meta">${f.city} · ${d.toFixed(1)} km away · ${f.status}</div>
      <div class="value"><b>${fmt(f.emissions_tco2e)}</b> tCO₂e / year</div>
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

  map.on("click", (e) => selectLocation({ lat: e.latlng.lat, lng: e.latlng.lng }));

  populateControls();

  // Select the first city by default so the user sees the indicator immediately.
  const firstCity = DATA.cities.find((c) => c.region === r0.id);
  if (firstCity) selectLocation({ lat: firstCity.lat, lng: firstCity.lng });
}

init();
