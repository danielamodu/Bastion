import time
import json
import random
import urllib.request
import urllib.error
import logging

logging.basicConfig(filename='poker_bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    with open('.arena-credentials', 'r') as f:
        creds = json.load(f)
        API_KEY = creds['apiKey']
except Exception as e:
    logging.error(f"Failed to load credentials: {e}")
    exit(1)

COMPETITION_ID = "cmq6l1gnq0lkz60y9i9d9eca1"
BASE_URL = "https://arena.dev.fun/api/arena"
HEADERS = {
    "x-arena-api-key": API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

def make_request(method, url, data=None):
    req = urllib.request.Request(url, headers=HEADERS, method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if e.code != 402:
            logging.error(f"HTTPError: {e.code} - {error_body}")
        return json.loads(error_body) if e.code == 402 else None
    except Exception as e:
        logging.error(f"Request error: {e}")
        return None

def transfer_funds(chain, to_addr, amount):
    payload = {"chain": chain, "to": to_addr, "amount": str(amount)}
    return make_request('POST', f"{BASE_URL}/agent/wallet/transfer/native", payload)

def get_available_tickets():
    resp = make_request('GET', f"{BASE_URL}/agent/sponsor-tickets")
    if not resp or 'tickets' not in resp:
        return 0
    return sum(1 for t in resp['tickets'] if t['status'] == 'available')

def try_join_or_rebuy(action="join", tx_hash=None):
    payload = {"competitionId": COMPETITION_ID}
    if tx_hash:
        payload["txHash"] = tx_hash
    resp = make_request('POST', f"{BASE_URL}/texas/{action}", payload)
    if not resp:
        return False
    if resp.get('error') == "Payment required":
        pr = resp.get('paymentRequirements', {})
        if pr.get('sponsored'):
            logging.info(f"Using sponsor ticket. Transferring {pr['amount']} to {pr['to']}")
            tx_resp = transfer_funds(pr['chain'], pr['to'], pr['amount'])
            if tx_resp and tx_resp.get('txHash'):
                logging.info(f"Transfer success: {tx_resp['txHash']}. Retrying {action}...")
                return try_join_or_rebuy(action, tx_resp['txHash'])
        else:
            logging.error("Payment required but not sponsored!")
            return False
    return True

preflop_raiser_tables = set()

RANKS = '23456789TJQKA'

def get_rank(card_str):
    return RANKS.index(card_str[0])

def get_suit(card_str):
    return card_str[1]

def evaluate_hand(hole_cards, board_cards):
    all_cards = hole_cards + board_cards
    if len(all_cards) < 2:
        return {'hand_rank': 0, 'description': 'No hand'}

    ranks = sorted([get_rank(c) for c in all_cards], reverse=True)
    suits = [get_suit(c) for c in all_cards]
    rank_counts = {r: ranks.count(r) for r in set(ranks)}

    # Flush check
    suit_counts = {s: suits.count(s) for s in set(suits)}
    flush_suit = next((s for s, c in suit_counts.items() if c >= 5), None)

    # Straight check
    unique_ranks = sorted(list(set(ranks)), reverse=True)
    straight_high = -1
    if len(unique_ranks) >= 5:
        for i in range(len(unique_ranks) - 4):
            window = unique_ranks[i:i+5]
            if window[0] - window[4] == 4 and len(set(window)) == 5:
                straight_high = window[0]
                break
        # Wheel: A-2-3-4-5
        if straight_high == -1 and 12 in unique_ranks and all(r in unique_ranks for r in [0,1,2,3]):
            straight_high = 3

    # Straight flush
    if flush_suit and straight_high != -1:
        flush_ranks = sorted(list(set(get_rank(c) for c in all_cards if get_suit(c) == flush_suit)), reverse=True)
        if len(flush_ranks) >= 5:
            for i in range(len(flush_ranks) - 4):
                window = flush_ranks[i:i+5]
                if window[0] - window[4] == 4 and len(set(window)) == 5:
                    return {'hand_rank': 9, 'description': 'Straight Flush'}
            if 12 in flush_ranks and all(r in flush_ranks for r in [0,1,2,3]):
                return {'hand_rank': 9, 'description': 'Straight Flush'}

    if any(c == 4 for c in rank_counts.values()):
        return {'hand_rank': 8, 'description': 'Four of a Kind'}

    counts = sorted(rank_counts.values(), reverse=True)
    if counts[0] == 3 and counts[1] >= 2:
        return {'hand_rank': 7, 'description': 'Full House'}

    if flush_suit:
        return {'hand_rank': 6, 'description': 'Flush'}

    if straight_high != -1:
        return {'hand_rank': 5, 'description': 'Straight'}

    if counts[0] == 3:
        return {'hand_rank': 4, 'description': 'Three of a Kind'}

    pairs = [r for r, c in rank_counts.items() if c == 2]
    if len(pairs) >= 2:
        return {'hand_rank': 3, 'description': 'Two Pair'}
    if len(pairs) == 1:
        return {'hand_rank': 2, 'description': 'One Pair'}

    return {'hand_rank': 1, 'description': 'High Card'}

def decide_action(table_state, total_chips, lives_remaining):
    global preflop_raiser_tables
    allowed = table_state.get('allowedActions', {})
    if not allowed:
        return None, ""

    table_id = table_state.get('id')
    my_seat_num = table_state.get('selfSeatNumber')
    seats = table_state.get('seats', [])
    my_seat = next((s for s in seats if s.get('seatNumber') == my_seat_num), None)

    hole_cards = my_seat.get('holeCards') if my_seat else None
    board_cards = table_state.get('boardCards') or []
    pot = table_state.get('potChips', 0)
    stack = my_seat.get('stackChips', 0)
    big_blind = table_state.get('bigBlindChips', 10)
    dealer_seat = table_state.get('dealerSeatNumber', 0)
    num_seats = len(seats) or 6

    call_amt = allowed.get('callToAmount', 0) or 0
    min_raise_to = allowed.get('minRaiseTo', 0) or 0
    min_bet = allowed.get('minBet', 0) or 0
    max_commit = allowed.get('maxCommit', stack) or stack
    pot_odds = call_amt / (pot + call_amt) if (pot + call_amt) > 0 else 1

    def make_bet(fraction, reason):
        target = int(pot * fraction)
        amt = max(min_raise_to if allowed.get('canRaise') else min_bet, target)
        amt = min(amt, max_commit)
        # ensure we're actually raising, not min-clicking below call
        if amt <= call_amt:
            amt = min(call_amt + max(min_bet, big_blind), max_commit)
        if allowed.get('canRaise') and amt > call_amt:
            return {"action": "raise", "amount": amt}, reason
        if allowed.get('canBet') and amt > 0:
            return {"action": "bet", "amount": amt}, reason
        if allowed.get('canCall'):
            return {"action": "call", "amount": call_amt}, reason
        return try_check_or_fold(reason)

    def try_check_or_fold(reason):
        if allowed.get('canCheck'):
            return {"action": "check"}, f"Checking. {reason}"
        if allowed.get('canCall') and pot_odds < 0.20:
            return {"action": "call", "amount": call_amt}, f"Pot odds {pot_odds:.2f} ok, calling. {reason}"
        if allowed.get('canFold'):
            return {"action": "fold"}, f"Folding. {reason}"
        return {"action": "check"}, "Fallback check."

    if not hole_cards or len(hole_cards) < 2:
        return try_check_or_fold("No visible cards.")

    hand_eval = evaluate_hand(hole_cards, board_cards)
    hand_rank = hand_eval['hand_rank']
    hand_desc = hand_eval['description']

    val1 = get_rank(hole_cards[0])
    val2 = get_rank(hole_cards[1])
    suit1 = get_suit(hole_cards[0])
    suit2 = get_suit(hole_cards[1])
    is_pair = val1 == val2
    is_suited = suit1 == suit2
    high_card = max(val1, val2)
    low_card = min(val1, val2)

    is_chip_leader = total_chips > 1500
    is_short_stack = total_chips < 200 and lives_remaining > 0
    my_position = (my_seat_num - dealer_seat + num_seats) % num_seats
    is_late_position = my_position <= 1
    num_board = len(board_cards)

    # Shove mode
    if is_short_stack:
        is_shove_hand = is_pair or high_card >= get_rank('T') or \
                        (is_suited and abs(val1 - val2) <= 2) or \
                        (abs(val1 - val2) == 1 and high_card >= get_rank('7'))
        if is_shove_hand:
            if allowed.get('canAllIn'):
                return {"action": "all-in", "amount": max_commit}, "Short stack shove!"
            return make_bet(1.0, "Short stack shove!")

    # ── PREFLOP ──
    if num_board == 0:
        if pot <= big_blind * 3:
            preflop_raiser_tables.discard(table_id)

        # 2-7 jackpot bluff (1% chance)
        is_27o = not is_suited and set([val1, val2]) == {get_rank('2'), get_rank('7')}
        if is_27o and random.random() < 0.01:
            return make_bet(3.0, "2-7 offsuit jackpot bluff!")

        if is_chip_leader:
            is_premium = (is_pair and high_card >= get_rank('8')) or \
                         (high_card == get_rank('A') and low_card >= get_rank('T')) or \
                         (high_card == get_rank('K') and low_card == get_rank('Q'))
        else:
            is_premium = (is_pair and high_card >= get_rank('7')) or \
                         (high_card == get_rank('A') and low_card >= get_rank('J')) or \
                         (high_card == get_rank('K') and low_card == get_rank('Q'))

        is_playable = is_premium or is_pair or \
                      (high_card >= get_rank('J') and (is_late_position or is_suited)) or \
                      (is_suited and high_card >= get_rank('9')) or \
                      (abs(val1 - val2) <= 2 and high_card >= get_rank('8') and is_late_position)

        if is_playable:
            # 3x BB open, or 2.5x facing a raise
            bet_amount = big_blind * 3 if call_amt == 0 else max(int(call_amt * 2.5), big_blind * 4)
            preflop_raiser_tables.add(table_id)
            return make_bet(bet_amount / max(pot, 1), f"Preflop pressure ({hand_desc})")

        return try_check_or_fold("Trash hand preflop.")

    # ── POSTFLOP ──
    # Draw detection
    all_cards_here = hole_cards + board_cards
    all_suits_here = [get_suit(c) for c in all_cards_here]
    suit_cnt = {s: all_suits_here.count(s) for s in set(all_suits_here)}
    flush_draw = any(c == 4 for c in suit_cnt.values())

    all_ranks_here = sorted(list(set(get_rank(c) for c in all_cards_here)))
    has_straight_draw = False
    if len(all_ranks_here) >= 4:
        for i in range(len(all_ranks_here) - 3):
            window = all_ranks_here[i:i+4]
            span = window[-1] - window[0]
            if span <= 4:
                missing = span + 1 - len(window)
                if missing <= 1:
                    has_straight_draw = True
                    break

    is_strong_draw = flush_draw or has_straight_draw
    is_strong_hand = hand_rank >= 5   # straight or better
    is_medium_hand = hand_rank >= 2   # one pair or better

    # Strong hand or semi-bluff with draw
    if is_strong_hand:
        return make_bet(0.70, f"Strong hand ({hand_desc}), betting for value.")

    if is_strong_draw and pot_odds < 0.40:
        return make_bet(0.60, f"Semi-bluff draw ({hand_desc}).")

    # Medium hand — check/call only, no bloating the pot
    if is_medium_hand:
        if allowed.get('canCheck'):
            return {"action": "check"}, f"Checking medium hand ({hand_desc})."
        if allowed.get('canCall') and pot_odds < 0.30:
            return {"action": "call", "amount": call_amt}, f"Calling medium hand ({hand_desc}) at {pot_odds:.2f}."
        return try_check_or_fold(f"Medium hand ({hand_desc}), too expensive.")

    # Probe bet — flop only, in position, preflop raiser, checked to
    is_checked_to = allowed.get('canCheck') and allowed.get('canBet')
    is_in_position = my_seat_num == dealer_seat
    if num_board == 3 and table_id in preflop_raiser_tables and is_in_position and is_checked_to and pot > big_blind * 3:
        return make_bet(0.33, "Probe bet on flop, missed board.")

    # River: tight calling logic
    if num_board == 5 and allowed.get('canCall') and call_amt > 0:
        if hand_rank >= 3 and pot_odds < 0.20:
            return {"action": "call", "amount": call_amt}, f"River call with {hand_desc}."
        return {"action": "fold"}, f"Folding river, weak hand ({hand_desc})."

    return try_check_or_fold("Missed board.")

logging.info("Starting Poker Bot v3 (Manus + Claude fixes)...")

last_heartbeat = 0
HEARTBEAT_INTERVAL = 60
last_tickets_check = 0
tickets_cache = 0

while True:
    try:
        current_time = time.time()
        if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
            logging.info("Heartbeat: Bot is alive and polling for actions.")
            last_heartbeat = current_time

        if current_time - last_tickets_check >= 300:
            tickets_cache = get_available_tickets()
            last_tickets_check = current_time

        data = make_request('GET', f"{BASE_URL}/texas/pending-actions?competitionId={COMPETITION_ID}")
        if not data:
            time.sleep(2)
            continue

        participant = data.get('participant', {})
        chip_state = participant.get('chipState')
        total_chips = participant.get('totalChips', 0)
        runner = data.get('runner', {})
        active_tables = runner.get('activeTableCount', 0)

        if chip_state == 'busted':
            logging.info("BUSTED! Attempting auto-rebuy...")
            try_join_or_rebuy("rebuy")
            time.sleep(2)
            continue

        if chip_state in ['available', 'locked_in_play'] and active_tables < 10:
            if current_time % 5 < 1:
                logging.info(f"Active tables: {active_tables}. Joining another...")
                try_join_or_rebuy("join")
                time.sleep(1)

        tables = data.get('tables', [])
        if not tables:
            time.sleep(2)
            continue

        for table in tables:
            action_obj, msg = decide_action(table, total_chips, tickets_cache)
            if not action_obj:
                continue
            payload = {
                "competitionId": COMPETITION_ID,
                "tableId": table['id'],
                "action": action_obj['action'],
                "message": msg
            }
            if 'amount' in action_obj and action_obj['action'] not in ['fold', 'check']:
                payload['amount'] = action_obj['amount']
            logging.info(f"Action: {payload}")
            make_request('POST', f"{BASE_URL}/texas/action", payload)

    except Exception as e:
        logging.error(f"Exception in loop: {str(e)}")
        time.sleep(2)

    time.sleep(0.5)