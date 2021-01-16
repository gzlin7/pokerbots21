'''
Parse poker gamelog into custom data structure
'''

import re
import eval7

# assumes playing "A" vs "B"
GAME_LOG_FILE = 'game_log.txt'
A = "A"
B = "B"

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
		round_pkr = Round(round_num)
		while "awarded" not in line:
			i += 1
			line = loglines[i]
			line_arr = line.split()

			# new street
			if "River" in line or "Flop" in line or "Turn" in line:
				community_cards = parse_hand(line)
				board = int(line_arr[-1])
				round_pkr.boards[board].community_cards = community_cards
				for board in range(1, 4):
					round_pkr.boards[board].pips = {A: 0, B: 0}


			if "posts" in line:
				player = line_arr[0]
				blind_amt = int(line_arr[5])
				for board in range(1, 4):
					round_pkr.boards[board].pips[player] += blind_amt
					round_pkr.boards[board].pot += blind_amt
					round_pkr.bankrolls[player] -= blind_amt

			if "calls" in line:
				player = line_arr[0]
				other_player = B if player == A else A
				board = int(line_arr[-1])
				continue_cost = round_pkr.boards[board].pips[other_player] - round_pkr.boards[board].pips[player]

				round_pkr.boards[board].pips[player] += continue_cost
				round_pkr.boards[board].pot += continue_cost
				round_pkr.bankrolls[player] -= continue_cost

			if "raises" in line:
				player = line_arr[0]
				board = int(line_arr[-1])
				raise_to = int(line_arr[3])
				raise_cost = raise_to - round_pkr.boards[board].pips[player]

				round_pkr.boards[board].pips[player] += raise_cost
				round_pkr.boards[board].pot += raise_cost
				round_pkr.bankrolls[player] -= raise_cost

			if "bets" in line:
				player = line_arr[0]
				board = int(line_arr[-1])
				bet_amount = int(line_arr[2])

				round_pkr.boards[board].pips[player] += bet_amount
				round_pkr.boards[board].pot += bet_amount
				round_pkr.bankrolls[player] -= bet_amount

			if "folds" in line:
				player = line_arr[0]
				other_player = B if player == A else A
				board = int(line_arr[-1])
				winner, a_hand_desc, b_hand_desc = eval_hands(round_pkr.boards[board].A_holes, round_pkr.boards[board].B_holes,
						   round_pkr.boards[board].community_cards)
				a_had_better = (A == winner)

				round_pkr.boards[board].outcome = {"Method": "Fold", "Winner": other_player, "A hand type": "not evaluated",
											   "B hand type": "not evaluated", "Winnings": round_pkr.boards[board].pot, "A_better_hand": a_had_better}

				if other_player == A:
					fold_winnings_A += round_pkr.boards[board].pot
				else:
					fold_winnings_B += round_pkr.boards[board].pot

			if "assigns" in line:
				player = line_arr[0]
				hand = parse_hand(line)
				board = int(line_arr[-1])
				if player == A:
					round_pkr.boards[board].A_holes = hand
				else:
					round_pkr.boards[board].B_holes = hand


			if "shows" in line:
				board = int(line_arr[-1])
				winner, a_hand_desc, b_hand_desc = eval_hands(round_pkr.boards[board].A_holes, round_pkr.boards[board].B_holes, round_pkr.boards[board].community_cards)

				res = []
				if winner == "TIE":
					round_pkr.boards[board].outcome = {"Method": "Showdown", "Winner": winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round_pkr.boards[board].pot // 2} # not quite
					round_pkr.bankrolls[A] += round_pkr.boards[board].pot // 2
					round_pkr.bankrolls[B] += round_pkr.boards[board].pot // 2
				else:
					round_pkr.boards[board].outcome = {"Method": "Showdown", "Winner": winner, A + " hand type": a_hand_desc,
											B + " hand type": b_hand_desc, "Winnings": round_pkr.boards[board].pot}
					round_pkr.bankrolls[winner] += round_pkr.boards[board].pot

				# handled this showdown, skip next line - check that this doesn't break anything in the future, eg printing line by line
				i += 1

		if "awarded" in line:
			round_pkr.bankrolls[A] += fold_winnings_A
			round_pkr.bankrolls[B] += fold_winnings_B
			round_pkr.deltas[A] = round_pkr.bankrolls[A] - 200
			round_pkr.deltas[B] = round_pkr.bankrolls[B] - 200

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
				if not outcome["A_better_hand"]:
					bad_folds_B += 1
				street_folds_B[len(round_pkr.boards[i].community_cards)] += 1
			else:
				total_folds_A += 1
				if outcome["A_better_hand"]:
					bad_folds_A += 1
				street_folds_A[len(round_pkr.boards[i].community_cards)] += 1


		# Showdown stats
		if outcome["Method"] == "Showdown":
			showdown_count[i] += 1
			if a_won:
				showdown_wins_A[i] += 1

for i in range(1,4):
	print("===== "+"BOARD "+ str(i) + " =====")
	print("Win (A): " + str(win_count[i] / num_rounds))
	print("Showdown Win: " + str(round(showdown_wins_A[i] / showdown_count[i],2)))
	print()
	print("Avg win amt (A): " + str(win_total_A[i] / num_rounds))
	print("Avg win amt (B): " + str(win_total_B[i] / num_rounds))
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

# for i in range(0, 10):
# 	rounds_data_obj = rounds_data[i]
# 	print(rounds_data_obj.deltas[A], rounds_data_obj.deltas[B])

