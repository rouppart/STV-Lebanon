from collections import namedtuple

Candidate = namedtuple('Candidate', ['code', 'votes'])
VoteFraction = namedtuple('VoteFraction', ['voterid', 'fraction', 'candidatecode', 'status'])


class Position:
    # Loop Type
    UNKNOWN = 0
    REDUCTION = 1
    ALLOCATION = 2
    LOSS = 3
    WIN = 4

    def __init__(self, stv, status, previous_position):
        def tupelize_candidate_list(candlist):
            return [Candidate(c.code, c.votes) for c in candlist]

        self.round = stv.rounds
        self.subround = stv.subrounds
        self.loopcount = stv.loopcount

        if status.winner is not None:
            self.looptype = self.WIN
            self.message = 'Win: ' + status.winner.name
        elif status.loser is not None:
            self.looptype = self.LOSS
            self.message = 'Loss: ' + status.loser.name
        elif stv.reductioncount > 0:
            self.looptype = self.REDUCTION
            self.message = 'Reductions: {}'.format(stv.reductioncount)
        elif stv.allocationcount > 0:
            self.looptype = self.ALLOCATION
            self.message = 'Allocations: {}'.format(stv.allocationcount)
        else:
            self.looptype = self.UNKNOWN
            self.message = 'Beginning'

        self.excluded_group = status.excluded_by_group[0].group.name if status.excluded_by_group else None
        if self.excluded_group:
            self.message += '\nExclusion of group: ' + self.excluded_group

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
                vlstatuscode = {vl.EXCLUDED: 'Excluded', vl.DEACTIVATED: 'Deactivated', vl.ACTIVE: 'Active',
                                vl.PARTIAL: 'Partial', vl.FULL: 'Full'}[vl.status]
                self.votefractions[(vid, ccode)] = VoteFraction(vid, vl.weight, ccode, vlstatuscode)

        self.nexttransform = None

        if previous_position is not None:
            self.add_previous(previous_position)

    @property
    def hasdecision(self):
        return self.looptype >= self.LOSS

    def add_previous(self, previous):
        previous.nexttransform = t = Transform()
        t.nextposition = self

        for k, nvf in self.votefractions.items():
            t.add_difference(previous.votefractions[k], nvf)


class Transform:
    def __init__(self):
        self.nextposition = None
        self.returnvfs = []
        self.sendvfs = []

    def add_difference(self, previousvl, nextvf):
        weightdiff = nextvf.fraction - previousvl.fraction
        if weightdiff != 0:
            vflist = self.sendvfs if weightdiff > 0 else self.returnvfs
            vflist.append(VoteFraction(nextvf.voterid, abs(weightdiff), nextvf.candidatecode, nextvf.status))


class STVProgress:
    def __init__(self, stv):
        """ receives a fresh stv instance and creates all positions and transforms """
        self.startpos = None
        currentpos = None
        for status in stv.start():
            if status.yieldlevel >= 0:
                newpos = Position(stv, status, currentpos)

                if self.startpos is None:
                    self.startpos = newpos

                currentpos = newpos

    def get_tansform_and_position(self):
        yield None, self.startpos
        t = self.startpos.nexttransform
        while t is not None:
            yield t, t.nextposition
            t = t.nextposition.nexttransform


def test_using_cli():
    try:
        from cli_interface import setup
    except ImportError:
        print('Could not import CLI Interface\nExiting')
        return

    print('Options:\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewmode = input('Type any number of options: ')

    stv = setup('g' in viewmode, 'n' not in viewmode)
    stvp = STVProgress(stv)
    candidates = stv.candidates

    for t, pos in stvp.get_tansform_and_position():
        print('\n\nRound: {}.{}.{}'.format(pos.round, pos.subround, pos.loopcount))
        print(pos.message)
        print()

        if t is not None:
            vlformat = '{0:<12}{3} {1:.2f} {3} {2}'
            if t.returnvfs:
                print('Return Fractions')
                for vf in t.returnvfs:
                    print(vlformat.format(vf.voterid, vf.fraction, candidates[vf.candidatecode].name, '<'))
            if t.sendvfs:
                print('Send Fractions')
                for vf in t.sendvfs:
                    print(vlformat.format(vf.voterid, vf.fraction, candidates[vf.candidatecode].name, '>'))

        print('\nCandidates:')
        for candlist, status in [(pos.winners, 'W'), (pos.active, 'A'), (pos.deactivated, 'D'), (pos.excluded, 'E')]:
            for cand in candlist:
                print('{:<20}{}  {:,.2f}'.format(candidates[cand.code].name, status, cand.votes))


if __name__ == '__main__':
    test_using_cli()
