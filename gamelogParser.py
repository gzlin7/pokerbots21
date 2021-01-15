'''
Parse poker gamelog into custom data structure
'''

import re
import eval7

# assumes playing "A" vs "B"
GAME_LOG_FILE = 'gamelog.txt'
A = "Hero"
B = "Villain"

f = open(GAME_LOG_FILE)
loglines = f.readlines()

assignments = []

class Board:
	def __init__(self, num, pre_inflation):
		self.num = num
		self.community_cards = []
		self.A_holes = []
		self.B_holes = []
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

	def __str__(self):
		return str(self.__class__) + ": " + str(self.__dict__)

rounds_data = []

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


i = 0

while i < len(loglines):
	line = loglines[i]
	if line.startswith("Round #"):
		fold_winnings_A = 0
		fold_winnings_B = 0
		round_num = line.split()[1]
		round_num = int(round_num[1:len(round_num)-1])
		round = Round(round_num)
		while "awarded" not in line:
			i += 1
			line = loglines[i]
			line_arr = line.split()

			# new street
			if "River" in line or "Flop" in line or "Turn" in line:
				community_cards = parse_hand(line)
				board = int(line_arr[-1])
				round.boards[board].community_cards = community_cards
				for board in range(1, 4):
					round.boards[board].pips = {A: 0, B: 0}


			if "posts" in line:
				player = line_arr[0]
				blind_amt = int(line_arr[5])
				for board in range(1, 4):
					round.boards[board].pips[player] += blind_amt
					round.boards[board].pot += blind_amt
					round.bankrolls[player] -= blind_amt

			if "calls" in line:
				player = line_arr[0]
				other_player = B if player == A else A
				board = int(line_arr[-1])
				continue_cost = round.boards[board].pips[other_player] - round.boards[board].pips[player]

				round.boards[board].pips[player] += continue_cost
				round.boards[board].pot += continue_cost
				round.bankrolls[player] -= continue_cost

			if "raises" in line:
				player = line_arr[0]
				board = int(line_arr[-1])
				raise_to = int(line_arr[3])
				raise_cost = raise_to - round.boards[board].pips[player]

				round.boards[board].pips[player] += raise_cost
				round.boards[board].pot += raise_cost
				round.bankrolls[player] -= raise_cost

			if "bets" in line:
				player = line_arr[0]
				board = int(line_arr[-1])
				bet_amount = int(line_arr[2])

				round.boards[board].pips[player] += bet_amount
				round.boards[board].pot += bet_amount
				round.bankrolls[player] -= bet_amount

			if "folds" in line:
				player = line_arr[0]
				other_player = B if player == A else A
				board = int(line_arr[-1])

				round.boards[board].outcome = {"Method": "Fold", "Winner": other_player, "A hand type": "not evaluated",
											   "B hand type": "not evaluated", "Winnings": round.boards[board].pot}

				if other_player == A:
					fold_winnings_A += round.boards[board].pot
				else:
					fold_winnings_B += round.boards[board].pot

			if "assigns" in line:
				player = line_arr[0]
				hand = parse_hand(line)
				board = int(line_arr[-1])
				if player == A:
					round.boards[board].A_holes = hand
				else:
					round.boards[board].B_holes = hand


			if "shows" in line:
				board = int(line_arr[-1])
				winner, a_hand_desc, b_hand_desc = eval_hands(round.boards[board].A_holes, round.boards[board].B_holes, round.boards[board].community_cards)

				res = []
				if winner == "TIE":
					round.boards[board].outcome = {"Method": "Showdown", "Winner": winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round.boards[board].pot // 2} # not quite
					round.bankrolls[A] += round.boards[board].pot // 2
					round.bankrolls[B] += round.boards[board].pot // 2
				else:
					round.boards[board].outcome = {"Method": "Showdown", "Winner": winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round.boards[board].pot}
					round.bankrolls[winner] += round.boards[board].pot

				# handled this showdown, skip next line - check that this doesn't break anything in the future, eg printing line by line
				i += 1

		if "awarded" in line:
			round.bankrolls[A] += fold_winnings_A
			round.bankrolls[B] += fold_winnings_B
			round.deltas[A] = round.bankrolls[A] - 200
			round.deltas[B] = round.bankrolls[B] - 200

		rounds_data.append(round)

	i += 1

# for i in range(0, 10):
# 	rounds_data_obj = rounds_data[i]
# 	print(rounds_data_obj.deltas[A], rounds_data_obj.deltas[B])

