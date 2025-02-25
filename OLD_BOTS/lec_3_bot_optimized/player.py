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

import sys, os

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
        self.board_allocations = [[], [], []] #keep track of our allocations at round start
        self.hole_strengths = [0, 0, 0] #better representation of our hole strengths (win probability!)
        self.sampling_duration_total = 0
        self.MONTE_CARLO_ITERS = 100  # the number of monte carlo samples we will use
        self.RANDOMIZATION_ON = False # whether to randomize ordering of holes to avoid deterministic exploitation
        self.blockPrint()
        # random.seed(10)




    # Disable
    def blockPrint(self):
        sys.stdout = open(os.devnull, 'w')

    # Restore
    def enablePrint(self):
        sys.stdout = sys.__stdout__

    def rank_to_numeric(self, rank):

        if rank.isnumeric(): #2-9
            return int(rank)
        elif rank == 'T': #10 is T, so we need to specify it here
            return 10
        elif rank == 'J': #Face cards for the rest of them
            return 11
        elif rank == 'Q':
            return 12
        elif rank == 'K':
            return 13
        else: #Ace (A) is the only one left
            return 14

    def sort_cards_by_rank(self, cards):
        return sorted(cards, reverse=True, key=lambda x: self.rank_to_numeric(x[0])) #we want it in descending order

    def allocate_cards(self, my_cards):
        '''
        Method that allocates our cards at the beginning of a round. Method
        modifies self.board_allocations. The method attempts to make pairs
        by allocating hole cards that share a rank if possible. The exact
        stack these cards are allocated to is not defined.

        Arguments:
        my_cards: a list of the 6 cards given to us at round start
        '''
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

            elif len(cards) == 2 or len(cards) == 4:  # a single pair or two pairs can be made here, add them all
                pairs += cards

            else:  # len(cards) == 3  A single pair plus an extra can be made here
                pairs.append(cards[0])
                pairs.append(cards[1])
                singles.append(cards[2])

        cards_remaining = set(my_cards)  # keep track of the cards we need to allocate still
        allocated_cards = set()  # the cards we've committed to the board
        holes_allocated = []  # the holes we've made

        _MIN_PAIR_VALUE = 5  # we only want pairs stronger than this!

        for i in range(len(pairs) // 2):
            pair = [pairs[2 * i], pairs[2 * i + 1]]  # get our pair
            pair_rank = pair[0][0]

            if self.rank_to_numeric(pair_rank) >= _MIN_PAIR_VALUE:  # our pair is strong! keep it!
                holes_allocated.append(pair)
                allocated_cards.update(pair)

        cards_remaining = cards_remaining - allocated_cards  # update our remaining cards

        sorted_remaining = self.sort_cards_by_rank(list(cards_remaining))  # sort our remaining cards

        for i in range(len(sorted_remaining) - 1):  # go through every adjecent card for straight draws!
            card_1 = sorted_remaining[i]
            card_2 = sorted_remaining[i + 1]

            rank_diff = self.rank_to_numeric(card_1[0]) - self.rank_to_numeric(card_2[0])  # how far apart our ranks are

            if (rank_diff <= 1) and (card_1 not in allocated_cards) and (
                    card_2 not in allocated_cards):  # if they're close and unused
                hole = [card_1, card_2]  # use them!
                holes_allocated.append(hole)
                allocated_cards.update(hole)

        cards_remaining = cards_remaining - allocated_cards  # update our bookkeeping

        suits = {}
        for card in cards_remaining:  # look for flush draws
            card_suit = card[1]

            if card_suit in suits:
                suits[card_suit].append(card)

            else:
                suits[card_suit] = [card]

        for suit in suits:

            cards = suits[suit]
            if len(cards) == 2 or len(cards) == 3:  # we found something!
                hole = [cards[0], cards[1]]
                holes_allocated.append(hole)
                allocated_cards.update(hole)

            elif len(cards) == 4:  # be wary!!! this could be too many of the same suits
                hole_1 = [cards[0], cards[1]]  # but we'll try anyway for now
                hole_2 = [cards[2], cards[3]]

                holes_allocated.append(hole_1)
                allocated_cards.update(hole_1)

                holes_allocated.append(hole_2)
                allocated_cards.update(hole_2)

        cards_remaining = cards_remaining - allocated_cards  # update cards remaining
        extra_cards = list(cards_remaining)

        for i in range(len(extra_cards) // 2):  # we couldnt do anything with these...oh well
            hole = [extra_cards[2 * i], extra_cards[2 * i + 1]]  # just group them up randomly
            holes_allocated.append(hole)
            allocated_cards.update(hole)

        cards_remaining = cards_remaining - allocated_cards  # final update

        assert len(holes_allocated) == 3, 'we allocated too many cards!!'  # check for mistakes!!!
        assert len(cards_remaining) == 0, "we didn't allocate enough!"

        return holes_allocated  # return our decisions

    def assign_holes(self, hole_cards):

        holes_and_strengths = []  # keep track of holes and their strengths

        for hole in hole_cards:
            strength = self.calculate_strength(hole, [], self.MONTE_CARLO_ITERS)  # use our monte carlo sim!
            holes_and_strengths.append((hole, strength))

        holes_and_strengths = sorted(holes_and_strengths, key=lambda x: x[1])  # sort them by strength

        if self.RANDOMIZATION_ON:
            if random.random() < 0.15:  # swap strongest with second, makes our strategy non-deterministic!
                temp = holes_and_strengths[2]
                holes_and_strengths[2] = holes_and_strengths[1]
                holes_and_strengths[1] = temp

            if random.random() < 0.15:  # swap second with last, makes us even more random
                temp = holes_and_strengths[1]
                holes_and_strengths[1] = holes_and_strengths[0]
                holes_and_strengths[0] = temp

        for i in range(NUM_BOARDS):  # we have our final board allocations!
            self.board_allocations[i] = holes_and_strengths[i][0]
            self.hole_strengths[i] = holes_and_strengths[i][1]

    def calculate_strength(self, hole_cards, community_cards, iters):
        '''
        A Monte Carlo method meant to estimate the win probability of a pair of 
        hole cards. Simlulates 'iters' games and determines the win rates of our cards

        Arguments:
        hole: a list of our two hole cards
        iters: a integer that determines how many Monte Carlo samples to take
        '''

        start_sampling_time = time.time()

        deck = eval7.Deck() #eval7 object!
        hole_cards = [eval7.Card(card) for card in hole_cards] #card objects, used to evaliate hands
        community_cards = [eval7.Card(card) for card in community_cards]  # card objects, used to evaliate hands

        for card in hole_cards: #remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        for card in community_cards: #remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        score = 0

        for _ in range(iters): #take 'iters' samples
            deck.shuffle() #make sure our samples are random

            _COMM = 5 - len(community_cards) #the number of cards we need to draw
            _OPP = 2

            draw = deck.peek(_COMM + _OPP)

            opp_hole = draw[: _OPP]
            hidden_community = draw[_OPP: ]

            our_hand = hole_cards + community_cards + hidden_community #the two showdown hands
            opp_hand = opp_hole + community_cards + hidden_community

            our_hand_value = eval7.evaluate(our_hand) #the ranks of our hands (only useful for comparisons)
            opp_hand_value = eval7.evaluate(opp_hand)

            if our_hand_value > opp_hand_value: #we win!
                score += 2
            
            elif our_hand_value == opp_hand_value: #we tie.
                score += 1
            
            else: #we lost....
                score += 0
        
        hand_strength = score / (2 * iters) #this is our win probability!

        sampling_duration = time.time() - start_sampling_time

        self.sampling_duration_total += sampling_duration

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
        my_bankroll = game_state.bankroll  # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        opp_bankroll = game_state.opp_bankroll # ^but for your opponent
        game_clock = game_state.game_clock  # the total number of seconds your bot has left to play this game
        round_num = game_state.round_num  # the round number from 1 to NUM_ROUNDS
        my_cards = round_state.hands[active]  # your six cards at the start of the round
        big_blind = bool(active)  # True if you are the big blind

        _MONTE_CARLO_ITERS = 100 #the number of monte carlo samples we will use
        
        allocated_holes = self.allocate_cards(my_cards) #our allocation strategy
        self.assign_holes(allocated_holes) #our randomized assignment method

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
        my_delta = terminal_state.deltas[active]  # your bankroll change from this round
        opp_delta = terminal_state.deltas[1-active] # your opponent's bankroll change from this round 
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        street = previous_state.street  # 0, 3, 4, or 5 representing when this round ended
        i = 1
        print("My remaining stack is", previous_state.stacks[active])
        print()

        for terminal_board_state in previous_state.board_states:
            print("Board", i)
            previous_board_state = terminal_board_state.previous_state
            my_cards = previous_board_state.hands[active]  # your cards
            opp_cards = previous_board_state.hands[1-active]  # opponent's cards or [] if not revealed
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
                    print("Opponent folded, so I win on this board", terminal_board_state.deltas[active])
                else:
                    print("I folded, so I gain nothing on this board")
            # showdown winner
            else:
                my_cards = [eval7.Card(card) for card in my_cards if card]
                opp_cards = [eval7.Card(card) for card in opp_cards if card]
                community_cards = [eval7.Card(card) for card in community_cards if card]

                my_hand = eval7.evaluate(my_cards + community_cards)
                opp_hand = eval7.evaluate(opp_cards + community_cards)

                if my_hand > opp_hand:
                    print("I win on this showdown board", previous_board_state.pot)
                elif opp_hand > my_hand:
                    print("I lost on this showdown board, so I gain nothing on this showdown board")
                else:
                    print("Tie, so I gain on this showdown board", previous_board_state.pot // 2)
            print()
            i += 1

        print("I win on this round total:", my_delta)
        print()
        
        self.board_allocations = [[], [], []] #reset our variables at the end of every round!
        self.hole_strengths = [0, 0, 0]

        game_clock = game_state.game_clock #check how much time we have remaining at the end of a game
        round_num = game_state.round_num #Monte Carlo takes a lot of time, we use this to adjust!

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
        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        street = round_state.street  # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active]  # your cards across all boards
        board_cards = [board_state.deck if isinstance(board_state, BoardState) else board_state.previous_state.deck for board_state in round_state.board_states] #the board cards
        my_pips = [board_state.pips[active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips you have contributed to the pot on each board this round of betting
        opp_pips = [board_state.pips[1-active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips your opponent has contributed to the pot on each board this round of betting
        continue_cost = [opp_pips[i] - my_pips[i] for i in range(NUM_BOARDS)] #the number of chips needed to stay in each board's pot
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        stacks = [my_stack, opp_stack]
        print("Before choosing board actions, my stack is", my_stack)
        print()
        net_upper_raise_bound = round_state.raise_bounds()[1] # max raise across 3 boards
        net_cost = 0 # keep track of the net additional amount you are spending across boards this round

        my_actions = [None] * NUM_BOARDS
        for i in range(NUM_BOARDS):
            print("~ Currently solving board", i+1, " ~")
            if isinstance(round_state.board_states[i], TerminalState):
                print("This board is Terminal.")
                print("!!!!")
            elif round_state.board_states[i].settled:
                print("This board is settled, can only check.")
                print("!!!!")

            hole_cards = self.board_allocations[i]


            if AssignAction in legal_actions[i]:
                print("Assigning preferred hole cards")
                my_actions[i] = AssignAction(hole_cards) #add to our actions

            elif isinstance(round_state.board_states[i], TerminalState): #make sure the game isn't over at this board
                print("At a terminal state")
                my_actions[i] = CheckAction() #check if it is

            # round of active play
            else: #do we add more resources?

                print("Hole cards on this board are", hole_cards)
                print("Visible community cards are", [card for card in board_cards[i] if card])
                print()
                visible_community_cards = [card for card in board_cards[i] if card]
                strength = self.calculate_strength(self.board_allocations[i], visible_community_cards, 100)
                print("Calculated strength of hole cards and board is", strength)
                print()

                print("Round of active play")
                print("Our stack has", my_stack - net_cost)
                board_cont_cost = continue_cost[i] #we need to pay this to keep playing
                board_total = round_state.board_states[i].pot #amount before we started betting
                pot_total = my_pips[i] + opp_pips[i] + board_total #total money in the pot right now
                print("Old pot has", round_state.board_states[i].pot, ", my pips are", my_pips[i], ", opponent pips are", opp_pips[i])
                print("Pot total is", pot_total)
                print("Continue cost is", board_cont_cost)
                min_raise, max_raise = round_state.board_states[i].raise_bounds(active, round_state.stacks)
                print("Min raise is", min_raise, ", max raise is", max_raise)
                # strength = self.hole_strengths[i]
                # print("Current street is", street)

                if street < 3: #pre-flop
                    raise_amount = int(my_pips[i] + board_cont_cost + 0.4 * (pot_total + board_cont_cost)) #play a little conservatively pre-flop
                    print("Desired pre-flop raise amount is", raise_amount)
                else:
                    raise_amount = int(my_pips[i] + board_cont_cost + 0.75 * (pot_total + board_cont_cost)) #raise the stakes deeper into the game
                    print("Desired post-flop raise amount is", raise_amount)


                raise_amount = max([min_raise, raise_amount]) #make sure we have a valid raise
                raise_amount = min([max_raise, raise_amount])

                print("After bounding raise_amount, desired raise amount is", raise_amount)

                raise_cost = raise_amount - my_pips[i] #how much it costs to make that raise

                print("This raise will cost", raise_cost)

                print()

                if RaiseAction in legal_actions[i] and (raise_cost <= my_stack - net_cost): #raise if we can and if we can afford it
                    print("Commit action is Raise because we can afford the full desired raise, raising to",raise_amount, ", costing", raise_cost)
                    commit_action = RaiseAction(raise_amount)
                    commit_cost = raise_cost

                elif CallAction in legal_actions[i] and (board_cont_cost <= my_stack - net_cost):  # call if we can afford it!:
                    print("Commit action is Call, can't afford full raise, paying", board_cont_cost)
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
                if board_cont_cost > 0: #our opp raised!!! we must respond
                    print("Opponent has raised. We must respond. Continue cost is", board_cont_cost)
                    if board_cont_cost > 5: #<--- parameters to tweak.
                        print("Continue cost > 5 so we are intimidated.")
                        _INTIMIDATION = 0.15
                        strength = max([0, strength - _INTIMIDATION]) #if our opp raises a lot, be cautious!
                        print("New strength is", strength)


                    pot_odds = board_cont_cost / (pot_total + board_cont_cost)
                    print("Pot odds are", pot_odds)
                    print("Strength is", strength)

                    if strength >= pot_odds: #Positive Expected Value!! at least call!!
                        print("Positive EV because strength >= pot odds")

                        if strength > 0.5 and random.random() < strength: #raise sometimes, more likely if our hand is strong
                            print("High strength, so we then CommitAction with probability strength, costing", commit_cost)
                            print("CommitActioning")
                            my_actions[i] = commit_action
                            net_cost += commit_cost

                        else:  # try to call if we don't raise
                            print("We'll just call because because not that high strength and outside of probability strength")
                            if (board_cont_cost <= my_stack - net_cost):  # we call because we can afford it and it's +EV
                                print("Calling, costing", board_cont_cost)
                                my_actions[i] = CallAction()
                                net_cost += board_cont_cost

                            else:  # we can't afford to call :(  should have managed our stack better
                                print("Wanted to call but can't, Folding")
                                my_actions[i] = FoldAction()
                                net_cost += 0
                    
                    else: #Negative Expected Value!!! FOLD!!!
                        print("Negative EV, so folding")
                        my_actions[i] = FoldAction()
                        net_cost += 0
                
                else: #board_cont_cost == 0, we control the action
                    print("We control the action.")

                    if random.random() < strength: #raise sometimes, more likely if our hand is strong
                        print("We CommitAction with probability strength, costing", commit_cost)
                        print("CommitActioning")
                        my_actions[i] = commit_action
                        net_cost += commit_cost

                    else: #just check otherwise
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
