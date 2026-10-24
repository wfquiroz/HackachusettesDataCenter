const path = require("path");
const fs = require("fs");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 5173;

const publicDir = path.join(__dirname, "public");
const facilitiesFile = path.join(__dirname, "facilities.json");
const layersFile = path.join(__dirname, "layers.json");

// API: facilities + regions + cities + thresholds
app.get("/api/facilities", (req, res) => {
  fs.readFile(facilitiesFile, "utf8", (err, raw) => {
    if (err) {
      console.error("Failed to read facilities.json:", err.message);
      return res.status(500).json({ error: "facilities data unavailable" });
    }
    try {
      res.type("application/json").send(raw);
    } catch (e) {
      res.status(500).json({ error: "facilities data malformed" });
    }
  });
});

// API: toggleable impact layers (noise, air, water, energy use/output)
app.get("/api/layers", (req, res) => {
  fs.readFile(layersFile, "utf8", (err, raw) => {
    if (err) return res.status(500).json({ error: "layers data unavailable" });
    res.type("application/json").send(raw);
  });
});

// API: statewide smooth impact surfaces (the pollution wave)
app.get("/api/surfaces", (req, res) => {
  fs.readFile(path.join(__dirname, "surfaces.json"), "utf8", (err, raw) => {
    if (err) return res.status(500).json({ error: "surfaces data unavailable" });
    res.type("application/json").send(raw);
  });
});

// API: MassGIS Protected & Recreational OpenSpace proxy (public state data).
// bbox=minLon,minLat,maxLon,maxLat -> GeoJSON polygons; point=lon,lat -> on_protected check.
app.get("/api/openspace", async (req, res) => {
  const BASE = "https://gis.eea.mass.gov/server/rest/services/" +
    "Protected_and_Recreational_OpenSpace_Polygons/MapServer/0/query";
  try {
    let url;
    if (req.query.point) {
      const [lon, lat] = String(req.query.point).split(",");
      url = `${BASE}?geometry=${lon},${lat}&geometryType=esriGeometryPoint&inSR=4326` +
        `&spatialRel=esriSpatialRelIntersects&outFields=SITE_NAME,PRIM_PURP,OWNER_TYPE,LEV_PROT` +
        `&returnGeometry=false&f=json`;
      const r = await fetch(url);
      const data = await r.json();
      const feats = data.features || [];
      return res.json({
        on_protected: feats.length > 0,
        sites: feats.slice(0, 5).map((f) => f.attributes || {}),
      });
    }
    const bbox = req.query.bbox || "-73.51,41.18,-69.90,42.89";
    url = `${BASE}?geometry=${bbox}&geometryType=esriGeometryEnvelope&inSR=4326` +
      `&spatialRel=esriSpatialRelIntersects&outFields=SITE_NAME,PRIM_PURP,LEV_PROT` +
      `&returnGeometry=true&outSR=4326&resultRecordCount=2000&f=geojson`;
    const r = await fetch(url);
    const body = await r.text();
    res.type("application/json").send(body);
  } catch (e) {
    res.status(502).json({ error: String(e) });
  }
});

// Simple health check (handy for Docker)
app.get("/healthz", (req, res) => res.json({ ok: true }));

// Static frontend
app.use(express.static(publicDir));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`HourMatch map running at http://localhost:${PORT}`);
});
