'''
This bot picks initial hands prioritizing pairs and then rank, then assigning the strongest hand to Board 3.
'''
import random
import time
import pandas as pd

import sys
import os


class Player():
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
        # random.seed(10)

        # make sure this df isn't too big!! Loading data all at once might be slow if you did more computations!
        # the values we computed offline, this df is slow to search through though
        calculated_df = pd.read_csv('hole_evs.csv')
        holes = calculated_df.Holes  # the columns of our spreadsheet
        strengths = calculated_df.EVs
        # convert to a dictionary, O(1) lookup time!
        self.starting_strengths = dict(zip(holes, strengths))

    # Disable

if __name__ == '__main__':
    evs = list(Player().starting_strengths.values())
    evs = list(set(evs))
    evs.sort(reverse=True)
    enum_hands = []
    ranks = [""]
    print(len(set(evs)))
    print(evs[30])
    print(evs)
