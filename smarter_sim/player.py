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


class Game:
    def __init__(self):
        pass


class Round:
    def __init__(self):
        self.current_street = 0
        self.boards = {1: Board(), 2: Board(), 3: Board()}


class Board:
    def __init__(self):
        self.strength_per_street = {0: None, 3: None, 4: None, 5: None}


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
        self.board_allocations.sort(
            key=lambda x: self.calculate_strength(x, my_cards, [], self._MONTE_CARLO_ITERS))

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

        for hand in list(itertools.combinations(list(deck), 2)):
            ev = self.get_ev(sorted([str(hand[0]), str(hand[1])],
                                    key=lambda x: self.values[x[0]], reverse=True))
            # TODO: better strength weighting
            ev = min(1, ev + 0.2)
            if random.random() < ev and hand not in opp_hands_to_try:
                opp_hands_to_try.add(hand)
            if len(opp_hands_to_try) >= iters:
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
                        self.board_allocations[i], my_cards, visible_community_cards, self._MONTE_CARLO_ITERS)
                    board.strength_per_street[round.current_street] = strength

                print("Calculated strength of hole cards and board is", strength)
                print()

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
                    if board_cont_cost > 5:  # <--- parameters to tweak.
                        print("Continue cost > 5 so we are intimidated.")
                        _INTIMIDATION = 0.15
                        # if our opp raises a lot, be cautious!
                        strength = max([0, strength - _INTIMIDATION])
                        print("New strength is", strength)

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
