#!/usr/bin/env python3
"""
Gera os INTERIORES das construções de Artis (biblioteca, lojas, estalagem,
casas nobres...) que NÃO existem em nenhum formato neste repositório: no
jogo original as portas apontam para mapas legados "001-2-*" sem arquivo.

Os interiores são criados com o tileset de interiores do próprio projeto
(data/graphics/tilesets/aemil/aurora/artis/indoor/fringe.png, "Indoor",
256 tiles de 32px). Tiles usados (id no tileset, gid = id+1):
  piso claro 17 · parede de madeira 97 · viga do topo 4 · porta 19/20/21+35/36/37
  prateleira 6-9 e 22-24 · estante de livros 46-47 (e 61-62 mesa c/ livros)
  camas 62-63/78-79 · banquinhos 83-84 · miudezas 38-40, 54-55, 57-59

Saída (public/assets/):
  maps/interior-<codigo>.json + .manifest.json   (formato que o jogo lê)
  tilesets/interiors/indoor.png + collision.png
  e PATCH em maps/index.json: "001-2-4" -> {id: "interior-001-2-4", spawn...}

A posição de spawn dentro do interior vai no índice porque as portas
legadas trazem dest_x/dest_y em coordenadas dos mapas perdidos — o jogo
usa esse spawn quando o destino é um interior. A SAÍDA do interior volta
para a porta exata de onde você entrou (mecanismo "back" no main.js).

Rode DEPOIS do convert_all.py (ele regenera o index.json):
    python3 tools/convert_all.py && python3 tools/make_interiors.py
"""
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
PUB = DEMO / "public"
REPO = DEMO.parent
MAPS = PUB / "assets" / "maps"
TILESETS = PUB / "assets" / "tilesets" / "interiors"

W, H = 22, 16           # tamanho do interior, em tiles de 32px
TILE = 32
ENTRY_TX, ENTRY_TY = 10, H - 2   # nasce aqui, logo acima da porta de saída

# gids (firstgid 1 no tileset Indoor; firstgid 257 no Collision)
FLOOR = 17 + 1
WALL = 97 + 1
BEAM = 4 + 1
DOOR = [19 + 1, 35 + 1]          # batente da porta (2 tiles de altura)
BLOCK = 257 + 5                  # tile cheio do tileset Collision (id 5)

NAMES = {
    "001-2-0": "Loja de Armaduras Leves",
    "001-2-1": "Casa Nobre nº 2",
    "001-2-2": "Casa da Taree",
    "001-2-4": "Biblioteca de Artis",
    "001-2-7": "Prefeitura de Artis",
    "001-2-10": "Casa Nobre nº 4",
    "001-2-11": "Casa Nobre nº 3",
    "001-2-12": "Casa Nobre nº 1",
    "001-2-15": "Casa Nobre nº 5",
    "001-2-16": "Casa do Capitão do Porto",
    "001-2-18": "Armazém do Cais",
    "001-2-19": "Salão dos Mercadores",
    "001-2-20": "Salão dos Mercadores (fundos)",
    "001-2-26": "Laboratório de Alquimia",
    "001-2-27": "Ferraria",
    "001-2-28": "Estalagem RedPlush",
    "001-2-31": "Prédio da Escadaria",
    "001-2-33": "Legião de Aemil",
}

# mobília por tipo de lugar: lista de (gid, largura_em_tiles)
FURNITURE = {
    "shelf": [6 + 1, 7 + 1, 8 + 1, 9 + 1],        # prateleira c/ pratos/pote
    "shelf2": [22 + 1, 23 + 1, 24 + 1],           # prateleira c/ garrafas/baú
    "books": [46 + 1, 47 + 1],                    # estante de livros
    "bed": [62 + 1, 63 + 1, 78 + 1, 79 + 1],      # cama (2x2: ids 62,63 / 78,79)
    "stool": [83 + 1, 84 + 1],
    "bits": [38 + 1, 39 + 1, 40 + 1, 54 + 1, 55 + 1, 57 + 1, 59 + 1],
}


def build_interior(code: str, friendly: str, seed: int) -> dict:
    rnd = random.Random(seed)
    ground = [[FLOOR] * W for _ in range(H)]
    fringe = [[0] * W for _ in range(H)]
    solid = [[0] * W for _ in range(H)]

    def put_wall(x, y):
        ground[y][x] = WALL
        solid[y][x] = BLOCK

    # paredes: topo com 2 fileiras (viga + madeira), lados e base
    for x in range(W):
        ground[0][x] = BEAM
        solid[0][x] = BLOCK
        put_wall(x, 1)
        put_wall(x, H - 1)
    for y in range(H):
        put_wall(0, y)
        put_wall(W - 1, y)
    # porta na base (2 tiles): batente no Fringe, chão livre e sem colisão
    for i, tx in enumerate((ENTRY_TX, ENTRY_TX + 1)):
        ground[H - 1][tx] = FLOOR
        solid[H - 1][tx] = 0
        fringe[H - 2][tx] = DOOR[i % 2]
        fringe[H - 3][tx] = DOOR[i % 2]

    blocked = set()

    def place(gids, tx, ty, w_tiles=1, h_tiles=1):
        for dy in range(h_tiles):
            for dx in range(w_tiles):
                gid = gids[dy * w_tiles + dx] if len(gids) == w_tiles * h_tiles else gids[0]
                fringe[ty + dy][tx + dx] = gid
                solid[ty + dy][tx + dx] = BLOCK
                blocked.add((tx + dx, ty + dy))

    # prateleiras encostadas na parede do topo (fileira y=2)
    x = 2
    while x < W - 6:
        kind = rnd.choice(["shelf", "shelf2", "books"])
        tiles = FURNITURE[kind]
        if x + len(tiles) < W - 1:
            place(tiles, x, 2, len(tiles), 1)
        x += len(tiles) + rnd.randint(1, 3)

    # camas no canto direito (estalagens e casas ganham 1-2)
    if any(k in friendly for k in ("Estalagem", "Casa", "Capitão")):
        place(FURNITURE["bed"], W - 4, 4, 2, 2)
        if rnd.random() < 0.6:
            place(FURNITURE["bed"], W - 4, 8, 2, 2)

    # banquinhos e miudezas espalhadas (sem travar a entrada)
    for _ in range(rnd.randint(3, 6)):
        for _try in range(10):
            tx, ty = rnd.randint(2, W - 3), rnd.randint(4, H - 4)
            if (tx, ty) in blocked or abs(tx - ENTRY_TX) <= 1 and ty >= H - 5:
                continue
            place([rnd.choice(FURNITURE["stool"] + FURNITURE["bits"])], tx, ty)
            break

    spawn_px = {"x": ENTRY_TX * TILE + TILE // 2, "y": ENTRY_TY * TILE + TILE // 2}
    return {
        "type": "map", "orientation": "orthogonal", "renderorder": "right-down",
        "infinite": False, "width": W, "height": H,
        "tilewidth": TILE, "tileheight": TILE,
        "tilesets": [
            {"firstgid": 1, "name": "Indoor", "tilewidth": 32, "tileheight": 32,
             "tilecount": 256, "columns": 16, "image": "../tilesets/interiors/indoor.png",
             "imagewidth": 512, "imageheight": 512, "margin": 0, "spacing": 0},
            {"firstgid": 257, "name": "Collision", "tilewidth": 32, "tileheight": 32,
             "tilecount": 16, "columns": 4, "image": "../tilesets/interiors/collision.png",
             "imagewidth": 128, "imageheight": 128, "margin": 0, "spacing": 0},
        ],
        "layers": [
            {"id": 1, "name": "Ground", "type": "tilelayer", "width": W, "height": H,
             "data": [g for row in ground for g in row], "opacity": 1, "visible": True, "x": 0, "y": 0},
            {"id": 2, "name": "Fringe", "type": "tilelayer", "width": W, "height": H,
             "data": [g for row in fringe for g in row], "opacity": 1, "visible": True, "x": 0, "y": 0},
            {"id": 3, "name": "Collision", "type": "tilelayer", "width": W, "height": H,
             "data": [g for row in solid for g in row], "opacity": 1, "visible": True, "x": 0, "y": 0},
            {"id": 4, "name": "Object", "type": "objectgroup", "draworder": "topdown",
             "opacity": 1, "visible": True, "x": 0, "y": 0, "objects": [
                 {"id": 1, "name": "Sair → Artis", "type": "Warp",
                  "x": ENTRY_TX * TILE, "y": ENTRY_TY * TILE, "width": TILE * 2, "height": TILE,
                  "rotation": 0, "visible": True,
                  "properties": [{"name": "dest_map", "type": "string", "value": "Artis"}]},
             ]},
        ],
        "nextlayerid": 5, "nextobjectid": 2, "version": "1.10",
        "tiledversion": "phaser-demo-interiors",
        "_spawn": spawn_px,
    }


def main():
    artis = json.loads((MAPS / "artis.json").read_text())
    doors = defaultdict(list)
    for layer in artis["layers"]:
        for obj in layer.get("objects", []):
            props = {p["name"]: p["value"] for p in obj.get("properties", [])}
            dest = props.get("map")
            if dest and dest.startswith("001-"):
                doors[dest].append(obj)

    TILESETS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "data/graphics/tilesets/aemil/aurora/artis/indoor/fringe.png",
                    TILESETS / "indoor.png")
    shutil.copyfile(REPO / "data/graphics/tilesets/generic/collision.png",
                    TILESETS / "collision.png")

    index = json.loads((MAPS / "index.json").read_text())
    for code, door_objs in sorted(doors.items()):
        friendly = NAMES.get(code, door_objs[0]["name"].removeprefix("To "))
        interior_id = f"interior-{code}"
        tilemap = build_interior(code, friendly, seed=hash(code) & 0xFFFF)
        spawn = tilemap.pop("_spawn")
        (MAPS / f"{interior_id}.json").write_text(json.dumps(tilemap))
        (MAPS / f"{interior_id}.manifest.json").write_text(json.dumps({
            "id": interior_id, "name": f"{friendly} (interior)",
            "tilewidth": TILE, "tileheight": TILE,
            "tilesets": [
                {"name": "Indoor", "key": "indoor", "file": "assets/tilesets/interiors/indoor.png"},
                {"name": "Collision", "key": "collision", "file": "assets/tilesets/interiors/collision.png"},
            ],
        }, indent=1))
        index[code] = {"id": interior_id, "tile": TILE, "spawn": spawn}
        print(f"{code}: {friendly} -> {interior_id}.json ({len(door_objs)} porta(s) em Artis)")

    (MAPS / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    print(f"\nindex.json atualizado com {len(doors)} interiores.")


if __name__ == "__main__":
    main()
