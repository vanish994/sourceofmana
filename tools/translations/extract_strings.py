#!/usr/bin/env python3
"""Extracts player-visible strings from scenes, scripts and content
resources, used to keep data/translations/pt_BR.csv up to date.

Usage: python3 tools/translations/extract_strings.py [--check]
With --check, exits with status 1 if some extracted string is missing
from data/translations/pt_BR.csv.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_PATH = os.path.join(ROOT, "data", "translations", "pt_BR.csv")

# Strings that look like text but are internal identifiers or must stay as-is
IGNORED = {
	"", "Artis", "GP", "x1", "x2", "x3", "English", "Português (Brasil)",
	"000000", "0/0", "Lvl. 2", "Test", "Player", "Ship",
}

STR = r'"((?:[^"\\]|\\.)*)"'
SCENE_PROPS = re.compile(r'^(?:text|tooltip_text|placeholder_text|title|popup/item_\d+/text) = ' + STR, re.M)
NPC_CALLS = re.compile(r'\b(?:Mes|Chat|Choice|Think|Whisper|Narrate|Express)\(\s*' + STR)
NOTIF_CALLS = re.compile(r'\b(?:Push)?Notification\((?:[^(),"]*,\s*)?' + STR)
CHAT_SYSTEM_CALLS = re.compile(r'\bChatSystem\([^,()]*,\s*' + STR)
TR_CALLS = re.compile(r'\btr\(' + STR + r'\)')
TMX_NAME = re.compile(r'<property name="name" value="([^"]*)"')
TRES_NAME = re.compile(r'^(?:name|_name) = ' + STR, re.M)
TRES_DESC = re.compile(r'^(?:description|_description) = ' + STR, re.M)
QUEST_FIELDS = re.compile(r'^(?:name|description|giver|giverLocation|target|targetLocation|reward) = ' + STR, re.M)
TRIPLE_QUOTED = re.compile(r'"""(.*?)"""', re.S)
CONST_LIST_FILES = (
	("sources/gui/DeathMessages.gd", re.compile(r'^\t' + STR + r',', re.M)),
	("sources/gui/Loading.gd", re.compile(r'^\t' + STR + r',', re.M)),
	("sources/input/DeviceManager.gd", re.compile(r'^\t"[^"]+" : ' + STR + r',', re.M)),
)

def unescape(s: str) -> str:
	return s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")

def is_translatable(s: str) -> bool:
	if s in IGNORED:
		return False
	return any(c.isalpha() for c in s)

def walk(root, exts):
	for base, _dirs, files in os.walk(root):
		for name in sorted(files):
			if os.path.splitext(name)[1] in exts:
				yield os.path.join(base, name)

def scan(found, root, exts, regexes, unesc=True):
	for path in walk(root, exts):
		with open(path, encoding="utf-8") as f:
			content = f.read()
		for regex in regexes:
			for m in regex.finditer(content):
				s = unescape(m.group(1)) if unesc else m.group(1)
				if is_translatable(s):
					found.setdefault(s, set()).add(os.path.relpath(path, ROOT))

def extract_scene_strings():
	found = {}
	scan(found, os.path.join(ROOT, "presets"), {".tscn"}, (SCENE_PROPS,))
	return found

def extract_npc_strings():
	found = {}
	scan(found, os.path.join(ROOT, "sources", "scripts"), {".gd"}, (NPC_CALLS, NOTIF_CALLS, CHAT_SYSTEM_CALLS))
	return found

def extract_code_strings():
	found = {}
	scan(found, os.path.join(ROOT, "sources"), {".gd"}, (TR_CALLS,))
	# Notifications pushed by actor/world server code (static ones only)
	for sub in ("actor", "world", "skill", "network"):
		scan(found, os.path.join(ROOT, "sources", sub), {".gd"}, (NOTIF_CALLS, CHAT_SYSTEM_CALLS))
	# Const string lists (death messages, loading tips, action names)
	for rel, regex in CONST_LIST_FILES:
		path = os.path.join(ROOT, *rel.split("/"))
		with open(path, encoding="utf-8") as f:
			content = f.read()
		for m in regex.finditer(content):
			s = unescape(m.group(1))
			if is_translatable(s):
				found.setdefault(s, set()).add(rel)
	# First-login multi-line message boxes
	with open(os.path.join(ROOT, "sources", "gui", "Gui.gd"), encoding="utf-8") as f:
		for m in TRIPLE_QUOTED.finditer(f.read()):
			s = m.group(1)
			if is_translatable(s):
				found.setdefault(s, set()).add("sources/gui/Gui.gd")
	# Gender display names
	with open(os.path.join(ROOT, "sources", "actor", "ActorCommons.gd"), encoding="utf-8") as f:
		content = f.read()
	for m in re.finditer(r'const gender\w+ : String\s*=\s*' + STR, content):
		found.setdefault(m.group(1), set()).add("sources/actor/ActorCommons.gd")
	return found

def extract_content_strings():
	found = {}
	for sub, regexes in (
		("presets/cells", (TRES_NAME, TRES_DESC)),
		("presets/entities", (TRES_NAME,)),
		("presets/hairstyles", (TRES_NAME,)),
		("presets/races", (TRES_NAME,)),
		("presets/palettes", (TRES_NAME,)),
		("presets/quests", (QUEST_FIELDS,)),
	):
		scan(found, os.path.join(ROOT, *sub.split("/")), {".tres"}, regexes)
	# Quest start/complete notifications are composed server side
	questNames = {}
	scan(questNames, os.path.join(ROOT, "presets", "quests"), {".tres"}, (re.compile(r'^name = ' + STR, re.M),))
	for name, origins in questNames.items():
		found.setdefault("Quest Started: " + name, set()).update(origins)
		found.setdefault("Quest Completed: " + name, set()).update(origins)
	# Map names come from the "name" property of Tiled maps
	scan(found, os.path.join(ROOT, "data", "maps"), {".tmx"}, (TMX_NAME,), unesc=False)
	# Login screen news and agreement
	for rel in ("data/db/news.json", "data/db/agreement.json"):
		with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
			data = json.load(f)
		for category in data.get("categories", []):
			for value in (category.get("category"),):
				if value and is_translatable(value):
					found.setdefault(value, set()).add(rel)
			for entry in category.get("entries", []):
				for value in (entry.get("title"), entry.get("content")):
					if value and is_translatable(value):
						found.setdefault(value, set()).add(rel)
	return found

def load_csv_keys():
	if not os.path.exists(CSV_PATH):
		return set()
	with open(CSV_PATH, newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		next(reader, None)
		return {row[0] for row in reader if row}

def main():
	check = "--check" in sys.argv
	sections = {
		"scenes": extract_scene_strings(),
		"npc-dialogues": extract_npc_strings(),
		"code": extract_code_strings(),
		"content": extract_content_strings(),
	}
	existing = load_csv_keys()
	allKeys = {}
	missing = 0
	for section, found in sections.items():
		for key in found:
			allKeys.setdefault(key, set()).update(found[key])
		print(f"## {section}: {len(found)} unique strings")
	for key in sorted(allKeys):
		if key not in existing:
			missing += 1
			if check:
				origin = sorted(allKeys[key])[0]
				print(f"MISSING ({origin}): {key!r}")
	print(f"## total unique: {len(allKeys)}, missing from CSV: {missing}")
	if check and missing:
		sys.exit(1)

if __name__ == "__main__":
	main()
