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
# Use threading mode to avoid eventlet/greenlet dependencies
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

# Data paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Materials directory (everything lives under labcards/)
MATERIALS_DIR = os.path.join(BASE_DIR, 'materials')

CARDS_TSV_PATH = os.path.join(MATERIALS_DIR, 'cards.tsv')
CARDS_JSON_PATH = os.path.join(MATERIALS_DIR, 'cards.json')
SESSION_PATH = os.path.join(MATERIALS_DIR, 'session.json')

# In-memory game state (single shared room/game)
all_cards: List[Dict[str, Any]] = []
# Suit-based structures
SUIT_ORDER = ["TOUCHSTONE", "WORKSHOP", "TOOL", "PROTOCOL", "PLATFORM"]
SUIT_SET = set(SUIT_ORDER)
ELIGIBLE_REDRAW = {"WORKSHOP", "TOOL", "PROTOCOL"}
suit_to_indexes: Dict[str, List[int]] = {}
# Drawn sequence (indexes of all_cards)
drawn_indexes: List[int] = []
# Mapping suit -> position in drawn_indexes where it was drawn
suit_drawn_pos: Dict[str, int] = {}
# One-time redraw usage per suit
redraw_used: Dict[str, bool] = {"WORKSHOP": False, "TOOL": False, "PROTOCOL": False}
# Pointer to next suit position in SUIT_ORDER
current_step: int = 0
_initialized: bool = False


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
	global suit_to_indexes, drawn_indexes, current_step, suit_drawn_pos, redraw_used
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
	suit_drawn_pos = {}
	redraw_used = {"WORKSHOP": False, "TOOL": False, "PROTOCOL": False}
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


def can_redraw_map() -> Dict[str, bool]:
	m: Dict[str, bool] = {}
	for s in ELIGIBLE_REDRAW:
		m[s] = bool(suit_drawn_pos.get(s) is not None and s in suit_drawn_pos and not redraw_used.get(s, False) and (suit_to_indexes.get(s) or []))
	return m


def current_state() -> Dict[str, Any]:
	return {
		'drawn': [all_cards[i] for i in drawn_indexes],
		'remaining': remaining_total(),
		'total': total_targets(),
		'canRedraw': can_redraw_map(),
		'redrawUsed': {k: bool(v) for k, v in redraw_used.items()},
	}


def save_session() -> None:
	try:
		os.makedirs(MATERIALS_DIR, exist_ok=True)
		with open(SESSION_PATH, 'w', encoding='utf-8') as f:
			json.dump({
				'drawn_indexes': drawn_indexes,
				'suit_to_indexes': suit_to_indexes,
				'suit_drawn_pos': suit_drawn_pos,
				'redraw_used': redraw_used,
				'current_step': current_step,
				'cards_len': len(all_cards),
			}, f, ensure_ascii=False)
	except Exception:
		pass


def try_load_session() -> bool:
	global drawn_indexes, suit_to_indexes, suit_drawn_pos, redraw_used, current_step
	if not os.path.exists(SESSION_PATH):
		return False
	try:
		with open(SESSION_PATH, 'r', encoding='utf-8') as f:
			data = json.load(f)
			if data.get('cards_len') != len(all_cards):
				return False
			drawn_indexes = [int(i) for i in data.get('drawn_indexes', [])]
			# Validate indexes
			for i in drawn_indexes:
				if i < 0 or i >= len(all_cards):
					return False
			suit_to_indexes = {k: [int(i) for i in v] for k, v in (data.get('suit_to_indexes') or {}).items() if k in SUIT_SET}
			suit_drawn_pos = {k: int(v) for k, v in (data.get('suit_drawn_pos') or {}).items() if k in SUIT_SET}
			redraw_used = {k: bool(v) for k, v in (data.get('redraw_used') or {}).items() if k in ELIGIBLE_REDRAW}
			current_step = int(data.get('current_step') or 0)
			return True
	except Exception:
		return False


def bootstrap() -> None:
	global all_cards, _initialized
	all_cards = load_cards()
	# Attempt to restore previous session; if invalid or absent, rebuild fresh
	if not try_load_session():
		build_suits()
	_initialized = True
	print(f"Materials dir: {MATERIALS_DIR}")
	print(f"Loaded cards: {len(all_cards)}")
	for suit in SUIT_ORDER:
		print(f"{suit}: {len(suit_to_indexes.get(suit, []))} available")


def ensure_bootstrap() -> None:
	if not _initialized or not all_cards:
		bootstrap()


@app.before_request
def _ensure_on_each_request():
	ensure_bootstrap()


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
	ensure_bootstrap()
	emit('state', current_state())


@socketio.on('draw')
def on_draw():
	ensure_bootstrap()
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
		suit_drawn_pos[current_suit] = len(drawn_indexes) - 1
		# Move to next suit position for the next draw
		current_step += 1
	# Broadcast updated state
	socketio.emit('state', current_state())
	save_session()


@socketio.on('redraw')
def on_redraw(payload):
	ensure_bootstrap()
	if not isinstance(payload, dict):
		return
	suit = (payload.get('suit') or '').strip().upper()
	if suit not in ELIGIBLE_REDRAW:
		return
	if redraw_used.get(suit):
		return
	pos = suit_drawn_pos.get(suit)
	if pos is None:
		return
	bucket = suit_to_indexes.get(suit) or []
	if not bucket:
		return
	# Replace the drawn card with a different one from the same suit
	new_idx = bucket.pop()
	drawn_indexes[pos] = new_idx
	redraw_used[suit] = True
	socketio.emit('state', current_state())
	save_session()


@socketio.on('reset')
def on_reset():
	ensure_bootstrap()
	build_suits()
	socketio.emit('state', current_state())
	save_session()


if __name__ == '__main__':
	bootstrap()
	port = int(os.environ.get('PORT', '5000'))
	socketio.run(app, host='0.0.0.0', port=port)

