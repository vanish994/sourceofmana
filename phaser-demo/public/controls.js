// Controles touch (Android/iOS): joystick virtual + botoes de zoom.
// Expõe window.touchVector {x,y} em -1..1, lido pelo main.js a cada frame.
(function () {
  window.touchVector = { x: 0, y: 0 };

  const joy = document.getElementById('joy');
  const thumb = document.getElementById('joy-thumb');
  if (!joy || !thumb) return;

  // Mostra os controles em qualquer aparelho com toque, mesmo se a
  // media query (pointer: coarse) nao casar (alguns Android reportam fine).
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    joy.style.display = 'block';
    const zb = document.getElementById('zoom-btns');
    if (zb) zb.style.display = 'flex';
  }

  const RADIUS = 44; // px maximos que o thumb desloca do centro
  let pointerId = null;

  function setThumb(dx, dy) {
    thumb.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
    window.touchVector.x = dx / RADIUS;
    window.touchVector.y = dy / RADIUS;
  }

  function handleMove(e) {
    const rect = joy.getBoundingClientRect();
    let dx = e.clientX - (rect.left + rect.width / 2);
    let dy = e.clientY - (rect.top + rect.height / 2);
    const len = Math.hypot(dx, dy);
    if (len > RADIUS) { dx = dx / len * RADIUS; dy = dy / len * RADIUS; }
    // zona morta pequena p/ nao andar sozinho com o dedo parado no centro
    if (Math.hypot(dx, dy) < 8) { dx = 0; dy = 0; }
    setThumb(dx, dy);
  }

  joy.addEventListener('pointerdown', e => {
    pointerId = e.pointerId;
    joy.setPointerCapture(pointerId);
    handleMove(e);
    e.preventDefault();
  });
  joy.addEventListener('pointermove', e => {
    if (e.pointerId === pointerId) handleMove(e);
  });
  const release = e => {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
    setThumb(0, 0);
  };
  joy.addEventListener('pointerup', release);
  joy.addEventListener('pointercancel', release);

  // Botoes de zoom: o main.js escuta este evento e ajusta a camera.
  const bindZoom = (id, delta) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', () =>
      window.dispatchEvent(new CustomEvent('demo-zoom', { detail: delta })));
  };
  bindZoom('zoom-in', 0.3);
  bindZoom('zoom-out', -0.3);

  // Botao Desprender: o jogo escuta e teleporta p/ um tile livre
  // (2 toques seguidos = volta para a entrada do mapa).
  const unstickBtn = document.getElementById('unstick-btn');
  if (unstickBtn) unstickBtn.addEventListener('click', () =>
    window.dispatchEvent(new CustomEvent('demo-unstick')));

  // Botao "Mapa": abre/fecha o mapa-mundi inteiro (imagem gerada dos
  // dados do mapa por tools/make_minimap.js) com um ponto na posicao
  // atual do jogador, publicada pelo main.js em window.playerWorld.
  const mapBtn = document.getElementById('map-btn');
  const wrap = document.getElementById('minimap-wrap');
  const dot = document.getElementById('player-dot');
  const img = document.getElementById('minimap');
  if (mapBtn && wrap && dot && img) {
    const setMapOpen = open => { wrap.style.display = open ? 'flex' : 'none'; };
    mapBtn.addEventListener('click', () => setMapOpen(wrap.style.display === 'none'));
    // Fechar: botao X dentro do painel, toque fora da imagem, ou no 🗺
    // (o botao 🗺 tem z-index maior que o painel, continua clicavel)
    const closeBtn = document.getElementById('minimap-close');
    if (closeBtn) closeBtn.addEventListener('click', () => setMapOpen(false));
    wrap.addEventListener('click', e => { if (e.target === wrap) setMapOpen(false); });
    setInterval(() => {
      if (wrap.style.display === 'none' || !window.playerWorld) return;
      // O minimapa é o Overworld; dentro de cidade/caverna o ponto some
      dot.style.display = window.playerWorld.mapId === 'overworld' ? 'block' : 'none';
      if (window.playerWorld.mapId !== 'overworld') return;
      const r = img.getBoundingClientRect();
      const w = wrap.getBoundingClientRect();
      const pw = window.playerWorld;
      dot.style.left = (r.left - w.left + (pw.x / pw.w) * r.width) + 'px';
      dot.style.top = (r.top - w.top + (pw.y / pw.h) * r.height) + 'px';
    }, 250);
  }
})();
