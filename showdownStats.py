'''
Find distribution of which board opponent plays their strongest hand on
'''

import re

GAME_LOG_FILE = 'gamelog.txt'

f = open(GAME_LOG_FILE)
loglines = f.readlines()

assignments = []

class Round:
	def __init__(self, num):
		self.num = num
		self.streets = [[],[],[]]
		self.my_holes = [[], [], []]
		self.opp_holes = [[], [], []]
		self.outcome = [False,False,False]

rounds_data = []

me = "Hero"
opp = "Villain"

def parse_board_idx(line):
	return int(line[line.index("board") + 6]) - 1

def parse_hand(line):
	return line[line.index("["):line.index("]") + 1]

i = 0
while i < len(loglines):
	line = loglines[i]
	if line.startswith("Round #"):
		num = line.split()[1]
		num = int(num[1:len(num)-1])
		round = Round(num)
		while "awarded" not in line:
			i += 1
			line = loglines[i]

			if "River" in line or "Flop" in line or "Turn" in line:
				street = parse_hand(line)
				board = parse_board_idx(line)
				round.streets[board] = street

			if "folds" in line:
				board = parse_board_idx(line)
				round.outcome[board] = line[:line.index("folds")] + "folds"

			if "assigns" in line:
				hand = parse_hand(line)
				board = parse_board_idx(line)
				if line.split()[0] == me:
					round.my_holes[board] = hand
				else:
					round.opp_holes[board] = hand

			# if "shows" in line:
			# 	# eval7 to determine winner
			# 	# add to outcomes

		rounds_data.append(round)

	i += 1

