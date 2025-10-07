import csv
import json
import os
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV_PATH = os.path.join(BASE_DIR, 'materials', 'cards.tsv')
JSON_PATH = os.path.join(BASE_DIR, 'materials', 'cards.json')


def main() -> None:
	if not os.path.exists(TSV_PATH):
		raise SystemExit(f"TSV not found: {TSV_PATH}")
	rows: List[Dict[str, Any]] = []
	with open(TSV_PATH, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f, delimiter='\t')
		for row in reader:
			rows.append({
				'Category1': (row.get('Category1') or '').strip(),
				'Category2': (row.get('Category2') or '').strip(),
				'Name': (row.get('Name') or '').strip(),
				'Text': (row.get('Text') or '').strip(),
				'ShortText': (row.get('ShortText') or '').strip(),
				'URL': (row.get('URL') or '').strip(),
			})
	os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
	with open(JSON_PATH, 'w', encoding='utf-8') as out:
		json.dump(rows, out, ensure_ascii=False, indent=2)
	print(f"Wrote {len(rows)} cards to {JSON_PATH}")


if __name__ == '__main__':
	main()
