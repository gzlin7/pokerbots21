'''
Parse poker gamelog into custom data structure
'''

import re
import eval7
import matplotlib.pyplot as plt
import pandas as pd
import statistics
import itertools

# assumes playing "A" vs "B"
GAME_LOG_FILE = 'game_log.txt'
A = "A"
B = "B"
_MONTE_CARLO_ITERS = 100

f = open(GAME_LOG_FILE)
loglines = f.readlines()

assignments = []

# parse hole EV data https://www.tightpoker.com/poker_hands.html
calculated_df = pd.read_csv('hole_evs.csv')
holes = calculated_df.Holes
strengths = calculated_df.EVs
starting_strengths = dict(zip(holes, strengths))

# rank order
values = dict(zip('23456789TJQKA', range(2, 15)))

class Board:
	def __init__(self, num, pre_inflation):
		self.num = num
		self.community_cards = []
		self.community_cards_per_street = {0: None, 3: None, 4: None, 5: None}
		self.actions_per_street = {0: [], 3: [], 4: [], 5: []}
		self.A_holes = []
		self.B_holes = []
		self.A_hole_ev = 0
		self.B_hole_ev = 0
		self.outcome = False
		self.pot = pre_inflation
		self.pips = {A : 0, B: 0}

	def __str__(self):
		return str(self.__class__) + ": " + str(self.__dict__)

class Round:
	def __init__(self, num):
		self.num = num
		self.boards = {1: None, 2: None, 3: None}
		for i in range(1, 4):
			board = Board(i, i * 2)
			self.boards[i] = board
		self.bankrolls = {A : 200, B : 200}
		self.deltas = {A : 0, B : 0}
		self.street = 0

	def __str__(self):
		return str(self.__class__) + ": " + str(self.__dict__)


def hole_to_key(hole):
	'''
    Converts a hole card list into a key that we can use to query our
    strength dictionary

    hole: list - A list of two card strings in the engine's format (Kd, As, Th, 7d, etc.)
    '''
	card_1 = hole[0]  # get all of our relevant info
	card_2 = hole[1]

	rank_1, suit_1 = card_1[0], card_1[1]  # card info
	rank_2, suit_2 = card_2[0], card_2[1]

	numeric_1, numeric_2 = rank_1, rank_2  # make numeric

	suited = suit_1 == suit_2  # off-suit or not
	suit_string = ' s' if suited else ''

	return rank_1 + rank_2 + suit_string


def get_ev(hole):
	hole_key = hole_to_key(hole)
	return starting_strengths[hole_key]


def calculate_strength(hole_cards, community_cards, iters, opp_hole = None):
	'''
    A Monte Carlo method meant to estimate the win probability of a pair of
    hole cards. Simlulates 'iters' games and determines the win rates of our cards

    Modified to take in opponent hole as well if we know that information (ie. during gamelog parsing)

    Arguments:
    hole: a list of our two hole cards
    iters: a integer that determines how many Monte Carlo samples to take
    '''

	deck = eval7.Deck()  # eval7 object!
	hole_cards = [eval7.Card(card) for card in hole_cards if card]  # card objects, used to evaliate hands
	community_cards = [eval7.Card(card) for card in community_cards if card]  # card objects, used to evaliate hands
	if opp_hole:
		opp_hole = [eval7.Card(card) for card in opp_hole if card]
		for card in opp_hole:
			deck.cards.remove(card)

	for card in hole_cards:  # remove cards that we know about! they shouldn't come up in simulations
		deck.cards.remove(card)

	for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
		deck.cards.remove(card)

	score = 0

	for _ in range(iters):  # take 'iters' samples
		deck.shuffle()  # make sure our samples are random

		_COMM = 5 - len(community_cards)  # the number of cards we need to draw

		if not opp_hole:
			_OPP = 2
		else:
			_OPP = 0

		draw = deck.peek(_COMM + _OPP)

		if not opp_hole:
			opp_hole = draw[: _OPP]

		hidden_community = draw[_OPP:]

		our_hand = hole_cards + community_cards + hidden_community  # the two showdown hands
		opp_hand = opp_hole + community_cards + hidden_community

		our_hand_value = eval7.evaluate(our_hand)  # the ranks of our hands (only useful for comparisons)
		opp_hand_value = eval7.evaluate(opp_hand)

		if our_hand_value > opp_hand_value:  # we win!
			score += 2

		elif our_hand_value == opp_hand_value:  # we tie.
			score += 1

		else:  # we lost....
			score += 0

	hand_strength = score / (2 * iters)  # this is our win probability!


	# print("sampling duration", sampling_duration)

	return hand_strength

def parse_hand(line):
	return line[line.index("[") + 1:line.index("]")].split()

def cards_to_class(cards):
	return [eval7.Card(card) for card in cards if card]

def eval_hands(hole_a, hole_b, board_cards):
	a_value = eval7.evaluate(cards_to_class(hole_a) + cards_to_class(board_cards))
	b_value = eval7.evaluate(cards_to_class(hole_b) + cards_to_class(board_cards))

	winner = ""

	if a_value > b_value:
		winner = A
	elif b_value > a_value:
		winner = B
	else:
		winner = "TIE"

	return winner, eval7.handtype(a_value), eval7.handtype(b_value)

rounds_data = []

cumulative_delta_a = 0
cumulative_delta_b = 0
cumulative_delta_a_series = []
cumulative_delta_b_series = []

bad_aggressions = {0: {A: 0, B: 0}, 3: {A: 0, B: 0}, 4: {A: 0, B: 0}, 5: {A: 0, B: 0}}
total_aggressions = {0: {A: 0, B: 0}, 3: {A: 0, B: 0}, 4: {A: 0, B: 0}, 5: {A: 0, B: 0}}

i = 0

while i < len(loglines):
	line = loglines[i]
	if line.startswith("Round #"):
		fold_winnings_A = 0
		fold_winnings_B = 0
		round_num = line.split()[1]
		round_num = int(round_num[1:len(round_num)-1])
		round_pkr = Round(round_num)
		while "awarded" not in line:
			i += 1
			line = loglines[i]
			line_arr = line.split()

			# new street
			if "River" in line or "Flop" in line or "Turn" in line:
				street_str_to_int = {"Flop": 0, "Turn": 4, "River": 5}
				if "Flop" in line:
					round_pkr.street = 3
				elif "Turn" in line:
					round_pkr.street = 4
				elif "River" in line:
					round_pkr.street = 5
				community_cards = parse_hand(line)
				board = int(line_arr[-1])
				round_pkr.boards[board].community_cards = community_cards
				round_pkr.boards[board].community_cards_per_street[round_pkr.street] = community_cards
				for board in range(1, 4):
					round_pkr.boards[board].pips = {A: 0, B: 0}

			if "assigns" in line:
				player = line_arr[0]
				hand = parse_hand(line)
				board = int(line_arr[-1])
				ev = get_ev(sorted(hand, key=lambda x: values[x[0]], reverse=True))
				if player == A:
					round_pkr.boards[board].A_holes = hand
					round_pkr.boards[board].A_hole_ev = ev
				else:
					round_pkr.boards[board].B_holes = hand
					round_pkr.boards[board].B_hole_ev = ev

			if "posts" in line:
				player = line_arr[0]
				blind_amt = int(line_arr[5])
				for board in range(1, 4):
					round_pkr.boards[board].pips[player] += blind_amt
					round_pkr.boards[board].pot += blind_amt
					round_pkr.bankrolls[player] -= blind_amt

			if "calls" in line or "raises" in line or "bets" in line or "folds" in line:
				player = line_arr[0]
				other_player = B if player == A else A
				board = int(line_arr[-1])

				a_strength = calculate_strength(round_pkr.boards[board].A_holes,
												round_pkr.boards[board].community_cards, _MONTE_CARLO_ITERS,
												round_pkr.boards[board].B_holes)
				b_strength = calculate_strength(round_pkr.boards[board].B_holes,
												round_pkr.boards[board].community_cards, _MONTE_CARLO_ITERS,
												round_pkr.boards[board].A_holes)
				if a_strength > b_strength:
					forecasted_winner = A
				elif b_strength > a_strength:
					forecasted_winner = B
				else:
					forecasted_winner = "TIE"
				# winner, a_hand_desc, b_hand_desc = eval_hands(round_pkr.boards[board].A_holes, round_pkr.boards[board].B_holes,
				# 		   round_pkr.boards[board].community_cards)

				if "calls" in line:
					continue_cost = round_pkr.boards[board].pips[other_player] - round_pkr.boards[board].pips[player]

					round_pkr.boards[board].pips[player] += continue_cost
					round_pkr.boards[board].pot += continue_cost
					round_pkr.bankrolls[player] -= continue_cost

					action = {"Type": "Call", "Player": player, "Cost": continue_cost, "Forecasted Winner": forecasted_winner}

					round_pkr.boards[board].actions_per_street[round_pkr.street].append(action)

					# not quite an aggression
					# if forecasted_winner != player:
					# 	bad_aggressions[player] += 1

				if "raises" in line:
					raise_to = int(line_arr[3])
					raise_cost = raise_to - round_pkr.boards[board].pips[player]

					round_pkr.boards[board].pips[player] += raise_cost
					round_pkr.boards[board].pot += raise_cost
					round_pkr.bankrolls[player] -= raise_cost

					action = {"Type": "Raise", "Player": player, "Cost": raise_cost, "To": raise_to,
							  "Forecasted Winner": forecasted_winner}

					round_pkr.boards[board].actions_per_street[round_pkr.street].append(action)

					total_aggressions[round_pkr.street][player] += 1

					if forecasted_winner != player:
						bad_aggressions[round_pkr.street][player] += 1

				if "bets" in line:
					bet_amount = int(line_arr[2])

					round_pkr.boards[board].pips[player] += bet_amount
					round_pkr.boards[board].pot += bet_amount
					round_pkr.bankrolls[player] -= bet_amount

					action = {"Type": "Bet", "Player": player, "Cost": bet_amount,
							  "Forecasted Winner": forecasted_winner}

					round_pkr.boards[board].actions_per_street[round_pkr.street].append(action)

					total_aggressions[round_pkr.street][player] += 1

					if forecasted_winner != player:
						bad_aggressions[round_pkr.street][player] += 1

				if "folds" in line:

					a_had_better = (A == forecasted_winner)
					tie = (forecasted_winner == "TIE")

					round_pkr.boards[board].outcome = {"Method": "Fold", "Winner": other_player, "A hand type": "not evaluated",
												   "B hand type": "not evaluated", "Winnings": round_pkr.boards[board].pot - round_pkr.boards[board].pips[other_player], "A_better_hand": a_had_better, "Tied Hands": tie}

					if other_player == A:
						fold_winnings_A += round_pkr.boards[board].pot
					else:
						fold_winnings_B += round_pkr.boards[board].pot

					action = {"Type": "Fold", "Player": player,
							  "Forecasted Winner": forecasted_winner}

					round_pkr.boards[board].actions_per_street[round_pkr.street].append(action)



			if "shows" in line:
				board = int(line_arr[-1])
				forecasted_winner, a_hand_desc, b_hand_desc = eval_hands(round_pkr.boards[board].A_holes, round_pkr.boards[board].B_holes, round_pkr.boards[board].community_cards)

				res = []
				if forecasted_winner == "TIE":
					round_pkr.boards[board].outcome = {"Method": "Showdown", "Winner": forecasted_winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round_pkr.boards[board].pot // 2 - round_pkr.boards[board].pips[other_player]} # not quite
					round_pkr.bankrolls[A] += round_pkr.boards[board].pot // 2
					round_pkr.bankrolls[B] += round_pkr.boards[board].pot // 2
				else:
					round_pkr.boards[board].outcome = {"Method": "Showdown", "Winner": forecasted_winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round_pkr.boards[board].pot - round_pkr.boards[board].pips[other_player]}
					round_pkr.bankrolls[forecasted_winner] += round_pkr.boards[board].pot

				# handled this showdown, skip next line - check that this doesn't break anything in the future, eg printing line by line
				i += 1

		if "awarded" in line:
			round_pkr.bankrolls[A] += fold_winnings_A
			round_pkr.bankrolls[B] += fold_winnings_B
			round_pkr.deltas[A] = round_pkr.bankrolls[A] - 200
			round_pkr.deltas[B] = round_pkr.bankrolls[B] - 200
			cumulative_delta_a += round_pkr.deltas[A]
			cumulative_delta_b += round_pkr.deltas[B]
			cumulative_delta_a_series.append(cumulative_delta_a)
			cumulative_delta_b_series.append(cumulative_delta_b)

		rounds_data.append(round_pkr)

	i += 1

num_rounds = len(rounds_data)
streets = [0,3,4,5]

# Win % and average winnings per board
win_count = {1: 0, 2:0, 3:0}
win_total_A = {1: 0, 2:0, 3:0}
win_total_B = {1: 0, 2:0, 3:0}

# Fold stats (who had stronger hand at time of fold?)
total_folds_A, total_folds_B = 0,0
bad_folds_A, bad_folds_B = 0,0

# Overall per-game betting stats
street_folds_A, street_folds_B = {0: 0, 3:0, 4:0, 5:0}, {0: 0, 3:0, 4:0, 5:0}

# Showdown stats
showdown_count = {1: 0, 2:0, 3:0}
showdown_wins_A = {1: 0, 2:0, 3:0}

# EV stats
evs_A = {1: [], 2:[], 3:[]}
evs_B = {1: [], 2:[], 3:[]}

for round_pkr in rounds_data:
	for i in range(1,4):
		outcome = round_pkr.boards[i].outcome
		a_won = outcome["Winner"] == A

		# Win % and average winnings per board
		if a_won:
			win_count[i] += 1
			win_total_A[i] += outcome["Winnings"]
		else:
			win_total_B[i] += outcome["Winnings"]

		# Fold stats (who had stronger hand at time of fold?)
		if outcome["Method"] == "Fold":
			if a_won:
				total_folds_B += 1
				if (not outcome["A_better_hand"]) or outcome["Tied Hands"]:
					bad_folds_B += 1
				street_folds_B[len(round_pkr.boards[i].community_cards)] += 1
			else:
				total_folds_A += 1
				if outcome["A_better_hand"] or outcome["Tied Hands"]:
					bad_folds_A += 1
				street_folds_A[len(round_pkr.boards[i].community_cards)] += 1


		# Showdown stats
		if outcome["Method"] == "Showdown":
			showdown_count[i] += 1
			if a_won:
				showdown_wins_A[i] += 1

		# EV stats
		evs_A[i].append(round_pkr.boards[i].A_hole_ev)
		evs_B[i].append(round_pkr.boards[i].B_hole_ev)

def num_to_str(number):
	return str(round(number,2))

print("===== WINNINGS =====")
for player in [A, B]:
	for i in range(1, 4):
		win_percent = win_count[i] / num_rounds
		win_percent = win_percent if player == A else 1 - win_percent
		showdown_win_percent = showdown_wins_A[i] / showdown_count[i]
		showdown_win_percent = showdown_win_percent if player == A else 1 - showdown_win_percent
		total_winnings = win_total_A[i] if player == A else win_total_B[i]
		avg_winnings = win_total_A[i] if player == A else win_total_B[i]
		avg_winnings /= num_rounds
		print(player + " Board " + str(i) +
			  ": win% " + num_to_str(win_percent) +
			  "  showdown win% " + num_to_str(showdown_win_percent) +
			  "  total winnings " + num_to_str(total_winnings) +
			  "  avg winnings " + num_to_str(avg_winnings)
			  )
	print()

print("===== PLAYER BETTING =====")
num_games = 3 * num_rounds
print("A:")
print("Fold rate: " + str(round(total_folds_A / num_games, 3)))
print("Bad Fold: " + str(round(bad_folds_A / total_folds_A, 3)))
print()
for street in [0,3,4,5]:
	print("Street " + str(street) + ": " + str(street_folds_A[street]))
print()
print("B:")
print("Fold rate: " + str(round(total_folds_B / num_games, 3)))
print("Bad Fold: " + str(round(bad_folds_B / total_folds_B, 3)))
print()
for street in [0,3,4,5]:
	print("Street " + str(street) + ": " + str(street_folds_B[street]))
print()

print("===== HOLE ALLOCATION =====")
num_games = 3 * num_rounds
for player in [A, B]:
	for i in range(1,4):
		evs = evs_A if player == A else evs_B
		print(player + " Board " + str(i) + ": " + "mean " + str(round(statistics.mean(evs[i]), 3)) +
			  "  stdev " + str(round(statistics.stdev(evs[i]), 3)))
	print()

# for i in range(0, 10):
# 	rounds_data_obj = rounds_data[i]
# 	print(rounds_data_obj.deltas[A], rounds_data_obj.deltas[B])

print("Bad aggressions (raises/bets) per street:", bad_aggressions)
# for player in A, B:
# 	print(player, ":", bad_aggressions[player] / total_aggressions[player])
# print()

plt.plot(cumulative_delta_a_series)
plt.ylabel('Player A cumulative delta')
plt.show()

plt.plot(cumulative_delta_b_series)
plt.ylabel('Player B cumulative delta')
plt.show()

