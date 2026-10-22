// Source of Mana x Phaser 3 — mundo completo navegável
// TODOS os 40 mapas do jogo (Overworld, Artis, Candor Cave, Drazil, Tulimshar,
// cavernas, minas, navio...) convertidos por tools/convert_all.py, com os
// warps LIGADOS: andar até um círculo azul troca de mapa, como no original.
//
// Como funciona:
//  * BootScene carrega assets/maps/index.json (nome do mapa -> arquivo),
//    gerado pelo conversor a partir da propriedade "name" de cada .tmx.
//  * WorldScene é genérica: init() recebe {mapId, spawn}; preload() baixa
//    <mapa>.json + <mapa>.manifest.json; create() baixa as imagens dos
//    tilesets daquele mapa e buildWorld() monta camadas/colisão/spawns.
//  * Warp: todo objeto type Warp/Port com dest_map que existe no índice
//    vira uma zona de viagem. dest_pos_x/y * dest_cellsize (ou o tamanho
//    de tile do mapa de destino) = onde você nasce do outro lado.
//    Warps p/ mapas que não existem como .tmx (interiores "001-2-*" das
//    lojas de Artis) aparecem em cinza, só informativos.
//  * Anti-loop: um warp só "arma" depois que você sai do raio dele —
//    nascer em cima do warp de volta nunca te joga de volta na hora.
//
// Mob: Salt Slime (slime.png 468x96, frames 52x24) — recorte de
// presets/entities/sprites/Slime.tscn: Down 0-3 | Left 9-12 | Up 18-21 | Right 27-30

function showError(msg) {
  const el = document.getElementById('error');
  if (el) { el.textContent = '⚠ ' + msg; el.style.display = 'block'; }
  console.error(msg);
}
window.addEventListener('error', e => {
  const where = (e.error && e.error.stack || '').split('\n')[1] || '';
  showError((e.message || 'erro desconhecido') + (where ? ' @ ' + where.trim() : ''));
});

// Onde o jogo começa: costa de Artis no Overworld (perto do "Artis Port")
const CITY_RESPAWN = { mapId: 'tulimshar', spawn: { x: 3056, y: 2096 } }; // Tulimshar, área livre no centro da cidade
const GAME_START = CITY_RESPAWN;

function propsToObj(obj) {
  const out = {};
  for (const p of obj.properties || []) out[p.name] = p.value;
  return out;
}

class BootScene extends Phaser.Scene {
  constructor() { super('boot'); }

  preload() {
    this.load.on('loaderror', file => showError('falha ao carregar ' + file.src));
    const loadingEl = document.getElementById('loading');
    this.load.on('progress', v => {
      if (loadingEl) loadingEl.textContent = `Carregando… ${Math.round(v * 100)}%`;
    });
    this.load.json('map-index', 'assets/maps/index.json');
    // Catálogo de mobs (tools/make_mobs.py): espécie -> sprite/frames/stats
    this.load.json('mob-catalog', 'assets/mobs/catalog.json');
  }

  create() {
    // Índice nome-do-mapa -> {id, tile}: é ele que resolve os dest_map
    this.registry.set('mapIndex', this.cache.json.get('map-index'));
    this.registry.set('mobCatalog', this.cache.json.get('mob-catalog'));
    this.scene.start('world', GAME_START);
  }
}

class WorldScene extends Phaser.Scene {
  constructor() { super('world'); }

  init(data) {
    this.mapId = (data && data.mapId) || CITY_RESPAWN.mapId;
    this.spawnPoint = (data && data.spawn) ||
      (this.mapId === CITY_RESPAWN.mapId ? CITY_RESPAWN.spawn : null);
    this.transitioning = false;
    this.warps = [];
    this.moveTarget = null;
    this.targetMob = null;
    this.backWarp = (data && data.back) || null;
    // Zera TUDO que buildWorld cria: no restart (warp), o update() roda
    // durante o carregamento do novo mapa e, se enxergar o player/mobs
    // destruídos do mapa anterior, quebra (setVelocity sem body) e,
    // pior, mata o loop do jogo (exceção no update para o RAF).
    this.player = null;
    this.playerLabel = null;
    this.cursors = null;
    this.wasd = null;
    this.mobs = null;
    this.map = null;
    this.collisionLayer = null;
    this.targetMarker = null;
  }

  preload() {
    this.load.on('loaderror', file => showError('falha ao carregar ' + file.src));
    this.progressText = this.add.text(480, 290, 'Carregando mapa… 0%', {
      fontSize: '18px', color: '#fff',
      backgroundColor: 'rgba(0,0,0,.6)', padding: { x: 12, y: 8 },
    }).setOrigin(0.5).setScrollFactor(0).setDepth(99);
    this.load.on('progress', v => {
      if (this.progressText) this.progressText.setText(
        `Carregando mapa… ${Math.round(v * 100)}%`);
    });
    this.load.json(`manifest:${this.mapId}`, `assets/maps/${this.mapId}.manifest.json`);
    this.load.tilemapTiledJSON(`map:${this.mapId}`, `assets/maps/${this.mapId}.json`);
    // Cópia bruta do JSON p/ ler as camadas de objetos (warps/spawns) sem
    // depender do formato interno do parser de tilemap do Phaser.
    // SEM ISTO, cache.json.get('raw:...') é undefined e buildWorld quebra.
    this.load.json(`raw:${this.mapId}`, `assets/maps/${this.mapId}.json`);
  }

  create() {
    // Com o manifesto em mãos, enfileira as imagens dos tilesets DESTE mapa
    this.manifest = this.cache.json.get(`manifest:${this.mapId}`);
    for (const ts of this.manifest.tilesets) {
      this.load.image(`ts:${this.mapId}:${ts.key}`, ts.file);
    }
    // Spritesheets só das espécies que spawnam neste mapa (+ a do jogador)
    const catalog = this.registry.get('mobCatalog');
    const raw = this.cache.json.get(`raw:${this.mapId}`);
    const speciesHere = new Set(['Salt Slime']);
    for (const layer of raw.layers) {
      for (const obj of layer.objects || []) {
        if ((obj.type || '').toLowerCase() === 'spawn') speciesHere.add(obj.name);
      }
    }
    this._speciesHere = [...speciesHere];
    for (const name of this._speciesHere) {
      const e = catalog[name];
      if (e && !this.textures.exists(`mob:${e.key}`)) {
        this.load.spritesheet(`mob:${e.key}`, e.file,
          { frameWidth: e.frameWidth, frameHeight: e.frameHeight });
      }
    }
    this.load.once('complete', () => this.buildWorld());
    this.load.start();
  }

  buildWorld() {
    if (this.progressText) { this.progressText.destroy(); this.progressText = null; }
    const loadingEl = document.getElementById('loading');
    if (loadingEl) loadingEl.remove();

    const index = this.registry.get('mapIndex');
    const map = this.make.tilemap({ key: `map:${this.mapId}` });
    this.map = map;
    const tilesets = this.manifest.tilesets.map(ts =>
      map.addTilesetImage(ts.name, `ts:${this.mapId}:${ts.key}`));
    if (tilesets.some(t => t === null)) {
      showError(`tileset não encontrado em ${this.mapId} — rode tools/convert_all.py`);
      return;
    }

    // ---- camadas na ordem do Tiled; Collision invisível; Over por cima ----
    let collisionLayer = null;
    map.layers.forEach((layerData, i) => {
      const name = layerData.name;
      const layer = map.createLayer(name, tilesets, 0, 0);
      if (!layer) return;
      const lower = name.toLowerCase();
      if (lower.startsWith('collision')) {
        layer.setVisible(false).setCollisionByExclusion([-1]);
        layer.setDepth(1);
        collisionLayer = layer;
      } else if (lower.startsWith('over')) {
        layer.setDepth(100 + i); // copas de árvore/telhados acima do jogador
      } else {
        layer.setDepth(i * 2);
      }
    });
    this.collisionLayer = collisionLayer;

    this.physics.world.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    this.cameras.main.fadeIn(250);

    // ---- animações de andar por espécie (frames do catálogo) ----------------
    const catalog = this.registry.get('mobCatalog');
    for (const name of this._speciesHere || ['Salt Slime']) {
      const e = catalog[name];
      if (!e) continue;
      for (const [dir, frames] of Object.entries(e.walk)) {
        const key = `walk-${e.key}-${dir}`;
        if (!this.anims.exists(key)) {
          this.anims.create({
            key,
            frames: frames.map(f => ({ key: `mob:${e.key}`, frame: f })),
            frameRate: 7, repeat: -1,
          });
        }
      }
    }
    // Escala p/ o sprite caber no mundo: ~34px de largura em mapa de
    // tile 16, ~54px em tile 32, sem estourar 2,4 tiles de altura.
    this.mobScaleFor = e => Math.min(
      (tile <= 16 ? 34 : 54) / e.frameWidth,
      (tile * 2.4) / e.frameHeight);

    // ---- jogador --------------------------------------------------------------
    const tile = map.tileWidth;
    const start = this.findWalkable(
      this.spawnPoint ? this.spawnPoint.x : map.widthInPixels / 2,
      this.spawnPoint ? this.spawnPoint.y : map.heightInPixels / 2);

    this.entryStart = { x: start.x, y: start.y };
    const playerEntry = catalog['Salt Slime'];
    this.player = this.physics.add.sprite(start.x, start.y,
      `mob:${playerEntry.key}`, playerEntry.walk.down[0]);
    this.player.setDepth(50).setScale(this.mobScaleFor(playerEntry)).setTint(0xffe08a);
    this.player.setData('animPrefix', `walk-${playerEntry.key}`);
    this.player.body.setSize(playerEntry.frameWidth * 0.5, playerEntry.frameHeight * 0.4)
      .setOffset(playerEntry.frameWidth * 0.25, playerEntry.frameHeight * 0.55);
    this.player.setCollideWorldBounds(true);
    if (collisionLayer) this.physics.add.collider(this.player, collisionLayer);
    this.cameras.main.startFollow(this.player, true, 0.12, 0.12);
    this.cameras.main.setZoom(tile <= 16 ? 2.4 : 1.6);

    this.playerLabel = this.add.text(0, 0, 'Você (um slime)', {
      fontSize: '11px', color: '#ffe08a',
      backgroundColor: 'rgba(0,0,0,.45)', padding: { x: 4, y: 2 },
    }).setDepth(61).setOrigin(0.5, 1);
    this.playerLabel.setPosition(start.x, start.y - 16);

    // ---- objetos do TMX: warps (viagem) + spawns (mobs) -----------------------
    const rawMap = this.cache.json.get(`raw:${this.mapId}`);
    this.warps = [];
    const spawnObjects = [];
    for (const layer of rawMap.layers) {
      if (layer.type !== 'objectgroup') continue;
      for (const obj of layer.objects || []) {
        const type = (obj.type || '').toLowerCase();
        const props = propsToObj(obj);
        if (type === 'warp' || type === 'port') {
          const destName = props.dest_map || props.map;
          const destEntry = destName ? index[destName] : null;
          const cell = parseInt(props.dest_cellsize, 10) ||
            (destEntry ? destEntry.tile : tile);
          const warp = {
            name: obj.name || destName || 'Warp',
            x: obj.x + (obj.width || 0) / 2,
            y: obj.y + (obj.height || 0) / 2,
            r: Math.max(22, tile * 0.8),
            destName,
            destId: destEntry ? destEntry.id : null,
            spawn: null, // resolvido logo abaixo
            _props: props,
            armed: true,
          };
          // Spawn no destino: portais modernos usam dest_pos_x/y; as
          // portas legadas de Artis (prop "map" = 001-2-*) apontam p/
          // interiores gerados, cujo spawn vem do indice de mapas.
          {
            const txv = props.dest_pos_x !== undefined ? props.dest_pos_x : props.dest_x;
            const tyv = props.dest_pos_y !== undefined ? props.dest_pos_y : props.dest_y;
            if (destEntry && !props.dest_map && destEntry.spawn) {
              warp.spawn = destEntry.spawn;
            } else if (destEntry && txv !== undefined && tyv !== undefined) {
              warp.spawn = { x: parseInt(txv, 10) * cell, y: parseInt(tyv, 10) * cell };
            }
            // Saida de interior volta p/ a porta exata de onde voce entrou
            if (this.backWarp && this.mapId.startsWith('interior-') &&
                warp.destId === this.backWarp.mapId) {
              warp.spawn = this.backWarp.spawn;
            }
          }
          // Anti-loop: se já nascer em cima deste warp, ele começa desarmado
          warp.armed = Phaser.Math.Distance.Between(start.x, start.y, warp.x, warp.y) > warp.r + 18;
          this.warps.push(warp);

          const functional = !!warp.destId;
          const g = this.add.graphics().setDepth(60);
          g.lineStyle(3, functional ? 0x66d9ff : 0x888888, 0.95)
            .strokeCircle(warp.x, warp.y, warp.r * 0.55);
          g.fillStyle(functional ? 0x66d9ff : 0x888888, 0.25)
            .fillCircle(warp.x, warp.y, warp.r * 0.55);
          this.add.text(warp.x, warp.y - warp.r - 6,
            functional ? `${warp.name} → ${destName}` : `${warp.name} (interior não incluído)`, {
              fontSize: '11px', color: functional ? '#aee6ff' : '#aaaaaa',
              backgroundColor: 'rgba(0,0,0,.45)', padding: { x: 4, y: 2 },
            }).setDepth(61).setOrigin(0.5);
        } else if (type === 'spawn') {
          spawnObjects.push({ obj, props });
        }
      }
    }

    // ---- mobs: dos objetos Spawn do próprio mapa ------------------------------
    this.mobs = this.physics.add.group();
    const addMob = (speciesName, x, y) => {
      const e = catalog[speciesName] || catalog['Salt Slime'];
      const spot = this.findWalkable(x, y);
      const mob = this.mobs.create(spot.x, spot.y, `mob:${e.key}`, e.walk.down[0]);
      mob.setDepth(50).setScale(this.mobScaleFor(e));
      mob.body.setSize(e.frameWidth * 0.5, e.frameHeight * 0.4)
        .setOffset(e.frameWidth * 0.25, e.frameHeight * 0.55);
      mob.setCollideWorldBounds(true);
      mob.setData({
        species: speciesName, hp: e.hp, maxHp: e.hp,
        level: e.level, animPrefix: `walk-${e.key}`,
        wanderSpeed: Phaser.Math.Clamp(e.walkSpeed * 0.45, 16, 65),
        home: { x: spot.x, y: spot.y }, nextTurn: 0,
      });
      mob.setInteractive({ useHandCursor: true });
    };
    let mobCount = 0;
    for (const { obj, props } of spawnObjects) {
      if (props.type && String(props.type).toLowerCase() !== 'monster') continue;
      const n = Math.min(parseInt(props.count, 10) || 1, 3);
      for (let i = 0; i < n && mobCount < 18; i++, mobCount++) {
        addMob(obj.name, (obj.x || 0) + Phaser.Math.Between(-64, 64),
               (obj.y || 0) + Phaser.Math.Between(-64, 64));
      }
    }
    // Sem fallback inventado: mapa sem Spawn no original (Overworld,
    // interiores) fica sem mobs mesmo — mob só onde o jogo original põe.
    if (collisionLayer) {
      this.physics.add.collider(this.mobs, collisionLayer);
      // Sem collider player x mobs de proposito: slime perambulando
      // encurralava o jogador contra paredes e o prendia.
    }
    this.physics.add.collider(this.mobs, this.mobs);

    // ---- entrada do usuário: teclado + TOQUE (Android) ----------------------
    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys('W,A,S,D');
    this.lastTargetDist = Infinity;
    this.targetStuckSince = 0;
    this.targetMarker = this.add.circle(0, 0, 8, 0xffe08a, 0.35)
      .setStrokeStyle(2, 0xffe08a, 0.9).setDepth(59).setVisible(false);

    this.input.on('gameobjectdown', (_pointer, mob) => this.orderAttack(mob));
    this.input.on('pointerdown', pointer => {
      const wx = pointer.worldX, wy = pointer.worldY;
      let nearest = null, nearestDist = 48;
      for (const mob of this.mobs.getChildren()) {
        if (!mob.active) continue;
        const d = Phaser.Math.Distance.Between(wx, wy, mob.x, mob.y);
        if (d < nearestDist) { nearestDist = d; nearest = mob; }
      }
      if (nearest) { this.orderAttack(nearest); return; }
      const spot = this.findWalkable(wx, wy);
      this.moveTarget = spot;
      this.targetMob = null;
      this.lastTargetDist = Infinity;
      this.targetMarker.setPosition(spot.x, spot.y).setVisible(true);
    });
    this.input.on('wheel', (_p, _o, _dx, dy) => {
      const cam = this.cameras.main;
      cam.setZoom(Phaser.Math.Clamp(cam.zoom - Math.sign(dy) * 0.2, 0.3, 4));
    });
    if (!this._zoomListener) {
      this._zoomListener = true;
      window.addEventListener('demo-zoom', e => {
        if (!this.cameras) return;
        const cam = this.cameras.main;
        cam.setZoom(Phaser.Math.Clamp(cam.zoom + e.detail, 0.3, 4));
      });
    }

    if (!this._unstickListener) {
      this._unstickListener = true;
      window.addEventListener('demo-unstick', () => this.unstick());
    }

    const functionalWarps = this.warps.filter(w => w.destId).length;
    this.add.text(10, 10,
      `📍 ${this.manifest.name} — ${map.width}x${map.height} tiles · ` +
      `${functionalWarps} saída(s) neste mapa\n` +
      `Ande até um círculo azul p/ viajar · toque no chão p/ andar · toque num slime p/ atacar`, {
        fontSize: '13px', color: '#fff',
        backgroundColor: 'rgba(0,0,0,.5)', padding: { x: 8, y: 6 },
      }).setScrollFactor(0).setDepth(70);
  }

  // Tile andável (sem colisão) mais próximo de (x, y), em passos de 1 tile.
  findWalkable(x, y) {
    const step = this.map.tileWidth;
    x = Phaser.Math.Clamp(x, step, this.map.widthInPixels - step);
    y = Phaser.Math.Clamp(y, step, this.map.heightInPixels - step);
    if (!this.collisionLayer) return { x, y };
    for (let r = 0; r < 60; r++) {
      for (let dx = -r; dx <= r; dx++) {
        for (let dy = -r; dy <= r; dy++) {
          const wx = x + dx * step, wy = y + dy * step;
          if (wx < 0 || wy < 0 || wx >= this.map.widthInPixels || wy >= this.map.heightInPixels) continue;
          const tile = this.collisionLayer.getTileAtWorldXY(wx, wy);
          if (!tile || tile.index === -1) return { x: wx, y: wy };
        }
      }
    }
    return { x, y };
  }

  doWarp(warp) {
    this.transitioning = true;
    this.player.setVelocity(0, 0);
    this.cameras.main.fadeOut(220, 0, 0, 0);
    this.time.delayedCall(240, () => {
      this.scene.restart({
        mapId: warp.destId,
        spawn: warp.spawn,
        // Entrando num interior: lembra a porta de origem p/ a saida
        // devolver voce exatamente nela (e nao numa porta qualquer).
        back: warp.destId && warp.destId.startsWith('interior-')
          ? { mapId: this.mapId,
              spawn: { x: warp.x, y: warp.y + this.map.tileWidth } }
          : null,
      });
    });
  }

  // Teleporta p/ o centro do tile andavel mais proximo (anel crescente).
  // Se apertar Desprender 2x em menos de 4s, volta p/ a entrada do mapa.
  unstick() {
    if (!this.player || !this.player.body) return;
    const now = this.time.now;
    const goEntry = this.lastUnstick && (now - this.lastUnstick) < 4000 && this.entryStart;
    this.lastUnstick = now;
    let dest = null;
    if (goEntry) {
      dest = this.findWalkable(this.entryStart.x, this.entryStart.y);
    } else {
      const step = this.map.tileWidth;
      outer:
      for (let r = 1; r <= 8; r++) {
        for (let dx = -r; dx <= r; dx++) {
          for (let dy = -r; dy <= r; dy++) {
            const cx = this.player.x + dx * step, cy = this.player.y + dy * step;
            const tile = this.collisionLayer
              ? this.collisionLayer.getTileAtWorldXY(cx, cy) : null;
            if (!tile || tile.index === -1) { dest = { x: cx, y: cy }; break outer; }
          }
        }
      }
      if (!dest && this.entryStart) dest = this.findWalkable(this.entryStart.x, this.entryStart.y);
    }
    if (!dest) return;
    this.player.body.reset(dest.x, dest.y);
    this.player.setVelocity(0, 0);
    this.moveTarget = null; this.targetMob = null;
    if (this.targetMarker) this.targetMarker.setVisible(false);
    this.stuckSince = 0;
  }

  // Toque/clique num slime: se estiver longe, persegue; perto, ataca.
  orderAttack(mob) {
    if (!mob.active) return;
    if (Phaser.Math.Distance.BetweenPoints(this.player, mob) <= 62) {
      this.attack(mob);
      this.targetMob = null;
      return;
    }
    this.targetMob = mob;
    this.moveTarget = null;
    this.targetMarker.setPosition(mob.x, mob.y).setVisible(true);
  }

  attack(mob) {
    if (Phaser.Math.Distance.BetweenPoints(this.player, mob) > 70) {
      this.cameras.main.shake(60, 0.0015);
      return;
    }
    const hp = mob.getData('hp') - 10;
    mob.setData('hp', hp);
    mob.setTintFill(0xffffff);
    this.time.delayedCall(90, () => mob.clearTint());
    if (hp > 0) return;
    mob.disableBody(true, true);
    this.time.delayedCall(3000, () => {
      const home = mob.getData('home');
      const spot = home || this.findWalkable(this.player.x, this.player.y);
      mob.enableBody(true, spot.x, spot.y, true, true);
      mob.setData('hp', mob.getData('maxHp') || 30);
    });
  }

  update(time) {
    // Guarda dura: se buildWorld falhar no meio (asset, parse etc.), o
    // update NÃO pode virar uma cascata de erros novos (era o tal
    // "reading 'left'": player existia, this.cursors ainda não).
    if (!this.player || !this.player.body || !this.cursors || !this.mobs) return;
    const p = this.player;
    if (this.playerLabel) this.playerLabel.setPosition(p.x, p.y - 16);
    const speed = this.map.tileWidth <= 16 ? 150 : 210;
    // Posição p/ o ponto amarelo do minimapa (controls.js lê isto)
    window.playerWorld = {
      x: p.x, y: p.y,
      w: this.map.widthInPixels, h: this.map.heightInPixels,
      mapId: this.mapId,
    };
    let vx = 0, vy = 0;

    if (!this.transitioning) {
      // Warps: viajar ao encostar no TILE do warp (portos ficam em tiles
      // de colisao/caís, o centro nunca e alcancavel a pe). Anti-loop:
      // so arma depois de se afastar do tile.
      const half = this.map.tileWidth / 2;
      for (const warp of this.warps) {
        if (!warp.destId) continue;
        const dx = Math.max(Math.abs(p.x - warp.x) - half, 0);
        const dy = Math.max(Math.abs(p.y - warp.y) - half, 0);
        const d = Math.hypot(dx, dy);
        if (d > warp.r + 18) warp.armed = true;
        else if (warp.armed && d <= warp.r * 0.75) { this.doWarp(warp); break; }
      }
    }

    if (!this.transitioning) {
      // 1) teclado (PC)
      if (this.cursors.left.isDown || this.wasd.A.isDown) vx = -speed;
      else if (this.cursors.right.isDown || this.wasd.D.isDown) vx = speed;
      if (this.cursors.up.isDown || this.wasd.W.isDown) vy = -speed;
      else if (this.cursors.down.isDown || this.wasd.S.isDown) vy = speed;
      if (vx !== 0 || vy !== 0) { this.moveTarget = null; this.targetMob = null; this.targetMarker.setVisible(false); }

      // 2) joystick virtual (Android)
      const tv = window.touchVector;
      if (tv && (Math.abs(tv.x) > 0.12 || Math.abs(tv.y) > 0.12)) {
        vx = tv.x * speed; vy = tv.y * speed;
        this.moveTarget = null; this.targetMob = null; this.targetMarker.setVisible(false);
      }

      // 3) toque num slime: persegue e ataca ao encostar
      if (vx === 0 && vy === 0 && this.targetMob) {
        const mob = this.targetMob;
        if (!mob.active) { this.targetMob = null; this.targetMarker.setVisible(false); }
        else {
          const d = Phaser.Math.Distance.BetweenPoints(p, mob);
          this.targetMarker.setPosition(mob.x, mob.y);
          if (d <= 58) {
            this.attack(mob);
            this.targetMob = null;
            this.targetMarker.setVisible(false);
          } else {
            const a = Math.atan2(mob.y - p.y, mob.x - p.x);
            vx = Math.cos(a) * speed; vy = Math.sin(a) * speed;
          }
        }
      }

      // 4) toque no chão: anda até o marcador; desiste se travar
      if (vx === 0 && vy === 0 && this.moveTarget) {
        const t = this.moveTarget;
        const d = Phaser.Math.Distance.Between(p.x, p.y, t.x, t.y);
        if (d < 8) {
          this.moveTarget = null; this.targetMarker.setVisible(false);
        } else {
          if (d > this.lastTargetDist - 1) {
            if (!this.targetStuckSince) this.targetStuckSince = time;
            if (time - this.targetStuckSince > 900) {
              this.moveTarget = null; this.targetMarker.setVisible(false); this.targetStuckSince = 0;
            }
          } else { this.targetStuckSince = 0; }
          this.lastTargetDist = d;
          if (this.moveTarget) {
            const a = Math.atan2(t.y - p.y, t.x - p.x);
            vx = Math.cos(a) * speed; vy = Math.sin(a) * speed;
          }
        }
      }
    }

    p.setVelocity(vx, vy);
    this.playWalk(p, vx, vy);

    // Anti-travamento: comandou andar mas o corpo quase nao sai do lugar
    // (encravado em quina de parede) por >1s -> desprende sozinho.
    const commanded = Math.hypot(vx, vy);
    const actual = Math.hypot(p.body.velocity.x, p.body.velocity.y);
    if (commanded > 0 && actual < commanded * 0.2) {
      if (!this.stuckSince) this.stuckSince = time;
      if (time - this.stuckSince > 1000) { this.unstick(); }
    } else {
      this.stuckSince = 0;
    }

    for (const mob of this.mobs.getChildren()) {
      if (!mob.active) continue;
      if (time > mob.getData('nextTurn')) {
        mob.setData('nextTurn', time + Phaser.Math.Between(1500, 3500));
        const angle = Phaser.Math.FloatBetween(0, Math.PI * 2);
        const sp = (mob.getData('wanderSpeed') || 40) * Phaser.Math.FloatBetween(0.7, 1.1);
        mob.setVelocity(Math.cos(angle) * sp, Math.sin(angle) * sp);
      }
      this.playWalk(mob, mob.body.velocity.x, mob.body.velocity.y);
    }
  }

  playWalk(sprite, vx, vy) {
    const prefix = sprite.getData('animPrefix');
    if (!prefix || (vx === 0 && vy === 0)) { sprite.anims.stop(); return; }
    const dir = Math.abs(vx) > Math.abs(vy)
      ? (vx > 0 ? 'right' : 'left')
      : (vy > 0 ? 'down' : 'up');
    const key = `${prefix}-${dir}`;
    if (this.anims.exists(key)) sprite.anims.play(key, true);
    else sprite.anims.stop();
  }
}

new Phaser.Game({
  // CANVAS (e não WebGL): elimina a classe inteira de "tela preta" em
  // navegadores/previews com WebGL bloqueado, e basta p/ pixel art 2D.
  type: Phaser.CANVAS,
  parent: 'game',
  scale: {
    mode: Phaser.Scale.FIT,       // encolhe p/ caber na tela do celular
    autoCenter: Phaser.Scale.CENTER_BOTH,
    width: 960,
    height: 600,
  },
  backgroundColor: '#1d5c2e',
  pixelArt: true,
  physics: { default: 'arcade', arcade: { debug: false } },
  scene: [BootScene, WorldScene],
});
