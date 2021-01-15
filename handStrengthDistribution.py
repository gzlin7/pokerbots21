'''
Find distribution of which board opponent plays their strongest hand on
'''

import re
import eval7

GAME_LOG_FILE = 'gamelog.txt'


def calculate_strength(hole_cards, community_cards, iters):
	'''
    A Monte Carlo method meant to estimate the win probability of a pair of
    hole cards. Simlulates 'iters' games and determines the win rates of our cards

    Arguments:
    hole: a list of our two hole cards
    iters: a integer that determines how many Monte Carlo samples to take
    '''

	deck = eval7.Deck()  # eval7 object!
	hole_cards = [eval7.Card(card) for card in hole_cards]  # card objects, used to evaliate hands
	community_cards = [eval7.Card(card) for card in community_cards]  # card objects, used to evaliate hands

	for card in hole_cards:  # remove cards that we know about! they shouldn't come up in simulations
		deck.cards.remove(card)

	for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
		deck.cards.remove(card)

	score = 0

	for _ in range(iters):  # take 'iters' samples
		deck.shuffle()  # make sure our samples are random

		_COMM = 5 - len(community_cards)  # the number of cards we need to draw
		_OPP = 2

		draw = deck.peek(_COMM + _OPP)

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

f = open(GAME_LOG_FILE)
loglines = f.readlines()

assignments = []

for line in loglines:
	if line.startswith("B assigns"):
		result = re.search(r"\[([A-Za-z0-9_ ]+)\]", line)
		assignment = result.group(1).split()
		assignments.append(assignment)

counts = {1: 0, 2: 0, 3:0}

i = 0
while i < len(assignments):
	hole_1 = assignments[i]
	hole_2 = assignments[i+1]
	hole_3 = assignments[i+2]

	strength_1 = calculate_strength(hole_1, [], 100)
	strength_2 = calculate_strength(hole_2, [], 100)
	strength_3 = calculate_strength(hole_3, [], 100)

	strengths = [strength_1, strength_2, strength_3]

	if max(strengths) == strength_1:
		counts[1] += 1
	elif max(strengths) == strength_2:
		counts[2] += 1
	elif max(strengths) == strength_3:
		counts[3] += 1
	i += 3

total = counts[1] + counts[2] + counts[3]

for count in counts:
	counts[count] = counts[count] / total

print(counts)