#!/usr/bin/env python3
"""
Converte um mapa Tiled (.tmx + .tsx externos) do Source of Mana para o
formato JSON que o Phaser 3 carrega nativamente (this.load.tilemapTiledJSON).

Uso:
    python3 tools/convert_tmx.py ../data/maps/candor/candor-cave.tmx

Saida (dentro de phaser-demo/public/assets/):
    maps/<nome-do-mapa>.json     -> tilemap no formato Tiled JSON
    tilesets/<tileset>.png       -> imagens dos tilesets referenciados

Limitacoes conscientes desta versao:
  * Apenas tilesets de imagem unica (todos os do mapa de exemplo sao assim).
    Tilesets do tipo "image collection" (uma imagem por tile) sao recusados
    com mensagem clara, porque o Phaser nao os suporta diretamente.
  * A camada "Collision" e convertida como qualquer outra; quem decide o que
    colide e o jogo (no demo: todo tile nao-vazio da camada colide).
  * Layers de objetos (Spawn/Warp) sao exportadas como objectgroup do Tiled
    JSON, com as <properties> convertidas para o array name/value do Phaser.
"""
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = DEMO_ROOT / "public" / "assets"


def safe_key(name: str) -> str:
    """Nome de arquivo/chave seguro a partir do nome do tileset."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_properties(elem):
    props = []
    container = elem.find("properties")
    if container is None:
        return props
    for p in container.findall("property"):
        value = p.get("value", "")
        ptype = p.get("type", "string")
        if ptype == "int":
            value = int(value)
        elif ptype == "float":
            value = float(value)
        elif ptype == "bool":
            value = value == "true"
        props.append({"name": p.get("name"), "type": ptype, "value": value})
    return props


def convert(tmx_path: Path):
    tmx_path = tmx_path.resolve()
    root = ET.parse(tmx_path).getroot()
    if root.tag != "map":
        raise SystemExit(f"{tmx_path} nao e um mapa Tiled (.tmx)")

    width, height = int(root.get("width")), int(root.get("height"))
    tile_w, tile_h = int(root.get("tilewidth")), int(root.get("tileheight"))

    # ---- tilesets -------------------------------------------------------
    # Pasta por mapa: mapas diferentes reusam nomes de tileset ("Ground",
    # "Collision"...) com imagens diferentes — pasta única sobrescreveria.
    tilesets = []
    used_names = set()
    tileset_dir = ASSETS / "tilesets" / tmx_path.stem
    tileset_dir.mkdir(parents=True, exist_ok=True)
    for ts in root.findall("tileset"):
        source = ts.get("source")
        if source:
            tsx_path = (tmx_path.parent / source).resolve()
            tsx = ET.parse(tsx_path).getroot()
            img_base = tsx_path.parent
        else:
            # Tileset embutido no proprio .tmx (ex.: "Desert" do Overworld).
            tsx = ts
            img_base = tmx_path.parent
        image = tsx.find("image")
        per_tile = tsx.findall("tile/image")
        if image is None or per_tile:
            raise SystemExit(
                f"Tilese '{tsx.get('name')}' e do tipo image-collection, "
                "que o Phaser nao suporta diretamente. Escolha outro mapa "
                "ou achate o tileset numa imagem unica no Tiled."
            )
        img_src = (img_base / image.get("source")).resolve()
        # Nomes duplicados quebram o addTilesetImage do Phaser (ele casa por
        # nome): o segundo "Accessory" do Artis viraria as tiles do primeiro.
        name = tsx.get("name")
        if name in used_names:
            suffix = 2
            while f"{name} {suffix}" in used_names:
                suffix += 1
            print(f"aviso: tileset duplicado '{name}' renomeado para '{name} {suffix}'")
            name = f"{name} {suffix}"
        used_names.add(name)
        key = safe_key(name)
        dest = tileset_dir / f"{key}.png"
        shutil.copyfile(img_src, dest)
        tilesets.append({
            "firstgid": int(ts.get("firstgid")),
            "name": name,
            "tilewidth": int(tsx.get("tilewidth")),
            "tileheight": int(tsx.get("tileheight")),
            "tilecount": int(tsx.get("tilecount")),
            "columns": int(tsx.get("columns")),
            "image": f"../tilesets/{tmx_path.stem}/{key}.png",
            "imagewidth": int(image.get("width")),
            "imageheight": int(image.get("height")),
            "margin": 0,
            "spacing": 0,
        })
        print(f"tileset {tsx.get('name'):>14} -> assets/tilesets/{key}.png")

    # ---- layers ---------------------------------------------------------
    layers = []
    next_id = 1
    for layer in root.findall("layer"):
        data = layer.find("data")
        if data is None or data.get("encoding") != "csv":
            raise SystemExit(f"Layer '{layer.get('name')}' nao esta em CSV; reexporte no Tiled.")
        gids = [int(v) for v in data.text.replace("\n", "").split(",") if v.strip() != ""]
        assert len(gids) == width * height, layer.get("name")
        layers.append({
            "id": next_id,
            "name": layer.get("name"),
            "type": "tilelayer",
            "width": width,
            "height": height,
            "data": gids,
            "opacity": 1,
            "visible": True,
            "x": 0,
            "y": 0,
        })
        next_id += 1
        print(f"layer   {layer.get('name'):>14} ({sum(1 for g in gids if g)} tiles)")

    for group in root.findall("objectgroup"):
        objects = []
        for obj in group.findall("object"):
            entry = {
                "id": int(obj.get("id")),
                "name": obj.get("name", ""),
                "type": obj.get("type", ""),
                "x": float(obj.get("x", 0)),
                "y": float(obj.get("y", 0)),
                "width": float(obj.get("width", 0)),
                "height": float(obj.get("height", 0)),
                "rotation": 0,
                "visible": True,
                "properties": parse_properties(obj),
            }
            objects.append(entry)
            print(f"object  {entry['name']:>14} type={entry['type']} @({entry['x']:.0f},{entry['y']:.0f})")
        layers.append({
            "id": next_id,
            "name": group.get("name"),
            "type": "objectgroup",
            "draworder": "topdown",
            "opacity": 1,
            "visible": True,
            "x": 0,
            "y": 0,
            "objects": objects,
        })
        next_id += 1

    tilemap = {
        "type": "map",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "infinite": False,
        "width": width,
        "height": height,
        "tilewidth": tile_w,
        "tileheight": tile_h,
        "tilesets": tilesets,
        "layers": layers,
        "nextlayerid": next_id,
        "nextobjectid": 999,
        "version": "1.10",
        "tiledversion": "phaser-demo-converter",
        "properties": parse_properties(root),
    }

    (ASSETS / "maps").mkdir(parents=True, exist_ok=True)
    out = ASSETS / "maps" / f"{tmx_path.stem}.json"
    out.write_text(json.dumps(tilemap), encoding="utf-8")

    # Manifesto: o que o Phaser precisa carregar antes de montar o mapa
    # (nome de exibicao do mapa + tilesets com arquivo ja resolvido).
    map_name = next((p["value"] for p in parse_properties(root)
                     if p["name"] == "name"), tmx_path.stem)
    manifest = {
        "id": tmx_path.stem,
        "name": map_name,
        "tilewidth": tile_w,
        "tileheight": tile_h,
        "tilesets": [
            {"name": t["name"], "key": safe_key(t["name"]),
             "file": f"assets/tilesets/{tmx_path.stem}/{safe_key(t['name'])}.png"}
            for t in tilesets
        ],
    }
    man_out = ASSETS / "maps" / f"{tmx_path.stem}.manifest.json"
    man_out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"\nOK -> {out.relative_to(DEMO_ROOT)}  ({width}x{height} tiles de {tile_w}px)"
          f" + {man_out.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    convert(Path(sys.argv[1]))
