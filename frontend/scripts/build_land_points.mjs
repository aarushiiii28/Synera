import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { geoContains } from 'd3-geo';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const landGeojsonPath = path.join(__dirname, '../data/reference/ne_110m_admin_0_countries.geojson');
const outPath = path.join(__dirname, '../frontend/public/land_points.bin');

const landGeojson = JSON.parse(fs.readFileSync(landGeojsonPath, 'utf8'));

const numCandidates = 60000;
const validPoints = [];

for (let i = 0; i < numCandidates; i++) {
  const y = 1 - (i / (numCandidates - 1)) * 2;
  const radius = Math.sqrt(1 - y * y);
  const theta = 2.39996322972865332 * i;

  const x = Math.cos(theta) * radius;
  const z = Math.sin(theta) * radius;

  // convert to lat/lon
  const lat = Math.asin(y) * (180 / Math.PI);
  const lon = Math.atan2(z, x) * (180 / Math.PI);

  // Use the standard rotation that our globe uses (actually our globe is rotated differently, 
  // but geoContains expects [lon, lat])
  
  const inLand = landGeojson.features.some((f) => geoContains(f, [lon, lat]));
  if (inLand) {
    // The globe is rendered with right-handed Y-up, and the sphere uses:
    // x = cos(lat)*sin(lon)
    // y = sin(lat)
    // z = cos(lat)*cos(lon)
    const latRad = lat * (Math.PI / 180);
    const lonRad = lon * (Math.PI / 180);
    
    validPoints.push(
      Math.cos(latRad) * Math.sin(lonRad),
      Math.sin(latRad),
      Math.cos(latRad) * Math.cos(lonRad)
    );
  }
}

const arr = new Float32Array(validPoints);
fs.writeFileSync(outPath, Buffer.from(arr.buffer));
console.log(`Generated ${arr.length / 3} land points`);
