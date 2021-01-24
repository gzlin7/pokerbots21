'''
Record a set of actions for a player we are trying to model
Train opponent model using actions csv at https://colab.research.google.com/drive/1Bw1D8HyClH456cXAmM6dssDQQxmILobI?usp=sharing

TODO: record board number, average opponent EV per board, opponent tightness/agg/fold rate over the course of game, during this game, ...
TODO: parse whether the modeled player is A or B based on filename -> play a lot more games and gather more data
'''
import random
import re
import eval7
import matplotlib.pyplot as plt
import pandas as pd
import statistics
import itertools

import os


class Action:
	def __init__(self, type, strength, potodds, bankroll, opp_raises, street, board, opp_tightness=None,
				 opp_aggressiveness=None):
		self.type = type
		self.strength = strength
		self.potodds = potodds
		self.bankroll = bankroll
		self.opp_raises = opp_raises
		self.street = street
		self.board = board

	def __str__(self):
		return str(self.__class__) + ": " + str(self.__dict__)


actions = []

directory = r'example_repo/logs'

for filename in os.listdir(directory):

	print(filename)

	# assumes playing "A" vs "B"
	GAME_LOG_FILE = os.path.join(directory, filename)

	A = "A"
	B = "B"
	_MONTE_CARLO_ITERS = 100

	# speed up by avoiding monte carlo simulation to determine strength, instead naive comparison of current hand strength using eval8
	ACCURATE_STRENGTH_SIM = True

	class Board:
		def __init__(self, num, pre_inflation):
			self.num = num
			self.community_cards = []
			self.community_cards_per_street = {0: None, 3: None, 4: None, 5: None}
			self.actions_per_street = {0: [], 3: [], 4: [], 5: []}
			self.raises_per_street = {A: {0: 0, 3: 0, 4: 0, 5: 0}, B: {0: 0, 3: 0, 4: 0, 5: 0}}
			self.raises = {A: 0, B: 0}
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
			self.A_cards = []
			self.B_cards = []
			self.eval_hand_memo = {}
			self.eval_count = 0

		def __str__(self):
			return str(self.__class__) + ": " + str(self.__dict__)

	# parse hole EV data https://www.tightpoker.com/poker_hands.html
	calculated_df = pd.read_csv('hole_evs.csv')
	holes = calculated_df.Holes
	strengths = calculated_df.EVs
	starting_strengths = dict(zip(holes, strengths))

	# rank order
	values = dict(zip('23456789TJQKA', range(2, 15)))

	# build dict of EVs to sets of eval7 hand

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

	ev_to_eval7hands = dict()
	for hand in list(itertools.combinations(list(eval7.Deck()), 2)):
		ev = get_ev(sorted([str(hand[0]), str(hand[1])],
								key=lambda x: values[x[0]], reverse=True))
		ev_to_eval7hands.setdefault(ev, set())
		ev_to_eval7hands[ev].add(hand)

	evs_descending = sorted(
		ev_to_eval7hands.keys(), reverse=True)

	def num_to_str(number):
		return str(round(number,2))




	# new, optimized version from updated bots
	def tight_calculate_strength(hole_cards, my_cards, community_cards, iters, weight=None, board=3, opp_hole=None):
		'''
		Arguments:
		hole_cards: a list of our two hole cards
		my_cards: a list of all our 6 initial hole cards, since they can't appear elsewhere
		community_cards: visible community cars
		iters: # of MC iterations
		weight: optional parameter of how likely our opponent plays particular hands (hole strength threshhold)
		'''

		deck = eval7.Deck()  # eval7 object!

		# card objects, used to evaliate hands
		hole_cards = [eval7.Card(card) for card in hole_cards]

		my_cards = [eval7.Card(card) for card in my_cards]


		# card objects, used to evaliate hands
		community_cards = [eval7.Card(card) for card in community_cards]

		# speed up parsing if we don't care about strength simulation - just return eval7 evaluate score
		if not ACCURATE_STRENGTH_SIM:
			return eval7.evaluate(hole_cards + community_cards)

		if opp_hole:
			opp_hole = [eval7.Card(card) for card in opp_hole if card]
			for card in opp_hole:
				deck.cards.remove(card)

		for card in my_cards:  # remove cards that we know about! they shouldn't come up in simulations
			deck.cards.remove(card)

		for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
			deck.cards.remove(card)

		# get more likely opp hands based on weight
		# avoid repeats
		opp_hands_to_try = set()
		score = 0

		possible_hands = set(itertools.combinations(deck, 2))

		for ev in evs_descending:
			for hand in ev_to_eval7hands[ev]:
				if hand in possible_hands:
					# TODO: better strength weighting
					ev = min(1, ev + 0.2)
					if random.random() < ev and hand not in opp_hands_to_try:
						opp_hands_to_try.add(hand)
					if len(opp_hands_to_try) >= iters:
						break

		for opp_hole in opp_hands_to_try:

			# the number of cards we need to draw
			_COMM = 5 - len(community_cards)
			_OPP = 2

			draw = deck.sample(_COMM + _OPP)

			hidden_community = draw[_OPP:]

			our_hand = hole_cards + community_cards + \
					   hidden_community  # the two showdown hands
			opp_hand = list(opp_hole) + community_cards + hidden_community
			our_key = frozenset(our_hand)
			opp_key = frozenset(opp_hand)

			if our_key not in curr_round.eval_hand_memo:
				# the ranks of our hands (only useful for comparisons)
				our_hand_value = eval7.evaluate(our_hand)
				curr_round.eval_hand_memo[our_key] = our_hand_value
				curr_round.eval_count += 1
			else:
				our_hand_value = curr_round.eval_hand_memo[our_key]

			if opp_key not in curr_round.eval_hand_memo:
				opp_hand_value = eval7.evaluate(opp_hand)
				curr_round.eval_hand_memo[opp_key] = opp_hand_value
				curr_round.eval_count += 1
			else:
				opp_hand_value = curr_round.eval_hand_memo[opp_key]

			if our_hand_value > opp_hand_value:  # we win!
				score += 2

			elif our_hand_value == opp_hand_value:  # we tie.
				score += 1

			else:  # we lost....
				score += 0

		# this is our win probability!
		hand_strength = score / (2 * len(opp_hands_to_try))

		# print("sampling duration", sampling_duration)

		return hand_strength


	def calculate_strength(hole_cards, my_cards, community_cards, iters):
		'''
		A Monte Carlo method meant to estimate the win probability of a pair of
		hole cards. Simlulates 'iters' games and determines the win rates of our cards

		Arguments:
		hole: a list of our two hole cards
		iters: a integer that determines how many Monte Carlo samples to take
		'''

		deck = eval7.Deck()  # eval7 object!
		hole_cards = [eval7.Card(card) for card in hole_cards if card]  # card objects, used to evaliate hands
		my_cards = [eval7.Card(card) for card in my_cards]
		community_cards = [eval7.Card(card) for card in community_cards if card]  # card objects, used to evaliate hands

		for card in my_cards:  # remove cards that we know about! they shouldn't come up in simulations
			deck.cards.remove(card)

		for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
			deck.cards.remove(card)

		score = 0

		for _ in range(iters):  # take 'iters' samples

			_COMM = 5 - len(community_cards)  # the number of cards we need to draw
			_OPP = 2

			draw = deck.sample(_COMM + _OPP)

			opp_hole = draw[: _OPP]
			hidden_community = draw[_OPP:]

			our_hand = hole_cards + community_cards + hidden_community  # the two showdown hands
			opp_hand = opp_hole + community_cards + hidden_community

			our_key = frozenset(our_hand)
			opp_key = frozenset(opp_hand)

			if our_key not in curr_round.eval_hand_memo:
				our_hand_value = eval7.evaluate(our_hand)  # the ranks of our hands (only useful for comparisons)
				curr_round.eval_hand_memo[our_key] = our_hand_value
				curr_round.eval_count += 1
			else:
				our_hand_value = curr_round.eval_hand_memo[our_key]

			if opp_key not in curr_round.eval_hand_memo:
				opp_hand_value = eval7.evaluate(opp_hand)
				curr_round.eval_hand_memo[opp_key] = opp_hand_value
				curr_round.eval_count += 1
			else:
				opp_hand_value = curr_round.eval_hand_memo[opp_key]

			if our_hand_value > opp_hand_value:  # we win!
				score += 2

			elif our_hand_value == opp_hand_value:  # we tie.
				score += 1

			else:  # we lost....
				score += 0

		hand_strength = score / (2 * iters)  # this is our win probability!


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

	cumulative_delta_a = 0
	cumulative_delta_b = 0
	cumulative_delta_a_series = []
	cumulative_delta_b_series = []

	bad_aggressions = {0: {A: 0, B: 0}, 3: {A: 0, B: 0}, 4: {A: 0, B: 0}, 5: {A: 0, B: 0}}
	total_aggressions = {0: {A: 0, B: 0}, 3: {A: 0, B: 0}, 4: {A: 0, B: 0}, 5: {A: 0, B: 0}}



	######################################################################

	# store parsed data
	rounds_data = []

	# read in game log file
	f = open(GAME_LOG_FILE)
	loglines = f.readlines()

	# output file
	outfile = open("annotated_gamelog.txt", "w")

	# loop over game log
	i = 0
	while i < len(loglines):
		line = loglines[i]
		line_arr = line.split()

		outfile.write(line)

		# new round
		if line.startswith("Round #"):

			# reset winnings from opponent folds - factored into bankroll delta at end of round
			fold_winnings_A = 0
			fold_winnings_B = 0

			round_num = int(line.split()[1][1:len(line.split()[1])-1])
			curr_round = Round(round_num)

			i += 1

			while "awarded" not in loglines[i]:
				line = loglines[i]
				line_arr = line.split()

				if "dealt" in line:
					player = line_arr[0]
					if player == A:
						curr_round.A_cards = parse_hand(line)
					else:
						curr_round.B_cards = parse_hand(line)
					outfile.write(line)

				if "illegal" in line:
					print(line)
					outfile.write(line)

				# summary of settled board at new street
				if "Board 1, (" in line or "Board 2, (" in line or "Board 3, (" in line:
					outfile.write(line)

				# new street/betting round
				if "River" in line or "Flop" in line or "Turn" in line:
					outfile.write(line)
					street_str_to_int = {"Flop": 0, "Turn": 4, "River": 5}
					if "Flop" in line:
						curr_round.street = 3
					elif "Turn" in line:
						curr_round.street = 4
					elif "River" in line:
						curr_round.street = 5
					community_cards = parse_hand(line)
					board_num = int(line_arr[-1])
					curr_round.boards[board_num].community_cards = community_cards
					curr_round.boards[board_num].community_cards_per_street[curr_round.street] = community_cards
					for board_num in range(1, 4):
						curr_round.boards[board_num].pips = {A: 0, B: 0}

				if "assigns" in line:
					player = line_arr[0]
					hand = parse_hand(line)
					board_num = int(line_arr[-1])
					curr_board = curr_round.boards[board_num]
					ev = get_ev(sorted(hand, key=lambda x: values[x[0]], reverse=True))

					if player == A:
						curr_board.A_holes = hand
						curr_board.A_hole_ev = ev
						strength = calculate_strength(curr_board.A_holes, curr_round.A_cards, [], _MONTE_CARLO_ITERS)
					else:
						curr_board.B_holes = hand
						curr_board.B_hole_ev = ev
						strength = calculate_strength(curr_board.B_holes, curr_round.B_cards, [], _MONTE_CARLO_ITERS)

					outfile.write(line[:-1] + ", with EV " + str(ev) + " and strength " + num_to_str(strength) + "\n")

				if "posts" in line:
					outfile.write(line)
					player = line_arr[0]
					blind_amt = int(line_arr[5])
					for board_num in range(1, 4):
						curr_round.boards[board_num].pips[player] += blind_amt
						curr_round.boards[board_num].pot += blind_amt
						curr_round.bankrolls[player] -= blind_amt

				# betting action
				if "calls" in line or "raises" in line or "bets" in line or "folds" in line or "checks" in line:
					outfile.write(line)
					player = line_arr[0]
					other_player = B if player == A else A
					board_num = int(line_arr[-1])
					curr_board = curr_round.boards[board_num]

					a_strength = calculate_strength(curr_board.A_holes, curr_round.A_cards,
													curr_board.community_cards, _MONTE_CARLO_ITERS)
					b_strength = calculate_strength(curr_board.B_holes, curr_round.B_cards,
													curr_board.community_cards, _MONTE_CARLO_ITERS)
					if a_strength > b_strength:
						forecasted_winner = A
					elif b_strength > a_strength:
						forecasted_winner = B
					else:
						forecasted_winner = "TIE"
					# winner, a_hand_desc, b_hand_desc = eval_hands(curr_board.A_holes, curr_board.B_holes,
					# 		   curr_board.community_cards)

					continue_cost = curr_board.pips[other_player] - curr_board.pips[player]
					potodds = continue_cost / (curr_board.pot + continue_cost)

					if "checks" in line:
						# action = Action("CHECK", a_strength, potodds, curr_round.bankrolls[player], curr_board.raises[other_player], curr_round.street, board_num)
						# if player == A:
						# 	actions.append(action)

						pass

					if "calls" in line:
						action = Action("CALL", a_strength, potodds, curr_round.bankrolls[player], curr_board.raises[other_player], curr_round.street, board_num)
						if player == A:
							actions.append(action)

						continue_cost = curr_board.pips[other_player] - curr_board.pips[player]

						curr_board.pips[player] += continue_cost
						curr_board.pot += continue_cost
						curr_round.bankrolls[player] -= continue_cost

						action = {"Type": "Call", "Player": player, "Cost": continue_cost, "Forecasted Winner": forecasted_winner}

						curr_board.actions_per_street[curr_round.street].append(action)

						# not quite an aggression
						# if forecasted_winner != player:
						# 	bad_aggressions[player] += 1

					if "raises" in line:
						action = Action("RAISE", a_strength, potodds, curr_round.bankrolls[player], curr_board.raises[other_player], curr_round.street, board_num)
						if player == A:
							actions.append(action)

						raise_to = int(line_arr[3])
						raise_cost = raise_to - curr_board.pips[player]

						curr_board.pips[player] += raise_cost
						curr_board.pot += raise_cost
						curr_round.bankrolls[player] -= raise_cost

						action = {"Type": "Raise", "Player": player, "Cost": raise_cost, "To": raise_to,
								  "Forecasted Winner": forecasted_winner}

						curr_board.actions_per_street[curr_round.street].append(action)
						curr_board.raises_per_street[player][curr_round.street] += 1
						curr_board.raises[player] += 1

						total_aggressions[curr_round.street][player] += 1


						if forecasted_winner != player:
							bad_aggressions[curr_round.street][player] += 1

					if "bets" in line:
						# action = Action("BET", a_strength, potodds, curr_round.bankrolls[player], curr_board.raises[other_player], curr_round.street, board_num)
						# if player == A:
						# 	actions.append(action)

						bet_amount = int(line_arr[2])

						curr_board.pips[player] += bet_amount
						curr_board.pot += bet_amount
						curr_round.bankrolls[player] -= bet_amount

						action = {"Type": "Bet", "Player": player, "Cost": bet_amount,
								  "Forecasted Winner": forecasted_winner}

						curr_board.actions_per_street[curr_round.street].append(action)
						curr_board.raises_per_street[player][curr_round.street] += 1
						curr_board.raises[player] += 1

						total_aggressions[curr_round.street][player] += 1

						if forecasted_winner != player:
							bad_aggressions[curr_round.street][player] += 1

					if "folds" in line:
						action = Action("FOLD", a_strength, potodds, curr_round.bankrolls[player], curr_board.raises[other_player], curr_round.street, board_num)
						if player == A:
							actions.append(action)

						a_had_better = (A == forecasted_winner)
						tie = (forecasted_winner == "TIE")

						curr_board.outcome = {"Method": "Fold", "Winner": other_player, "A hand type": "not evaluated",
													   "B hand type": "not evaluated", "Winnings": curr_board.pot - curr_board.pips[other_player], "A_better_hand": a_had_better, "Tied Hands": tie}

						if other_player == A:
							fold_winnings_A += curr_board.pot
							print("A wins Board", board_num, "net winnings", curr_board.pot - curr_board.pips[other_player], file=outfile)
						else:
							fold_winnings_B += curr_board.pot
							print("B wins Board", board_num, "net winnings", curr_board.pot - curr_board.pips[other_player], file=outfile)

						action = {"Type": "Fold", "Player": player,
								  "Forecasted Winner": forecasted_winner}

						curr_board.actions_per_street[curr_round.street].append(action)

				if "shows" in line:
					outfile.write(line)
					board_num = int(line_arr[-1])
					curr_board = curr_round.boards[board_num]

					forecasted_winner, a_hand_desc, b_hand_desc = eval_hands(curr_board.A_holes, curr_board.B_holes, curr_board.community_cards)

					res = []
					if forecasted_winner == "TIE":
						curr_round.boards[board_num].outcome = {"Method": "Showdown", "Winner": forecasted_winner, A + " hand type": a_hand_desc,
												B + " hand type": b_hand_desc, "Winnings": curr_board.pot // 2 - curr_board.pips[other_player]} # not quite
						curr_round.bankrolls[A] += curr_board.pot // 2
						curr_round.bankrolls[B] += curr_board.pot // 2
						outfile.write(loglines[i+1])
						print("Tie on Board", board_num, "winnings...", file=outfile)
					else:
						curr_round.boards[board_num].outcome = {"Method": "Showdown", "Winner": forecasted_winner, A + " hand type": a_hand_desc,
												B + " hand type": b_hand_desc, "Winnings": curr_board.pot - curr_board.pips[other_player]}
						curr_round.bankrolls[forecasted_winner] += curr_board.pot
						outfile.write(loglines[i+1])
						print(forecasted_winner, "wins Board", board_num, "net winnings", curr_board.pot - curr_board.pips[other_player], file=outfile)

					# handled this showdown, skip next line - check that this doesn't break anything in the future, eg printing line by line
					i += 1

				i += 1

			if "awarded" in loglines[i]:
				outfile.write(loglines[i])
				curr_round.bankrolls[A] += fold_winnings_A
				curr_round.bankrolls[B] += fold_winnings_B
				curr_round.deltas[A] = curr_round.bankrolls[A] - 200
				curr_round.deltas[B] = curr_round.bankrolls[B] - 200
				cumulative_delta_a += curr_round.deltas[A]
				cumulative_delta_b += curr_round.deltas[B]
				cumulative_delta_a_series.append(cumulative_delta_a)
				cumulative_delta_b_series.append(cumulative_delta_b)
				i += 1
				outfile.write(loglines[i])

			rounds_data.append(curr_round)

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

	for curr_round in rounds_data:
		for i in range(1,4):
			outcome = curr_round.boards[i].outcome
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
					street_folds_B[len(curr_round.boards[i].community_cards)] += 1
				else:
					total_folds_A += 1
					if outcome["A_better_hand"] or outcome["Tied Hands"]:
						bad_folds_A += 1
					street_folds_A[len(curr_round.boards[i].community_cards)] += 1


			# Showdown stats
			if outcome["Method"] == "Showdown":
				showdown_count[i] += 1
				if a_won:
					showdown_wins_A[i] += 1

			# EV stats
			evs_A[i].append(curr_round.boards[i].A_hole_ev)
			evs_B[i].append(curr_round.boards[i].B_hole_ev)

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

	# plt.plot(cumulative_delta_a_series)
	# plt.ylabel('Player A cumulative delta')
	# plt.show()
	#
	# plt.plot(cumulative_delta_b_series)
	# plt.ylabel('Player B cumulative delta')
	# plt.show()

actions_df = pd.DataFrame.from_records([vars(action) for action in actions])

actions_df.to_csv('loosey_goosey_actions_only_call_raise_and_fold.csv', index=False)

