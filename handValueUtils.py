'''
Find distribution of which board opponent plays their strongest hand on
'''

import re
import eval7
import itertools

# # 5.2 Hand Strength
# # https://webdocs.cs.ualberta.ca/~jonathan/PREVIOUS/Grad/papp/node38.html

    def calculate_strength(self, hole_cards, my_cards, community_cards, iters, weight=None):
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
        # card objects, used to evaliate hands
        community_cards = [eval7.Card(card) for card in community_cards]

        for card in hole_cards:  # remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        # get more likely opp hands based on weight
        # avoid repeats
        opp_hands_to_try = set()
        score = 0
        while len(opp_hands_to_try) < iters:
            for hand in list(itertools.combinations(list(deck), 2)):
                ev = self.get_ev(sorted([str(hand[0]), str(hand[1])],
                                        key=lambda x: self.values[x[0]], reverse=True))
                # TODO: better strength weighting
                ev = min(1, ev + 0.2)
                if random.random() < ev and hand not in opp_hands_to_try:
                    opp_hands_to_try.add(hand)
            break

        for opp_hole in opp_hands_to_try:
            deck.shuffle()  # make sure our samples are random

            # the number of cards we need to draw
            _COMM = 5 - len(community_cards)
            _OPP = 2

            draw = deck.peek(_COMM)

            hidden_community = draw[_OPP:]

            our_hand = hole_cards + community_cards + \
                hidden_community  # the two showdown hands
            opp_hand = list(opp_hole) + community_cards + hidden_community

            # the ranks of our hands (only useful for comparisons)
            our_hand_value = eval7.evaluate(our_hand)
            opp_hand_value = eval7.evaluate(opp_hand)

            if our_hand_value > opp_hand_value:  # we win!
                score += 2  # the pseudocode for HandStrength() uses +1 for both wins and ties?

            elif our_hand_value == opp_hand_value:  # we tie.
                score += 1

            else:  # we lost....
                score += 0

        # this is our win probability!
        hand_strength = score / (2 * len(opp_hands_to_try))

        # print("sampling duration", sampling_duration)

        return hand_strength

deck = eval7.Deck()  # eval7 object!
draw = deck.deal(2)
# print(draw)
# print(len(deck))
# print(list(deck))
hand = list(itertools.combinations(list(deck), 2))[0]
print(str(hand[0]))