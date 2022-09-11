from typing import List, Optional, Generator
from collections import namedtuple
from .stv import STV

Candidate = namedtuple('Candidate', ['code', 'votes'])
VoteFraction = namedtuple('VoteFraction', ['voterid', 'fraction', 'candidatecode', 'status'])


class Position:
    # Loop Type
    UNKNOWN = 0
    REDUCTION = 1
    ALLOCATION = 2
    LOSS = 3
    WIN = 4

    def __init__(self, stv: STV, status, previous_position):
        def tupelize_candidate_list(candlist):
            return [Candidate(c.code, c.votes) for c in candlist]

        self.round = stv.rounds
        self.subround = stv.subrounds
        self.loopcount = stv.loopcount

        if status.winner is not None:
            self.looptype = self.WIN
            self.message = f"Win: {status.winner.name}"
        elif status.loser is not None:
            self.looptype = self.LOSS
            self.message = f"Loss: {status.loser.name}"
        elif stv.reductioncount > 0:
            self.looptype = self.REDUCTION
            self.message = f"Reductions: {stv.reductioncount}"
        elif stv.allocationcount > 0:
            self.looptype = self.ALLOCATION
            self.message = f"Allocations: {stv.allocationcount}"
        else:
            self.looptype = self.UNKNOWN
            self.message = "Beginning"

        self.excluded_group = status.excluded_by_group[0].group.name if status.excluded_by_group else None
        if self.excluded_group:
            self.message += f"\nExclusion of group: {self.excluded_group}"

        self.winners = tupelize_candidate_list(stv.winners)
        self.active = tupelize_candidate_list(stv.active)
        self.deactivated = tupelize_candidate_list(stv.deactivated)
        self.excluded = tupelize_candidate_list(stv.excluded)

        self.votefractions = {}
        self.waste = {}  # Key is VoterID
        for voter in stv.voters.values():
            vid = voter.uid
            self.waste[vid] = voter.waste
            for vl in voter.votelinks:
                ccode = vl.candidate.code
                vlstatuscode = {vl.EXCLUDED: "Excluded", vl.DEACTIVATED: "Deactivated", vl.ACTIVE: "Active",
                                vl.PARTIAL: "Partial", vl.FULL: "Full"}[vl.status]
                self.votefractions[(vid, ccode)] = VoteFraction(vid, vl.weight, ccode, vlstatuscode)

        self.nexttransform: Optional[Transform] = None

        if previous_position is not None:
            self.add_previous(previous_position)

    @property
    def hasdecision(self) -> bool:
        return self.looptype >= self.LOSS

    def add_previous(self, previous: 'Position') -> None:
        previous.nexttransform = t = Transform(self)

        for k, nvf in self.votefractions.items():
            t.add_difference(previous.votefractions[k], nvf)


class Transform:
    def __init__(self, nextposition: Position):
        self.nextposition = nextposition
        self.returnvfs: List[VoteFraction] = []
        self.sendvfs: List[VoteFraction] = []

    def add_difference(self, previousvf: VoteFraction, nextvf: VoteFraction) -> None:
        weightdiff = nextvf.fraction - previousvf.fraction
        if weightdiff != 0:
            vflist = self.sendvfs if weightdiff > 0 else self.returnvfs
            vflist.append(VoteFraction(nextvf.voterid, abs(weightdiff), nextvf.candidatecode, nextvf.status))


class STVProgress:
    def __init__(self, stv: STV):
        """ receives a fresh stv instance and creates all positions and transforms """
        self.startpos = None
        currentpos = None
        for status in stv.start():
            if status.yieldlevel >= 0:
                newpos = Position(stv, status, currentpos)

                if self.startpos is None:
                    self.startpos = newpos

                currentpos = newpos

    def get_tansform_and_position(self) -> Generator:
        if self.startpos is None:
            raise Exception("STV Progress could not initialize")
        yield None, self.startpos
        t = self.startpos.nexttransform
        while t is not None:
            yield t, t.nextposition
            t = t.nextposition.nexttransform
