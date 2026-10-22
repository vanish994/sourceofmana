#!/usr/bin/env python3
"""
Converte TODOS os mapas .tmx de data/maps/ para o Phaser e gera o indice
public/assets/maps/index.json:  { "Nome do Mapa": {"id": "<stem>", "tile": 32} }

E esse indice que permite ao jogo resolver os warps: no TMX, um warp diz
dest_map="Candor Cave" — o indice traduz o nome para o arquivo convertido.

Uso:  python3 tools/convert_all.py
Mapas que falharem (ex.: tileset image-collection) sao listados no final
e ficam fora do indice — os warps para eles aparecem no jogo como
"sem saida (mapa nao convertido)".
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_tmx import convert, ASSETS  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MAPS_DIR = REPO / "data" / "maps"


def main():
    index = {}
    ok, failed = [], []
    for tmx in sorted(MAPS_DIR.rglob("*.tmx")):
        try:
            convert(tmx)
        except SystemExit as e:
            failed.append((tmx.name, str(e)))
            continue
        except Exception as e:  # noqa: BLE001 - queremos listar e seguir
            failed.append((tmx.name, f"{type(e).__name__}: {e}"))
            continue
        root = ET.parse(tmx).getroot()
        name = next((p.get("value") for p in root.findall("properties/property")
                     if p.get("name") == "name"), tmx.stem)
        # Em duplicidade de nome de exibicao, o primeiro mapa vence.
        index.setdefault(name, {"id": tmx.stem, "tile": int(root.get("tilewidth"))})
        ok.append(tmx.stem)

    (ASSETS / "maps").mkdir(parents=True, exist_ok=True)
    out = ASSETS / "maps" / "index.json"
    out.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== {len(ok)} mapas convertidos -> {out.relative_to(REPO)}")
    for stem in ok:
        print("  ok:", stem)
    if failed:
        print(f"=== {len(failed)} FALHARAM (fora do indice):")
        for name, why in failed:
            print(f"  {name}: {why}")


if __name__ == "__main__":
    main()
