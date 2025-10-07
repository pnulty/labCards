import csv
import json
import os
import random
from typing import List, Dict, Any

from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO, emit

# App setup
app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
socketio = SocketIO(app, cors_allowed_origins='*')

# Data paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Materials directory (everything lives under labcards/)
MATERIALS_DIR = os.path.join(BASE_DIR, 'materials')

CARDS_TSV_PATH = os.path.join(MATERIALS_DIR, 'cards.tsv')
CARDS_JSON_PATH = os.path.join(MATERIALS_DIR, 'cards.json')

# In-memory game state (single shared room/game)
all_cards: List[Dict[str, Any]] = []
# Suit-based structures
SUIT_ORDER = ["TOUCHSTONE", "WORKSHOP", "TOOL", "PROTOCOL", "PLATFORM"]
SUIT_SET = set(SUIT_ORDER)
suit_to_indexes: Dict[str, List[int]] = {}
# Drawn sequence (indexes of all_cards)
drawn_indexes: List[int] = []
# Pointer to next suit position in SUIT_ORDER
current_step: int = 0


def load_cards_from_tsv(tsv_path: str) -> List[Dict[str, Any]]:
	cards: List[Dict[str, Any]] = []
	if not os.path.exists(tsv_path):
		return cards
	with open(tsv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f, delimiter='\t')
		for row in reader:
			card = {
				'Category1': row.get('Category1', '').strip(),
				'Category2': row.get('Category2', '').strip(),
				'Name': row.get('Name', '').strip(),
				'Text': row.get('Text', '').strip(),
				'ShortText': row.get('ShortText', '').strip(),
				'URL': row.get('URL', '').strip(),
			}
			cards.append(card)
	return cards


def load_cards() -> List[Dict[str, Any]]:
	if os.path.exists(CARDS_JSON_PATH):
		with open(CARDS_JSON_PATH, 'r', encoding='utf-8') as f:
			data = json.load(f)
			return data if isinstance(data, list) else []
	return load_cards_from_tsv(CARDS_TSV_PATH)


def build_suits() -> None:
	"""Build and shuffle per-suit index lists and reset draw progression."""
	global suit_to_indexes, drawn_indexes, current_step
	suit_to_indexes = {suit: [] for suit in SUIT_ORDER}
	for idx, card in enumerate(all_cards):
		c1 = (card.get('Category1') or '').strip().upper()
		c2 = (card.get('Category2') or '').strip().upper()
		use = c1 if c1 in SUIT_SET else (c2 if c2 in SUIT_SET else '')
		if use:
			suit_to_indexes[use].append(idx)
	# Shuffle within each suit for randomness
	for lst in suit_to_indexes.values():
		random.shuffle(lst)
	drawn_indexes = []
	current_step = 0


def remaining_total() -> int:
	"""Number of remaining draws = count of suits at or after current_step that still have at least one card available."""
	remaining = 0
	for pos in range(current_step, len(SUIT_ORDER)):
		s = SUIT_ORDER[pos]
		if suit_to_indexes.get(s):
			remaining += 1
	return remaining


def total_targets() -> int:
	"""Total possible draws in this session = number of suits that have at least one card."""
	return sum(1 for s in SUIT_ORDER if suit_to_indexes.get(s))


def current_state() -> Dict[str, Any]:
	return {
		'drawn': [all_cards[i] for i in drawn_indexes],
		'remaining': remaining_total(),
		'total': total_targets(),
	}


@app.route('/')
def index():
	return send_from_directory(app.static_folder, 'index.html')


@app.route('/instructions')
def instructions():
	return send_from_directory(MATERIALS_DIR, 'instructions.docx', as_attachment=True)


@app.route('/healthz')
def healthz():
	return jsonify({'ok': True, 'drawn': len(drawn_indexes)})


@socketio.on('connect')
def on_connect():
	emit('state', current_state())


@socketio.on('draw')
def on_draw():
	global current_step
	# Advance to the next suit that still has available cards
	while current_step < len(SUIT_ORDER) and not suit_to_indexes.get(SUIT_ORDER[current_step]):
		current_step += 1
	# If we have exhausted all suits, just emit current state
	if current_step >= len(SUIT_ORDER):
		emit('state', current_state())
		return
	# Draw one from the current suit
	current_suit = SUIT_ORDER[current_step]
	bucket = suit_to_indexes.get(current_suit) or []
	if bucket:
		# Take the next randomized card from this suit
		idx = bucket.pop()
		drawn_indexes.append(idx)
		# Move to next suit position for the next draw
		current_step += 1
	# Broadcast updated state
	socketio.emit('state', current_state())


@socketio.on('reset')
def on_reset():
	build_suits()
	socketio.emit('state', current_state())


def bootstrap():
	global all_cards
	all_cards = load_cards()
	build_suits()
	# Simple startup logging to help verify data loading
	print(f"Materials dir: {MATERIALS_DIR}")
	print(f"Loaded cards: {len(all_cards)}")
	for suit in SUIT_ORDER:
		print(f"{suit}: {len(suit_to_indexes.get(suit, []))} available")


if __name__ == '__main__':
	bootstrap()
	port = int(os.environ.get('PORT', '5000'))
	socketio.run(app, host='0.0.0.0', port=port)

