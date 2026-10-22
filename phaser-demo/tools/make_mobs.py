#!/usr/bin/env python3
"""
Gera o CATÁLOGO DE MOBS do demo: espécie -> sprite/frames/stats reais.

Fontes (tudo do repo, nada inventado):
  * espécies e onde spawnam: objetos Spawn dos mapas (assets convertidos)
  * ficha da entidade: presets/entities/<Espécie>.tres (EntityData),
    seguindo a cadeia _parent (ex.: Salt Slime -> Slime)
  * sprite: _customTexture do .tres ou a textura da cena
    presets/entities/sprites/<Preset>.tscn (_spritePreset, com _parent)
  * grade e animações Walk*: hframes/vframes do nó Body + AnimationLibrary
    da cena .tscn (mesmoParser usado p/ o Slime no demo original)
  * stats: _stats do .tres (maxHealth, level, walkSpeed, attack, baseExp)

Saída:
  public/assets/mobs/catalog.json
  public/assets/monsters/<especie>.png (cópias das sheets usadas)

Uso: python3 tools/make_mobs.py   (depois do convert_all.py)
"""
import json
import re
import shutil
import struct
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
REPO = DEMO.parent
ASSETS = DEMO / "public" / "assets"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def png_size(path: Path):
    with open(path, "rb") as f:
        f.read(16)
        return struct.unpack(">II", f.read(8))


EXT_RE = re.compile(r'\[ext_resource [^\]]*path="res://([^"]+)"[^\]]*id="([^"]+)"')
REF_RE = re.compile(r'ExtResource\("([^"]+)"\)')


def parse_tres(path: Path, depth=0):
    """Retorna dict com spritePreset, customTexture e stats (com _parent)."""
    text = path.read_text()
    exts = {m.group(2): m.group(1) for m in EXT_RE.finditer(text)}

    def field(name):
        m = re.search(rf'^{name} = ExtResource\("([^"]+)"\)', text, re.M)
        return exts.get(m.group(1)) if m else None

    stats = {}
    m = re.search(r"_stats = \{(.*?)\n\}", text, re.S)
    if m:
        for k, v in re.findall(r'"(\w+)": ([0-9.]+)', m.group(1)):
            stats[k] = float(v) if "." in v else int(v)

    out = {
        "spritePreset": field("_spritePreset"),
        "customTexture": field("_customTexture"),
        "stats": stats,
    }
    parent = field("_parent")
    if parent and depth < 6:
        base = parse_tres(REPO / parent, depth + 1)
        merged = dict(base["stats"]); merged.update(stats)
        out["stats"] = merged
        out["spritePreset"] = out["spritePreset"] or base["spritePreset"]
        out["customTexture"] = out["customTexture"] or base["customTexture"]
    return out


def parse_sprite_tscn(path: Path):
    """Grade (hframes/vframes) + frames das animações Walk* da cena."""
    text = path.read_text()
    tex = None
    m = re.search(r'\[ext_resource type="Texture2D" [^\]]*path="res://([^"]+\.png)"', text)
    if m:
        tex = m.group(1)
    body = re.search(r'\[node name="Body"[^\]]*\](.*?)(?=\n\[node|\Z)', text, re.S)
    body = body.group(1) if body else ""
    # A textura que vale e a do Body (a cena pode ter acessorios antes,
    # ex.: SlimeSea tem a geleia como primeiro Texture2D da lista)
    bm = re.search(r'texture = ExtResource\("([^"]+)"\)', body)
    if bm:
        exts = {mm.group(2): mm.group(1) for mm in re.finditer(
            r'\[ext_resource [^\]]*path="res://([^"]+)"[^\]]*id="([^"]+)"', text)}
        if bm.group(1) in exts:
            tex = exts[bm.group(1)]
    hf = int(re.search(r"hframes = (\d+)", body).group(1))
    vf = int(re.search(r"vframes = (\d+)", body).group(1))
    idle_frame = int(re.search(r"frame = (\d+)", body).group(1)) if "frame =" in body else 0

    walks = {}
    for am in re.finditer(
            r'\[sub_resource type="Animation" id="[^"]+"\]\nresource_name = "(Walk\w+|Idle\w+)"(.*?)(?=\n\[sub_resource|\n\[node|\Z)',
            text, re.S):
        name, block = am.group(1), am.group(2)
        vals = re.search(r'"values": \[([0-9, ]+)\]', block)
        if vals:
            frames = [int(v) for v in vals.group(1).split(",")]
            walks[name] = frames
    return {"texture": tex, "hframes": hf, "vframes": vf,
            "idleFrame": idle_frame, "anims": walks}


def main():
    # ---- especies a partir dos spawns dos mapas convertidos ----------------
    species = set()
    for f in sorted((ASSETS / "maps").glob("*.json")):
        if "index" in f.name or "manifest" in f.name or "interior" in f.name:
            continue
        m = json.loads(f.read_text())
        for layer in m["layers"]:
            for obj in layer.get("objects", []):
                props = {p["name"]: p["value"] for p in obj.get("properties", [])}
                if (obj.get("type") or "").lower() == "spawn" and \
                        str(props.get("type", "Monster")).lower() == "monster":
                    species.add(obj["name"])
    species.add("Salt Slime")  # sprite do jogador

    tres_by_norm = {}
    for t in (REPO / "presets/entities").glob("*.tres"):
        tres_by_norm[re.sub(r"[^a-z0-9]", "", t.stem.lower())] = t

    (ASSETS / "monsters").mkdir(parents=True, exist_ok=True)
    (ASSETS / "mobs").mkdir(parents=True, exist_ok=True)
    # Sem ficha nem no jogo original (nos de coleta/legado): usam o
    # parente mais proximo em vez de virarem slime generico.
    ALIASES = {
        "Pikpik": "Piou", "Piousse": "Piou",
        "Plushroom Field": "Evil Mushroom",
        "Manana Tree": "Peyote", "Coconut Tree": "Peyote", "Crocotree": "Peyote",
    }

    catalog, warnings = {}, []
    for name in sorted(species):
        tres = REPO / "presets/entities" / f"{name}.tres"
        if not tres.exists():
            tres = tres_by_norm.get(re.sub(r"[^a-z0-9]", "", name.lower()))
        if (not tres or not tres.exists()) and name in ALIASES:
            tres = REPO / "presets/entities" / f"{ALIASES[name]}.tres"
        if not tres or not tres.exists():
            warnings.append(f"{name}: sem .tres — fora do catálogo (cai no slime)")
            continue
        ent = parse_tres(tres)
        if not ent["spritePreset"]:
            warnings.append(f"{name}: sem spritePreset — fora do catálogo")
            continue
        spr = parse_sprite_tscn(REPO / ent["spritePreset"])
        png_rel = ent["customTexture"] or spr["texture"]
        if not png_rel:
            warnings.append(f"{name}: sem textura — fora do catálogo")
            continue
        png_path = REPO / png_rel
        w, h = png_size(png_path)
        fw, fh = w // spr["hframes"], h // spr["vframes"]
        dest_name = f"{slug(name)}.png"
        shutil.copyfile(png_path, ASSETS / "monsters" / dest_name)

        walk = {}
        for d in ("Down", "Left", "Right", "Up"):
            frames = spr["anims"].get(f"Walk{d}")
            if not frames:  # espécie estática (árvore etc.): usa o frame idle
                frames = spr["anims"].get(f"Idle{d}", [spr["idleFrame"]])
            walk[d.lower()] = frames
        st = ent["stats"]
        catalog[name] = {
            "key": slug(name),
            "file": f"assets/monsters/{dest_name}",
            "frameWidth": fw, "frameHeight": fh,
            "walk": walk,
            "hp": int(st.get("maxHealth", 30)),
            "level": int(st.get("level", 1)),
            "walkSpeed": float(st.get("walkSpeed", 50)),
            "attack": int(st.get("attack", 5)),
            "exp": int(st.get("baseExp", 0)),
        }
        print(f"{name:>16}: {dest_name} {fw}x{fh} HP{catalog[name]['hp']} "
              f"nv{catalog[name]['level']} walk={ {k: v[:3] for k, v in walk.items()} }")

    out = ASSETS / "mobs" / "catalog.json"
    out.write_text(json.dumps(catalog, indent=1, ensure_ascii=False))
    print(f"\ncatálogo: {len(catalog)}/{len(species)} espécies -> {out.relative_to(DEMO)}")
    for w_ in warnings:
        print("  ⚠", w_)


if __name__ == "__main__":
    main()
