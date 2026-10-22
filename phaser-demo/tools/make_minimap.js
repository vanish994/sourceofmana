// Gera public/assets/minimap.png renderizando todas as camadas do
// overworld.json (2px por tile). Uso (dev):  npm i pngjs --no-save
//   node tools/make_minimap.js

const fs = require('fs');
const { PNG } = require('pngjs');
const root = require('path').join(__dirname, '..', 'public') + '/';
const map = JSON.parse(fs.readFileSync(root + 'assets/maps/overworld.json'));
const S = 2; // px por tile no minimapa -> 770x580
const out = new PNG({ width: map.width * S, height: map.height * S });
const imgs = {};
for (const t of map.tilesets) imgs[t.name] = PNG.sync.read(fs.readFileSync(root + t.image.replace('../', 'assets/')));
function tilesetFor(gid) { return [...map.tilesets].reverse().find(t => gid >= t.firstgid && gid < t.firstgid + t.tilecount); }
for (const layer of map.layers) {
  if (!layer.data) continue;
  if (layer.name === 'Collision') continue;
  for (let y = 0; y < map.height; y++) for (let x = 0; x < map.width; x++) {
    const gid = layer.data[y * map.width + x];
    if (!gid) continue;
    const t = tilesetFor(gid); if (!t) continue;
    const img = imgs[t.name]; const id = gid - t.firstgid;
    const tx = (id % t.columns) * t.tilewidth, ty = Math.floor(id / t.columns) * t.tileheight;
    for (let dy = 0; dy < S; dy++) for (let dx = 0; dx < S; dx++) {
      const si = ((ty + Math.floor(dy * t.tileheight / S)) * img.width + tx + Math.floor(dx * t.tilewidth / S)) * 4;
      if (img.data[si + 3] < 128) continue;
      const di = ((y * S + dy) * out.width + (x * S + dx)) * 4;
      out.data[di] = img.data[si]; out.data[di+1] = img.data[si+1]; out.data[di+2] = img.data[si+2]; out.data[di+3] = 255;
    }
  }
}
fs.writeFileSync(root + 'assets/minimap.png', PNG.sync.write(out));
console.log('minimapa gerado:', out.width + 'x' + out.height);
