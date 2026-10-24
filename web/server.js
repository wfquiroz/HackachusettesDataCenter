const path = require("path");
const fs = require("fs");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 5173;

const publicDir = path.join(__dirname, "public");
const facilitiesFile = path.join(__dirname, "facilities.json");

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

// Simple health check (handy for Docker)
app.get("/healthz", (req, res) => res.json({ ok: true }));

// Static frontend
app.use(express.static(publicDir));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`HourMatch map running at http://localhost:${PORT}`);
});
