# Source of Mana × Phaser 3 — demo

Prova de conceito: **o mapa-múndi completo e um mob do Source of Mana rodando
no Phaser 3**, sem usar nenhum código do MMORPG (nada de cliente/servidor/DB
em GDScript).

> Versão anterior usava a Candor Cave — uma caverna subterrânea escura, que
> na tela parecia “tudo preto”. Agora o demo usa o **Overworld inteiro**,
> renderiza via **Canvas 2D** (não WebGL) e, se algo falhar ao carregar,
> mostra a mensagem de erro na própria página em vez de tela preta.

- Mapas: **os 40 mapas do jogo** (`data/maps/**/*.tmx`) — Overworld,
  Artis, Candor Cave/Arena, Drazil, Tulimshar inteira, deserto, minas,
  Splatyna, navio… — com os **warps funcionais**: andar até um círculo
  azul viaja para o mapa de destino (e volta), como no jogo original.
  Gere tudo com `python3 tools/convert_all.py`, que também emite
  `assets/maps/index.json` (nome do mapa → arquivo) para resolver os
  `dest_map` dos warps. Única exceção honesta: as portas de interiores
  de Artis (`001-2-*` — biblioteca, lojas, casas) não existem como `.tmx`
  em nenhum lugar do repositório, então aparecem como marcadores cinza
  — **atualização:** os interiores foram **criados** (ver seção abaixo),
  então hoje todas as portas de Artis abrem.
- Mobs: **as 32 espécies reais** dos spawns (Bat, Scorpion, Sand Snake,
  Maggot, Turtle, Peyote...), cada uma com sprite, frames de andar e
  stats (HP/nível/velocidade) extraídos das fichas do jogo por
  `tools/make_mobs.py` -> `assets/mobs/catalog.json`. O jogador continua
  sendo um Salt Slime. Mapas sem Spawn no original (Overworld,
  interiores) ficam sem mobs — nada de slime inventado no mapa-múndi.
- Phaser 3.60 vendorizado em `public/lib/` (licença em `PHASER-LICENSE.md`),
  então o demo roda 100% offline, sem build e sem CDN.

## Como rodar

```bash
cd phaser-demo/public
python3 -m http.server 8080
# abra http://localhost:8080
```

(Qualquer servidor estático serve — `npx serve`, Live Server do VS Code etc.)

**Controles:**
- 📱 **Android/toque:** arraste o **joystick virtual** (canto inferior
  esquerdo) ou **toque no chão** para andar até lá; **toque num slime**
  para andar até ele e atacar; botões **＋/－** (canto inferior direito)
  dão zoom. Implementação em `public/controls.js` + handlers `pointerdown`
  no `public/main.js` (`window.touchVector`, tap-to-move, perseguir-e-atacar).
- 🎮 **PC:** WASD/setas movem, clique num slime ataca, roda do mouse dá zoom.
- 🆘 **Botão "Desprender"** (canto superior direito): se ficar preso numa
  parede/canto, teleporta para o tile livre mais próximo; **dois toques
  seguidos** voltam para a entrada do mapa. O jogo também se desprende
  sozinho ao detectar 1s de movimento comandado sem sair do lugar — e os
  mobs não colidem mais fisicamente com o jogador (encurralavam).
- 🗺 **Botão "Mapa"** (canto superior direito, em qualquer aparelho): abre o
  **mapa-múndi inteiro** de uma vez — durante o jogo a câmera só mostra a
  vizinhança do jogador, o que pode dar a impressão de que "o mapa não
  carregou inteiro". A imagem é `public/assets/minimap.png`, gerada dos
  dados do próprio mapa por `tools/make_minimap.js` (2 px/tile, todas as
  camadas menos Collision), com um ponto amarelo na sua posição atual.

O canvas usa `touch-action: none` e `Phaser.Scale.FIT` para caber na tela
do celular sem rolar a página nem distorcer.

## Como o mapa chegou ao Phaser

O Phaser **não lê `.tmx`**; ele lê o **JSON do Tiled**
(`this.load.tilemapTiledJSON`). Duas formas de obter esse JSON:

1. **Abrir o `.tmx` no Tiled e exportar como JSON** (File → Export As → JSON), ou
2. **Usar o conversor incluído** (sem precisar do Tiled):

```bash
cd phaser-demo
python3 tools/convert_tmx.py ../data/maps/overworld/overworld.tmx
```

O script lê o `.tmx` + os `.tsx` externos, copia as imagens dos tilesets para
`public/assets/tilesets/` e gera `public/assets/maps/<mapa>.json` já com:

- as camadas de tile (`Ground`, `Ground2`, `Ground3`, `Fringe`, `Over`,
  `Collision`),
- tilesets externos (`.tsx`) **e embutidos** no `.tmx` (o Overworld tem o
  tileset `Desert` embutido) — tilesets com nome duplicado são renomeados,
  pois o Phaser casa tilesets por nome,
- a camada de objetos (`Object`) com `Warp`/`Port` e suas propriedades
  (`dest_map`, `dest_pos_x/y`...) — no demo os warps viram marcadores
  visuais com o destino anotado;
- as propriedades do mapa.

Para usar outro mapa, rode o conversor nele, ajuste a lista `TILESETS` em
`public/main.js` (nome do tileset → arquivo) e troque o caminho do JSON.
Caveats: o conversor aceita tilesets de **imagem única** (é o caso deste
mapa); tilesets "image collection" precisariam ser achatados numa imagem
única no Tiled, pois o Phaser não os suporta diretamente.

## Como o mob chegou ao Phaser

O PNG sozinho não diz como fatiar. O recorte foi extraído da cena original
`presets/entities/sprites/Slime.tscn` (Godot):

| Dado | Valor |
|---|---|
| Sheet | `slime.png`, 468×96 |
| Grade | 9 colunas × 4 linhas → frame **52×24** |
| Walk Down | frames 1, 2, 3, 0 |
| Walk Left | frames 10, 11, 12, 9 |
| Walk Up | frames 19, 20, 21, 18 |
| Walk Right | frames 28, 29, 30, 27 |

No Phaser isso vira `this.load.spritesheet(..., { frameWidth: 52, frameHeight: 24 })`
+ 4 animações — ver `WALK_FRAMES` em `public/main.js`. Para outro mob, abra o
`.tscn` dele em `presets/entities/sprites/`, leia `hframes`/`vframes` do nó
`Body` e as animações `Walk*` do `AnimationLibrary`.

Os stats (HP, nível, drops, skills) ficam em `presets/entities/<Mob>.tres`
(ex.: `Salt Slime.tres`: nível 1, pai `Slime.tres`) e servem como ficha de
referência para você reimplementar a lógica no seu jogo.

## Simplificações deste demo

- **Colisão por tile inteiro:** no original, os tiles da camada `Collision`
  têm sub-formas (meia parede, triângulos — ver
  `data/graphics/tilesets/generic/Collision.tsx`). Aqui, todo tile não-vazio
  da camada colide por inteiro (`setCollisionByExclusion([-1])`).
- **Spawn/Warp sem lógica de servidor:** viraram spawn aleatório em tiles
  andáveis e marcadores visuais, só para mostrar que os dados chegam íntegros.
- Sem minimapa, diálogo, inventário etc. — é um ponto de partida, não um porte.

## Licença dos assets

Arte do **Source of Mana** sob **CC BY-SA 4.0**: você pode usar e modificar,
inclusive comercialmente, desde que **dê crédito** (autores por arquivo em
`../LICENSE.md` e `../data/db/credits.json`, com link para
https://github.com/sourceofmana) e **mantenha a arte derivada sob a mesma
licença** (Share-Alike). O código deste demo é MIT, como o restante do projeto.

## Bugs já caçados (regressão)

- `Cannot read properties of undefined (reading 'left')`: o `buildWorld`
  lia `rawMap.layers`, mas o JSON bruto (`raw:<mapa>`) não era carregado no
  `preload` — quebrava no meio, depois do player e antes do teclado; o
  `update()` seguinte lia `this.cursors.left` e, como exceção dentro do
  `update()` **mata o loop de RAF do Phaser**, o jogo congelava. Correções:
  carregar o JSON bruto no preload, guarda dura no `update()`
  (`player/body/cursors/mobs`) e zerar player/teclado/mobs no `init()`
  (sem isso, o `update()` durante a troca de mapa usava o player destruído
  do mapa anterior e matava a transição no meio). Ida e volta
  Overworld ⇄ Artis testadas num arnês jsdom+canvas rodando o jogo real.

- Nascimento no mar / warp inalcançável: o spawn inicial caía num tile de
  água (Ground gid 11) na costa de Artis, e o centro dos portos fica dentro
  de tile de colisão (cais). Spawn movido p/ grama (tile 262,99) e o gatilho
  dos warps passou a medir distância ao **tile** do warp — encostar no cais
  viaja. Painel do minimapa: botão 🗺 ganhou z-index acima do painel +
  botão "✕ Fechar" interno + fechar tocando fora da imagem (antes o painel
  cobria o próprio botão de fechar).

## Interiores das construções (gerados)

Os interiores de Artis (bibliotecas, lojas, casas...) não existem em
nenhum formato neste repositório — as portas apontam para IDs legados
`001-2-*` sem arquivo. Eles foram **criados** para este demo com o
tileset de interiores do próprio projeto (`fringe.png`, 256 tiles):
`python3 tools/make_interiors.py` (depois do `convert_all.py`) gera
18 salas de 22×16 (Biblioteca, Ferraria, Laboratório de Alquimia,
Estalagem RedPlush, Salão dos Mercadores, Prefeitura, casas nobres...)
com piso/paredes/prateleiras/camas do tileset, cada uma ligada à sua
porta em Artis. A saída devolve o jogador **na porta exata de onde
entrou** (as salas com várias portas, como o Salão dos Mercadores,
lembram a sua). São interiores novos e simples — não são os mapas
originais perdidos; se um dia os TMX aparecerem, troque os arquivos
`interior-*.json` e apague as entradas `001-2-*` do `index.json`.

## Catálogo de mobs (make_mobs.py)

Rode depois do convert_all: `python3 tools/make_mobs.py`. Ele cruza os
objetos Spawn dos mapas com `presets/entities/<Espécie>.tres` (seguindo
`_parent`) e `presets/entities/sprites/*.tscn` (grade + animações Walk)
e gera o catálogo que o jogo consome. 6 espécies não têm ficha nem no
jogo original (árvores de coleta e legados: Manana/Coconut/Crocotree,
Pikpik, Piousse, Plushroom Field) e usam o parente mais próximo
(Peyote/Piou/cogumelo) em vez de virarem slime. Paletas alternativas
via shader do original (ex.: Sand Snake vs Snake, mesma sheet) ainda
não são aplicadas — entram com a textura base.
