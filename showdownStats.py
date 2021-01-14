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

i = 0
while i < len(loglines):
	line = loglines[i]
	if line.startswith("Round #"):
		num = [int(s[1:len(s)-1]) for s in line.split() if s.startswith('#')]
		round = Round(num[0])
		while "awarded" not in line:
			i += 1
			line = loglines[i]

			if "River" in line or "Flop" in line or "Turn" in line:
				street = line[line.index("["):line.index("]")+1]
				board = int(line[line.index("board") + 6]) - 1
				round.streets[board] = street

			if "folds" in line:
				board = int(line[line.index("board") + 6]) - 1
				round.outcome[board] = line[:line.index("folds")] + "folds"

			if "shows" in line:
				hand = line[line.index("["):line.index("]") + 1]
				board = int(line[line.index("board") + 6]) - 1
				if line.split()[0] == me:
					round.my_holes[board] = hand
				else:
					round.opp_holes[board] = hand

		rounds_data.append(round)
		
	i += 1


