# Análise do demo Phaser × Source of Mana

*Estado atual: POC navegável — 40 mapas convertidos + 18 interiores gerados,
warps funcionais, controles touch, 1 mob. Código: ~580 linhas em
`public/main.js` + ~100 em `controls.js`. Assets gerados: 31,9 MB.
Tudo ainda **não commitado** (`git status` mostra `?? phaser-demo/`).*

## Notas por área

| Área | Nota | Resumo |
|---|---|---|
| Mundo / navegação | 8/10 | 58 mapas no índice, warps ida-e-volta testados, anti-loop e anti-travamento funcionam |
| Combate / gameplay | 3/10 | Clicar-e-matar sem risco: sem HP do jogador, XP, aggro ou animação de ataque |
| Conteúdo aproveitado | 3/10 | 32 espécies spawnam, todas com sprite de slime; NPCs, músicas e sons ignorados |
| Performance mobile | 5/10 | JSON baixado 2× por mapa, zoom-out caro no Canvas, sem compressão |
| UX Android | 6/10 | Joystick + tap-to-move funcionam, mas sem pathfinding o toque "anda em linha reta até a parede" |
| Arquitetura | 5/10 | Monolito de 580 linhas, globais `window.*`, estado some a cada troca de mapa |
| Documentação | 6/10 | README rico, mas trechos velhos ("sem minimapa", "marcadores visuais") |

## Achados principais (com evidência)

### Performance / carregamento
1. **Download dobrado por mapa.** `preload()` baixa o mesmo arquivo duas
   vezes (`tilemapTiledJSON` + `raw:` como JSON) — Overworld são
   2,16 MB × 2, Artis 1,37 MB × 2. Os objetos (warps/spawns) podem sair
   do tilemap já parseado pelo Phaser. **~50% de banda e parse a menos.**
2. **18,3 MB de JSON sem compressão.** Arrays CSV de inteiros comprimem
   ~90% com gzip. Hoje o `http.server`/hospedagem não comprime nada.
3. **Zoom-out caro.** No zoom 0.3, o renderer Canvas desenha ~200×125
   tiles × ~5 camadas por frame só no Overworld — é o maior risco de
   travamento no Android. Limitar o zoom mínimo por mapa (ou manter o
   minimapa como a forma de "ver tudo") resolve.
4. **`findWalkable` é uma espiral O(r²)** chamada a cada spawn/toque
   (até ~14 mil testes de tile). Funciona, mas uma BFS limitada é mais
   barata e acha o tile certo mais rápido.
5. Listeners de `progress`/`loaderror` são **registrados de novo a cada
   reinício de cena** — vazamento pequeno, mas cresce a cada warp.

### Conteúdo subaproveitado (o maior desperdício)
6. **32 espécies distintas** aparecem nos objetos Spawn dos mapas
   (Sand Snake ×27, Scorpion ×27, Maggot ×23, Sea Slime, Peyote, Croc,
   Bat, Fire Goblin...) e **todas viram slime**. Existem 29 sprites de
   monstro em `data/graphics/sprites/monsters/` e as fichas de recorte
   em `presets/entities/sprites/*.tscn` (mesmo formato do Slime).
7. **93 fichas de entidade** (`presets/entities/*.tres`) têm HP, nível,
   velocidade, EXP, skills e drops prontos — o demo usa HP fixo 30.
8. **NPCs ignorados:** 40+ nomes (`Gabz`, `Nard`, `Peter`, guardas de
   Tulimshar, `Well` ×11, baús...) com sprite próprio em
   `data/graphics/sprites/npcs/`, nenhum renderizado.
9. **Áudio zerado:** cada `.tmx` declara sua música (`music=Adventure
   Begins`, `Foreboding`...) e há 42 sons de entidades — nenhum toca.
10. As animações de **ataque** já existem nas sheets (frames Attack nas
    4 direções) e não são usadas; o ataque atual é só um flash branco.

### Gameplay
11. **Tap-to-move sem pathfinding** é a causa raiz dos "fiquei preso":
    o jogador anda em linha reta e para na parede (o Desprender é um
    remendo). A* sobre a grade de colisão (a camada já existe) elimina
    a classe inteira do problema — e permite tocar num warp distante
    e ir sozinho.
12. **Sem consequência:** jogador não tem HP, não morre, mob morto
    renasce em 2s do lado do jogador. Sem XP/nível, matar é decorativo.
13. **Estado volátil:** `scene.restart` apaga tudo — mobs mortos voltam,
    posição só se mantém via spawn do warp. Sem save (nem `localStorage`).
14. Overworld a pé é lento (150 px/s num mundo de 6160 px ≈ 41 s de
    costa a costa): falta correr (Shift/botão) e/ou viagem rápida entre
    portos já visitados.

### UX mobile
15. Sem **pinch zoom** (só botões), sem vibração/feedback ao atacar,
    alvos de toque pequenos apesar do raio generoso de 48 px existir
    só para mobs — warp e chão estão ok.
16. Canvas 960×600 paisagem em celular retrato = jogo pequeno com
    letterbox. Vale testar resolução adaptativa ao aspecto da tela.
17. Botões HTML (Mapa/Desprender/zoom) funcionam, mas o HUD de texto
    do Phaser mistura informação demais numa caixa só.

### Arquitetura / processo
18. **Nada commitado ainda** — o risco mais imediato do projeto.
19. `main.js` monolítico (Boot + World + input + combate + warps) e
    acoplado ao DOM via globais (`window.touchVector`, `window.playerWorld`,
    CustomEvents). Separar em módulos (`player.js`, `mobs.js`, `warps.js`,
    `world-loader.js`) destrava o resto.
20. Build em 3 passos manuais (`convert_all` → `make_interiors` →
    minimapa à parte com dependência npm não declarada) e **sem testes
    no repo** — o arnês jsdom+canvas que validou warps/interiores mora
    fora da árvore. Um `tools/build.sh` + `tests/smoke.js` fecha isso.
21. README com trechos desatualizados ("Sem minimapa", "viraram
    marcadores visuais", instrução de `TILESETS` que não existe mais).

## Roadmap sugerido

### P0 — barato, impacto imediato (1 sessão cada)
- [ ] **Commit** do `phaser-demo/` inteiro.
- [ ] **Pathfinding A*** no tap-to-move (grade da camada Collision).
- [ ] **Matar o download dobrado** de JSON + gzip na hospedagem.
- [ ] **Sprites corretos por espécie**: conversor extrai de
      `presets/entities/sprites/*.tscn` um catálogo (nome → png, frame,
      walk) e o spawn usa o sprite da espécie. *Maior salto visual.*
- [ ] `tools/build.sh` (converte + interiores + minimapa) e mover o
      smoke test (jsdom+canvas) para `phaser-demo/tests/`.

### P1 — vira jogo (2–4 sessões)
- [ ] **Combate de verdade**: stats dos `.tres` (HP/nível/velocidade/EXP),
      IA idle→persegue→ataca, animação Attack, jogador com HP/XP/nível,
      morte → respawn na entrada do mapa.
- [ ] **Sons e música**: SFX de ataque/morte dos mobs (`data/sounds/
      entities/`) e trilha por mapa (propriedade `music` do TMX).
- [ ] **NPCs no mundo**: sprite + nome; tocar = balão de fala simples
      (textos podem começar como placeholder por NPC famoso).
- [ ] **Save em `localStorage`**: mapa, posição, nível, mobs mortos
      (com respawn por timer).
- [ ] Correr (botão/Shift) + viagem rápida entre portos descobertos.

### P2 — polimento (conforme fôlego)
- [ ] Colisão por sub-formas do `Collision.tsx` (meias-paredes e
      diagonais) em vez de tile inteiro.
- [ ] Minimapa por mapa (não só Overworld) com warps marcados.
- [ ] Pinch zoom, viewport adaptativo p/ retrato, PWA (manifest +
      service worker p/ jogar offline no Android).
- [ ] Refactor em módulos ES (+ tipos via JSDoc) e CI rodando o smoke.
- [ ] Interiores com mais identidade (NPC atrás do balcão na loja,
      camas usáveis na estalagem) — e, se os TMX originais aparecerem,
      aposentar os gerados.

## Por onde eu começaria

**Sprites por espécie + pathfinding.** O primeiro muda a cara do jogo
em cada mapa (caverna com morcegos de verdade, deserto com escorpiões);
o segundo aposenta de vez a família de bugs "fiquei preso/não anda".
Juntos, transformam a POC em algo que parece o jogo original rodando
no navegador.
