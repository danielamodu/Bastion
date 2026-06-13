import time
import json
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
    resp = make_request('POST', f"{BASE_URL}/agent/wallet/transfer/native", payload)
    return resp

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

def decide_action(table_state, total_chips, lives_remaining):
    global preflop_raiser_tables
    allowed = table_state.get('allowedActions', {})
    if not allowed:
        return None, ""

    table_id = table_state.get('id')
    my_seat_num = table_state.get('selfSeatNumber')
    my_seat = next((s for s in table_state.get('seats', []) if s.get('seatNumber') == my_seat_num), None)
    
    hole_cards = my_seat.get('holeCards') if my_seat else None
    board_cards = table_state.get('boardCards') or []
    pot = table_state.get('potChips', 0)
    stack = my_seat.get('stackChips', 0)
    
    call_amt = allowed.get('callToAmount', 0) or 0
    pot_odds = call_amt / (pot + call_amt) if (pot + call_amt) > 0 else 1
    
    def try_check_or_fold(reason):
        if allowed.get('canCheck'):
            return {"action": "check"}, f"Checking. {reason}"
        if allowed.get('canCall') and pot_odds < 0.25:
            return {"action": "call", "amount": call_amt}, f"Pot odds {pot_odds:.2f} < 25%, calling. {reason}"
        if allowed.get('canFold'):
            return {"action": "fold"}, f"Folding. {reason}"
        return {"action": "check"}, "Fallback check."

    if not hole_cards or len(hole_cards) < 2:
        return try_check_or_fold("No visible cards.")

    ranks = '23456789TJQKA'
    def card_value(card_str):
        return ranks.index(card_str[0]) if card_str[0] in ranks else -1

    val1 = card_value(hole_cards[0])
    val2 = card_value(hole_cards[1])
    suit1 = hole_cards[0][1] if len(hole_cards[0]) > 1 else ''
    suit2 = hole_cards[1][1] if len(hole_cards[1]) > 1 else ''
    
    is_pair = val1 == val2
    is_suited = suit1 == suit2
    high_card = max(val1, val2)
    low_card = min(val1, val2)
    
    # Modes
    is_chip_leader = total_chips > 1500
    is_short_stack = total_chips < 200 and lives_remaining > 0

    # Shove mode
    if is_short_stack:
        is_shove_hand = is_pair or high_card == 12 or (is_suited and abs(val1 - val2) == 1)
        if is_shove_hand:
            amt = allowed.get('maxCommit', stack)
            if allowed.get('canAllIn'):
                return {"action": "all-in", "amount": amt}, "Short stack with lives! Shoving wide!"
            elif allowed.get('canRaise'):
                return {"action": "raise", "amount": amt}, "Short stack with lives! Shoving wide!"
            elif allowed.get('canBet'):
                return {"action": "bet", "amount": amt}, "Short stack with lives! Shoving wide!"

    # 1. Preflop Logic
    if len(board_cards) == 0:
        # Reset tracking for new hand
        if pot <= table_state.get('bigBlindChips', 10) * 3:
            preflop_raiser_tables.discard(table_id)

        # Premium: 77+, AJ+, KQ
        is_premium = (is_pair and high_card >= 5) or \
                     (high_card == 12 and low_card >= 9) or \
                     (high_card == 11 and low_card == 10)
                     
        if is_chip_leader:
            is_premium = (is_pair and high_card >= 8) or (high_card == 12 and low_card >= 10)

        is_playable = is_premium or is_pair or \
                      high_card >= 11 or \
                      (high_card == 10 and low_card >= 7) or \
                      (is_suited and high_card >= 8) or \
                      (abs(val1 - val2) <= 2 and high_card >= 7)

        if is_playable:
            if allowed.get('canRaise'):
                amt = max(allowed.get('minRaiseTo', 0), table_state.get('bigBlindChips', 10) * 3)
                amt = min(amt, allowed.get('maxCommit', stack))
                preflop_raiser_tables.add(table_id)
                return {"action": "raise", "amount": amt}, "Playable/Premium preflop, applying pressure!"
            elif allowed.get('canBet'):
                amt = max(allowed.get('minBet', 0), table_state.get('bigBlindChips', 10) * 3)
                amt = min(amt, allowed.get('maxCommit', stack))
                preflop_raiser_tables.add(table_id)
                return {"action": "bet", "amount": amt}, "Playable/Premium preflop, applying pressure!"
            else:
                return try_check_or_fold("Playable but cannot raise/bet.")
                
        return try_check_or_fold("Trash hand preflop.")
            
    # 2. Postflop Logic
    else:
        board_vals = [card_value(c) for c in board_cards]
        hit_pair = val1 in board_vals or val2 in board_vals
        
        all_suits = [c[1] for c in hole_cards + board_cards if len(c) > 1]
        suit_counts = {s: all_suits.count(s) for s in set(all_suits)}
        made_flush = any(c >= 5 for c in suit_counts.values())
        flush_draw = any(c == 4 for c in suit_counts.values())
        
        # River showdown calling logic
        if len(board_cards) == 5 and allowed.get('canCall') and call_amt > 0:
            top_board_val = max(board_vals) if board_vals else -1
            has_top_pair_or_better = (is_pair and val1 > top_board_val) or (val1 == top_board_val) or (val2 == top_board_val) or made_flush
            if not has_top_pair_or_better and pot_odds > 0.15:
                if allowed.get('canFold'):
                    return {"action": "fold"}, f"Folding to river aggression without top pair+ (odds {pot_odds:.2f})"
        
        is_strong_postflop = is_pair or hit_pair or made_flush
        if is_chip_leader:
            is_strong_postflop = (is_pair and high_card >= 8) or (hit_pair and high_card >= 10) or made_flush
            
        if is_strong_postflop or flush_draw:
            if allowed.get('canRaise') or allowed.get('canBet'):
                action = "raise" if allowed.get('canRaise') else "bet"
                min_amt = allowed.get('minRaiseTo', 0) if action == "raise" else allowed.get('minBet', 0)
                amt = max(min_amt, int(pot * 0.70))
                amt = min(amt, allowed.get('maxCommit', stack))
                return {"action": action, "amount": amt}, f"Strong hand/draw, applying pressure (70% pot: {amt})."
            else:
                return try_check_or_fold("Strong hand/draw but cannot raise/bet.")
            
        # Probe bet logic
        is_in_position = my_seat_num == table_state.get('dealerSeatNumber')
        is_checked_to = allowed.get('canCheck') and allowed.get('canBet')
        if table_id in preflop_raiser_tables and is_in_position and is_checked_to and pot > 30:
            amt = max(allowed.get('minBet', 0), int(pot * 0.33))
            amt = min(amt, allowed.get('maxCommit', stack))
            if amt > 0:
                return {"action": "bet", "amount": amt}, "Probe betting missed board."
                
        return try_check_or_fold("Missed board.")

logging.info("Starting updated Poker Bot (Hyper-Aggressive 5 Lives Strategy)...")

last_heartbeat = 0
HEARTBEAT_INTERVAL = 60 # 1 min
last_tickets_check = 0
tickets_cache = 0

while True:
    try:
        current_time = time.time()
        if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
            logging.info("Heartbeat: Bot is alive and polling for actions.")
            last_heartbeat = current_time

        # Update tickets cache every 5 minutes
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
        
        # Auto-Rebuy
        if chip_state == 'busted':
            logging.info("We are BUSTED! Attempting auto-rebuy...")
            try_join_or_rebuy("rebuy")
            time.sleep(2)
            continue
            
        # Multi-tabling: Join up to 10 tables if we have chips and aren't busted
        if chip_state in ['available', 'locked_in_play'] and active_tables < 10:
            # Throttle join requests to avoid spamming
            if current_time % 5 < 1:  
                logging.info(f"Active tables: {active_tables}. Attempting to join another table...")
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
            
            logging.info(f"Submitting action: {payload}")
            act_resp = make_request('POST', f"{BASE_URL}/texas/action", payload)
            
    except Exception as e:
        logging.error(f"Exception in loop: {str(e)}")
        time.sleep(2)
    
    time.sleep(0.5)
