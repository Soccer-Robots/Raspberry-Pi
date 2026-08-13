'''
i'll list here first what is the gameplan. First is that we put our changing stations in 2 different corners: the top left and top right. The leftmost robot goes left, and the rightmost robot goes right. They first turn to face the corner, move towards it, then rotate so that their back faces towards the corner, then move back.

Anyways for how this is triggered, at end of game trigger thread and have a flag determining if it's done, can't say it's ready until poll = true, and thread works through the logic of sending them to the right place and returns (while enabling flag) once done.
'''
