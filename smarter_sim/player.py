'''
This bot picks initial hands prioritizing pairs and then rank, then assigning the strongest hand to Board 3.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction, AssignAction
from skeleton.states import GameState, TerminalState, RoundState, BoardState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND, NUM_BOARDS
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import eval7
import random
import time
import itertools
import pandas as pd

import sys
import os
from numpy.random import choice


class Game:
    def __init__(self):
        pass


class Round:
    def __init__(self):
        self.current_street = 0
        self.boards = {1: Board(), 2: Board(), 3: Board()}
        self.eval_count = 0
        self.calculate_strength_called = 0
        self.eval_hand_memo = {}


class Board:
    def __init__(self):
        self.strength_per_street = {0: None, 3: None, 4: None, 5: None}
        self.raises_per_street = {0: 0, 3: 0, 4: 0, 5: 0}
        self.raises_weighted = 0

class Player(Bot):
    '''
    A pokerbot.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        self.board_allocations = [
            [], [], []]  # keep track of our allocations at round start
        # better representation of our hole strengths (win probability!)
        self.hole_strengths = [0, 0, 0]
        self.sampling_duration_total = 0
        self.round = Round()

        self._MONTE_CARLO_ITERS = 100
        # whether to randomize ordering of holes to avoid deterministic exploitation
        self.RANDOMIZATION_ON = False

        # self.enablePrint()
        self.blockPrint()

        # random.seed(10)

        # make sure this df isn't too big!! Loading data all at once might be slow if you did more computations!
        # the values we computed offline, this df is slow to search through though
        calculated_df = pd.read_csv('hole_evs.csv')
        holes = calculated_df.Holes  # the columns of our spreadsheet
        strengths = calculated_df.EVs
        # convert to a dictionary, O(1) lookup time!
        self.starting_strengths = dict(zip(holes, strengths))

        # https://www.daniweb.com/programming/software-development/threads/303283/sorting-cards, is this in eval7?
        self.values = dict(zip('23456789TJQKA', range(2, 15)))

        # build dict of EVs to sets of eval7 hand
        self.ev_to_eval7hands = dict()
        for hand in list(itertools.combinations(list(eval7.Deck()), 2)):
            ev = self.get_ev(sorted([str(hand[0]), str(hand[1])],
                                    key=lambda x: self.values[x[0]], reverse=True))
            self.ev_to_eval7hands.setdefault(ev, set())
            self.ev_to_eval7hands[ev].add(hand)

        self.evs_descending = sorted(
            self.ev_to_eval7hands.keys(), reverse=True)

        self.street_to_raise_weight = {0: 1, 3: 4, 4: 5, 5: 7}

        self.ev_probs = {
         1: {-0.15: 0.06902866744185226, -0.14: 0.10808813078938893, -0.13: 0.14157522992368363,
             -0.12: 0.154410540371909, -0.11: 0.14030899454463125, -0.1: 0.10790588302216017,
             -0.09: 0.07334753945380453, -0.08: 0.047544294676774075, -0.07: 0.031738806017877715,
             -0.06: 0.022396822598138626, -0.05: 0.016617874731018365, -0.04: 0.013084875241543711,
             -0.03: 0.010808699057643562, -0.02: 0.0088676776971456, 0.0: 0.005673890046324188,
             0.01: 0.0050968446018726165, 0.02: 0.00500762936028664, 0.03: 0.004853261257342864,
             0.04: 0.0043442178802638965, 0.05: 0.00365615188224246, 0.07: 0.0028397307337060394,
             0.08: 0.0025152155191976292, 0.09: 0.0019468386525987537, 0.1: 0.001256962046762336,
             0.15: 0.003201459317069615, 0.16: 0.003620701665306903, 0.17: 0.0033505984355376895,
             0.19: 0.0020333673491544565, 0.2: 0.0016675015430530223, 0.23: 0.001543086457390307,
             0.25: 0.000806637316277485, 0.29: 1.0155174695139377e-05, 0.31: 7.837957180866324e-07,
             0.32: 3.4008724067673026e-06, 0.38: 0.00045046973885700455, 0.39: 0.0003936804563351882,
             0.44: 3.380329997924799e-06, 0.51: 3.145815419212247e-14, 0.58: 0.0, 0.59: 0.0, 0.78: 0.0, 0.86: 0.0,
             1.22: 0.0, 1.67: 0.0, 2.32: 0.0},
         2: {-0.15: 0.03977510174594329, -0.14: 0.0432027188605401, -0.13: 0.046150238026392044,
             -0.12: 0.04850663677713087, -0.11: 0.05019091220222614, -0.1: 0.05115792362522236,
             -0.09: 0.05140083577789229, -0.08: 0.05094995375887196, -0.07: 0.04986822518306932,
             -0.06: 0.04824411281998, -0.05: 0.046182842529857715, -0.04: 0.04379716258843967,
             -0.03: 0.041198701386193116, -0.02: 0.03849080422054624, 0.0: 0.03309021593777404,
             0.01: 0.030527877958800777, 0.02: 0.028117048744068507, 0.03: 0.025884490339843084,
             0.04: 0.023845773050939975, 0.05: 0.022007969733170967, 0.07: 0.018933957807113672,
             0.08: 0.017686679829694168, 0.09: 0.0166194980194001, 0.1: 0.01571857059931706, 0.15: 0.013008220839233043,
             0.16: 0.012657105379905565, 0.17: 0.012314125135830817, 0.19: 0.011583950139992723,
             0.2: 0.011175402388037343, 0.23: 0.009761523321012116, 0.25: 0.008734999692335349,
             0.29: 0.006867186726529431, 0.31: 0.006139611634174658, 0.32: 0.005830024146620382,
             0.38: 0.004346924513262271, 0.39: 0.004104969725847695, 0.44: 0.0029089836907208234,
             0.51: 0.0022122756533047264, 0.58: 0.0022019700646927747, 0.59: 0.0021273103026621483,
             0.78: 0.0005616258826197185, 0.86: 0.0005271269234147686, 1.22: 0.0012148608440331488,
             1.67: 0.00017355147334311536, 2.32: 0.0},
         3: {-0.15: 0.01829841137490927, -0.14: 0.019023127672754166, -0.13: 0.019735873958998375,
             -0.12: 0.020433856236369737, -0.11: 0.021114362418629767, -0.1: 0.02177478794773058,
             -0.09: 0.022412660073244956, -0.08: 0.023025660418810826, -0.07: 0.023611645491380437,
             -0.06: 0.024168664827312513, -0.05: 0.024694976513885233, -0.04: 0.025189059874565205,
             -0.03: 0.02564962516014091, -0.02: 0.026075620144319016, 0.0: 0.02682089553214878,
             0.01: 0.027139274653129906, 0.02: 0.02742127253322372, 0.03: 0.027667015292703323,
             0.04: 0.02787684263991833, 0.05: 0.028051294652509325, 0.07: 0.02829714193815415,
             0.08: 0.028370474369507237, 0.09: 0.028412268383008782, 0.1: 0.028423809553591094,
             0.15: 0.028077970036246888, 0.16: 0.027938704608681315, 0.17: 0.027779646561318583,
             0.19: 0.02740806325934776, 0.2: 0.027198368447859427, 0.23: 0.026489291773832725,
             0.25: 0.02596140525103467, 0.29: 0.02480716559976021, 0.31: 0.024192364319556587,
             0.32: 0.023877508415172402, 0.38: 0.021908659178380394, 0.39: 0.02157015782650561,
             0.44: 0.01985039343540038, 0.51: 0.017430858423301367, 0.58: 0.015144472258794775,
             0.59: 0.014839422944457545, 0.78: 0.010455692794215246, 0.86: 0.009138822198670819,
             1.22: 0.005064540061224135, 1.67: 0.003564653335789283, 2.32: 0.0036132176095042975}}

        print()

    # Disable

    def blockPrint(self):
        sys.stdout = open(os.devnull, 'w')

    # Restore
    def enablePrint(self):
        sys.stdout = sys.__stdout__

    # EVs https://www.tightpoker.com/poker_hands.html
    def hole_to_key(self, hole):
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

    def get_ev(self, hole):
        hole_key = self.hole_to_key(hole)
        return self.starting_strengths[hole_key]

    def allocate_cards(self, my_cards):
        '''
        Method that allocates our cards at the beginning of a round. Method
        modifies self.board_allocations. The method attempts to make pairs
        by allocating hole cards that share a rank if possible. The exact
        stack these cards are allocated to is not defined.

        Arguments:
        my_cards: a list of the 6 cards given to us at round start
        '''

        print("Allocating cards")
        print()

        ranks = {}

        for card in my_cards:
            card_rank = card[0]  # 2 - 9, T, J, Q, K, A
            card_suit = card[1]  # d, h, s, c

            if card_rank in ranks:  # if we've seen this rank before, add the card to our list
                ranks[card_rank].append(card)

            else:  # make a new list if we've never seen this one before
                ranks[card_rank] = [card]

        pairs = []  # keep track of all of the pairs we identified
        singles = []  # all other cards

        for rank in ranks:
            cards = ranks[rank]

            if len(cards) == 1:  # single card, can't be in a pair
                singles.append(cards[0])

            # a single pair or two pairs can be made here, add them all
            elif len(cards) == 2 or len(cards) == 4:
                pairs += cards

            else:  # len(cards) == 3  A single pair plus an extra can be made here
                pairs.append(cards[0])
                pairs.append(cards[1])
                singles.append(cards[2])

        if len(pairs) > 0:  # we found a pair! update our state to say that this is a strong round
            self.strong_hole = True

        # https://www.daniweb.com/programming/software-development/threads/303283/sorting-cards, is this in eval7?
        values = dict(zip('23456789TJQKA', range(2, 15)))
        # high ranks better
        pairs.sort(key=lambda x: values[x[0]])
        singles.sort(key=lambda x: values[x[0]])

        # put best cards on best board (best cards last)
        allocation = singles + pairs

        # subsequent pairs of cards should be pocket pairs if we found any
        for i in range(NUM_BOARDS):
            cards = [allocation[2*i], allocation[2*i + 1]]
            self.board_allocations[i] = cards  # record our allocations

        print("Calculating strength")
        print("Calculating strength")
        print("Calculating strength")

        board_strengths = {}

        for i in range(1, 4):
            self.round.boards[i].strength_per_street[0] = self.calculate_strength(
                self.board_allocations[i-1], my_cards, [], self._MONTE_CARLO_ITERS, board = i)
            board_strengths[frozenset(
                self.board_allocations[i-1])] = self.round.boards[i].strength_per_street[0]

        self.board_allocations.sort(
            key=lambda x: board_strengths[frozenset(x)])

        if self.RANDOMIZATION_ON:
            if random.random() < 0.15:  # swap strongest with second, makes our strategy non-deterministic!
                temp = self.board_allocations[2]
                self.board_allocations[2] = self.board_allocations[1]
                self.board_allocations[1] = temp

            if random.random() < 0.15:  # swap second with last, makes us even more random
                temp = self.board_allocations[1]
                self.board_allocations[1] = self.board_allocations[0]
                self.board_allocations[0] = temp

# # 5.2 Hand Strength
# # https://webdocs.cs.ualberta.ca/~jonathan/PREVIOUS/Grad/papp/node38.html

    def calculate_strength(self, hole_cards, my_cards, community_cards, iters, weight=None, board = 3):
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

        for card in my_cards:  # remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        for card in community_cards:  # remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        # get more likely opp hands based on weight
        # avoid repeats
        opp_hands_to_try = set()
        score = 0

        possible_hands = set(itertools.combinations(deck, 2))

        while len(opp_hands_to_try) < iters:

            selected_evs = choice(self.evs_descending, iters,
                          p=[self.ev_probs[board][ev] / sum(self.ev_probs[board].values()) for ev in self.evs_descending])

            for selected_ev in selected_evs:
                selected_hand = random.choice(list(self.ev_to_eval7hands[selected_ev]))
                if selected_hand in possible_hands:
                    ev_prob = self.ev_probs[board][selected_ev]
                    # print("Board is", board)
                    # print("EV is", selected_ev)
                    # print("EV prob is", ev_prob)
                    if selected_hand not in opp_hands_to_try:
                        opp_hands_to_try.add(selected_hand)
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

            if our_key not in self.round.eval_hand_memo:
                # the ranks of our hands (only useful for comparisons)
                our_hand_value = eval7.evaluate(our_hand)
                self.round.eval_hand_memo[our_key] = our_hand_value
                self.round.eval_count += 1
            else:
                our_hand_value = self.round.eval_hand_memo[our_key]

            if opp_key not in self.round.eval_hand_memo:
                opp_hand_value = eval7.evaluate(opp_hand)
                self.round.eval_hand_memo[opp_key] = opp_hand_value
                self.round.eval_count += 1
            else:
                opp_hand_value = self.round.eval_hand_memo[opp_key]

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

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        print("New round!")
        print()
        # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        my_bankroll = game_state.bankroll
        opp_bankroll = game_state.opp_bankroll  # ^but for your opponent
        # the total number of seconds your bot has left to play this game
        game_clock = game_state.game_clock
        round_num = game_state.round_num  # the round number from 1 to NUM_ROUNDS
        # your six cards at the start of the round
        my_cards = round_state.hands[active]
        big_blind = bool(active)  # True if you are the big blind

        self.allocate_cards(my_cards)  # our old allocation strategy

        self.round = Round()

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        print("Round over!")
        print()
        # your bankroll change from this round
        my_delta = terminal_state.deltas[active]
        # your opponent's bankroll change from this round
        opp_delta = terminal_state.deltas[1-active]
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        street = previous_state.street  # 0, 3, 4, or 5 representing when this round ended
        i = 1
        print("My remaining stack is", previous_state.stacks[active])
        print()

        for terminal_board_state in previous_state.board_states:
            print("Board", i)
            previous_board_state = terminal_board_state.previous_state
            my_cards = previous_board_state.hands[active]  # your cards
            # opponent's cards or [] if not revealed
            opp_cards = previous_board_state.hands[1-active]
            community_cards = previous_board_state.deck
            my_cards = [card for card in my_cards if card]
            opp_cards = [card for card in opp_cards if card]
            community_cards = [card for card in community_cards if card]
            print("My cards are", my_cards)
            print("Opp cards are", opp_cards)
            print("Comm cards are", community_cards)

            # someone folded before showdown
            if not opp_cards or not my_cards:
                if terminal_board_state.deltas[active] > terminal_board_state.deltas[1 - active]:
                    print("Opponent folded, so I win on this board",
                          terminal_board_state.deltas[active])
                else:
                    print("I folded, so I gain nothing on this board")
            # showdown winner
            else:
                my_cards = [eval7.Card(card) for card in my_cards if card]
                opp_cards = [eval7.Card(card) for card in opp_cards if card]
                community_cards = [eval7.Card(card)
                                   for card in community_cards if card]

                my_hand = eval7.evaluate(my_cards + community_cards)
                opp_hand = eval7.evaluate(opp_cards + community_cards)

                if my_hand > opp_hand:
                    print("I win on this showdown board",
                          previous_board_state.pot)
                elif opp_hand > my_hand:
                    print(
                        "I lost on this showdown board, so I gain nothing on this showdown board")
                else:
                    print("Tie, so I gain on this showdown board",
                          previous_board_state.pot // 2)
            print()
            i += 1

        print("I win on this round total:", my_delta)
        print()

        # reset our variables at the end of every round!
        self.board_allocations = [[], [], []]
        self.hole_strengths = [0, 0, 0]

        # check how much time we have remaining at the end of a game
        game_clock = game_state.game_clock
        # Monte Carlo takes a lot of time, we use this to adjust!
        round_num = game_state.round_num

        if round_num == NUM_ROUNDS:
            print("Time remaining after all rounds:", game_clock)
            print("Total sampling duration:", self.sampling_duration_total)

    def get_actions(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs a triplet of actions from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your actions.
        '''

        print("*** get_actions called ***")
        print()
        # the actions you are allowed to take
        legal_actions = round_state.legal_actions()
        # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        street = round_state.street
        my_cards = round_state.hands[active]  # your cards across all boards
        board_cards = [board_state.deck if isinstance(
            board_state, BoardState) else board_state.previous_state.deck for board_state in round_state.board_states]  # the board cards
        # the number of chips you have contributed to the pot on each board this round of betting
        my_pips = [board_state.pips[active] if isinstance(
            board_state, BoardState) else 0 for board_state in round_state.board_states]
        # the number of chips your opponent has contributed to the pot on each board this round of betting
        opp_pips = [board_state.pips[1-active] if isinstance(
            board_state, BoardState) else 0 for board_state in round_state.board_states]
        # the number of chips needed to stay in each board's pot
        continue_cost = [opp_pips[i] - my_pips[i] for i in range(NUM_BOARDS)]
        # the number of chips you have remaining
        my_stack = round_state.stacks[active]
        # the number of chips your opponent has remaining
        opp_stack = round_state.stacks[1-active]
        stacks = [my_stack, opp_stack]
        print("Before choosing board actions, my stack is", my_stack)
        print()
        # max raise across 3 boards
        net_upper_raise_bound = round_state.raise_bounds()[1]
        net_cost = 0  # keep track of the net additional amount you are spending across boards this round

        round = self.round
        if street != round.current_street:
            print("New street")
            # do stuff on new betting round? setup?
            round.current_street = street

        my_actions = [None] * NUM_BOARDS
        for i in range(NUM_BOARDS):
            print("~ Currently solving board", i+1, " ~")
            if isinstance(round_state.board_states[i], TerminalState):
                print("This board is Terminal.")
                print("!!!!")
            elif round_state.board_states[i].settled:
                print("This board is settled, can only check.")
                print("!!!!")

            board = round.boards[i+1]

            hole_cards = self.board_allocations[i]

            if AssignAction in legal_actions[i]:
                print("Assigning preferred hole cards")
                my_actions[i] = AssignAction(hole_cards)  # add to our actions

            # make sure the game isn't over at this board
            elif isinstance(round_state.board_states[i], TerminalState):
                print("At a terminal state")
                my_actions[i] = CheckAction()  # check if it is

            # round of active play
            else:  # do we add more resources?

                print("Hole cards on this board are", hole_cards)
                print("Visible community cards are", [
                      card for card in board_cards[i] if card])
                print()
                visible_community_cards = [
                    card for card in board_cards[i] if card]

                if board.strength_per_street[round.current_street]:
                    print("Avoided recalculating")
                    strength = board.strength_per_street[round.current_street]
                else:
                    print("Calculating strength")
                    strength = self.calculate_strength(
                        self.board_allocations[i], my_cards, visible_community_cards, self._MONTE_CARLO_ITERS, board = i+1)
                    board.strength_per_street[round.current_street] = strength

                print("Calculated strength of hole cards and board is", strength)
                print()

                # strength2 = pow(strength, board.raises_weighted / 5)
                # strength2 = strength - (board.raises_weighted / 50)

                print("Round of active play")
                print("Our stack has", my_stack - net_cost)
                # we need to pay this to keep playing
                board_cont_cost = continue_cost[i]
                # amount before we started betting
                board_total = round_state.board_states[i].pot
                # total money in the pot right now
                pot_total = my_pips[i] + opp_pips[i] + board_total
                print("Old pot has", round_state.board_states[i].pot,
                      ", my pips are", my_pips[i], ", opponent pips are", opp_pips[i])
                print("Pot total is", pot_total)
                print("Continue cost is", board_cont_cost)
                min_raise, max_raise = round_state.board_states[i].raise_bounds(
                    active, round_state.stacks)
                print("Min raise is", min_raise, ", max raise is", max_raise)
                # strength = self.hole_strengths[i]
                # print("Current street is", street)

                if street < 3:  # pre-flop
                    # play a little conservatively pre-flop
                    raise_amount = int(
                        my_pips[i] + board_cont_cost + 0.4 * (pot_total + board_cont_cost))
                    print("Desired pre-flop raise amount is", raise_amount)
                else:
                    # raise the stakes deeper into the game
                    raise_amount = int(
                        my_pips[i] + board_cont_cost + 0.75 * (pot_total + board_cont_cost))
                    print("Desired post-flop raise amount is", raise_amount)

                # make sure we have a valid raise
                raise_amount = max([min_raise, raise_amount])
                raise_amount = min([max_raise, raise_amount])

                print(
                    "After bounding raise_amount, desired raise amount is", raise_amount)

                # how much it costs to make that raise
                raise_cost = raise_amount - my_pips[i]

                print("This raise will cost", raise_cost)

                print()

                # raise if we can and if we can afford it
                if RaiseAction in legal_actions[i] and (raise_cost <= my_stack - net_cost):
                    print("Commit action is Raise because we can afford the full desired raise, raising to",
                          raise_amount, ", costing", raise_cost)
                    commit_action = RaiseAction(raise_amount)
                    commit_cost = raise_cost

                # call if we can afford it!:
                elif CallAction in legal_actions[i] and (board_cont_cost <= my_stack - net_cost):
                    print(
                        "Commit action is Call, can't afford full raise, paying", board_cont_cost)
                    commit_action = CallAction()
                    commit_cost = board_cont_cost  # the cost to call is board_cont_cost

                elif CheckAction in legal_actions[i]:  # try to check if we can
                    print("Commit action is Check")
                    commit_action = CheckAction()
                    commit_cost = 0

                else:  # we have to fold
                    print("Commit action is Fold")
                    commit_action = FoldAction()
                    commit_cost = 0

                print()

                print("###########")
                if board_cont_cost > 0:  # our opp raised!!! we must respond
                    print(
                        "Opponent has raised. We must respond. Continue cost is", board_cont_cost)

                    new_raises = 0
                    # fix assumption
                    if board_cont_cost == 1:
                        print("Assuming opponent played big blind, this is meaningless.")
                    elif my_pips[i] == 0:
                        new_raises += 0.5
                        print("Opponent has bet")
                    else:
                        new_raises += 1
                        print("Opponent has raised")

                    new_raises *= self.street_to_raise_weight[round.current_street]
                    board.raises_per_street[round.current_street] += 1
                    board.raises_weighted += new_raises

                    if board_cont_cost > 5:  # <--- parameters to tweak.
                        print("Continue cost > 5 so we are intimidated.")
                        _INTIMIDATION = 0.15
                        # if our opp raises a lot, be cautious!
                        strength = max([0, strength - _INTIMIDATION])
                        print("New strength is", strength)

                    print("Total raises on st", street, "are", board.raises_weighted)

                    pot_odds = board_cont_cost / (pot_total + board_cont_cost)
                    print("Pot odds are", pot_odds)
                    print("Strength is", strength)

                    if strength >= pot_odds:  # Positive Expected Value!! at least call!!
                        print("Positive EV because strength >= pot odds")

                        if strength > 0.5 and random.random() < strength:  # raise sometimes, more likely if our hand is strong
                            print(
                                "High strength, so we then CommitAction with probability strength, costing", commit_cost)
                            print("CommitActioning")
                            my_actions[i] = commit_action
                            net_cost += commit_cost

                        else:  # try to call if we don't raise
                            print(
                                "We'll just call because because not that high strength and outside of probability strength")
                            # we call because we can afford it and it's +EV
                            if (board_cont_cost <= my_stack - net_cost):
                                print("Calling, costing", board_cont_cost)
                                my_actions[i] = CallAction()
                                net_cost += board_cont_cost

                            # we can't afford to call :(  should have managed our stack better
                            else:
                                print("Wanted to call but can't, Folding")
                                my_actions[i] = FoldAction()
                                net_cost += 0

                    else:  # Negative Expected Value!!! FOLD!!!
                        print("Negative EV, so folding")
                        my_actions[i] = FoldAction()
                        net_cost += 0

                else:  # board_cont_cost == 0, we control the action
                    print("We control the action.")

                    if random.random() < strength:  # raise sometimes, more likely if our hand is strong
                        print(
                            "We CommitAction with probability strength, costing", commit_cost)
                        print("CommitActioning")
                        my_actions[i] = commit_action
                        net_cost += commit_cost

                    else:  # just check otherwise
                        print("Outside probability strength, so just Checking")
                        my_actions[i] = CheckAction()
                        net_cost += 0
                print("###########")

            print()
            print("Done with this board")
            print()

        print("At end of action, stack size is", my_stack - net_cost)
        print("Done with this action")
        print()
        print()

        return my_actions


if __name__ == '__main__':
    run_bot(Player(), parse_args())
    # print("hi")
    # print(Player().hands_ev_descending)
