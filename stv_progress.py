from collections import namedtuple

Candidate = namedtuple('Candidate', ['code', 'name', 'group'])
VoteLink = namedtuple('VoteLink', ['voterid', 'weight', 'candidatecode', 'status'])


class Position:
    def __init__(self, stv, status, previous_position=None):
        def tupelize_candidate_list(candlist):
            return [Candidate(c.code, c.name, c.group) for c in candlist]

        self.round = stv.rounds
        self.subround = stv.subrounds
        self.loopcount = stv.loopcount
        self.loopisallocation = stv.allocationcount > 0
        self.loopisreduction = stv.reductioncount > 0

        self.winners = tupelize_candidate_list(stv.winners)
        self.active = tupelize_candidate_list(stv.active)
        self.deactivated = tupelize_candidate_list(stv.deactivated)
        self.excluded = tupelize_candidate_list(stv.excluded)

        self.votelinks = {}
        for voter in stv.voters.values():
            vid = voter.uid
            for vl in voter.votelinks:
                ccode = vl.candidate.code
                self.votelinks[(vid, ccode)] = VoteLink(vid, vl.weight, ccode, vl.status)

        if status.winner is not None:
            self.message = 'Win:' + status.winner.name
        elif status.loser is not None:
            self.message = 'Loss:' + status.loser.name
        elif self.loopisallocation:
            self.message = 'Allocations: {}'.format(stv.allocationcount)
        elif self.loopisreduction:
            self.message = 'Reductions: {}'.format(stv.reductioncount)
        else:
            self.message = 'Beginning'

        self.nexttransform = None

        if previous_position is not None:
            self.add_previous(previous_position)

    def add_previous(self, previous):
        previous.nexttransform = t = Transform()
        t.nextposition = self

        for k, nvl in self.votelinks.items():
            t.add_difference(previous.votelinks[k], nvl)


class Transform:
    def __init__(self):
        self.nextposition = None
        self.returnvls = []
        self.sendvls = []

    def add_difference(self, previousvl, nextvl):
        weightdiff = nextvl.weight - previousvl.weight
        if weightdiff != 0:
            vllist = self.sendvls if weightdiff > 0 else self.returnvls
            vllist.append(VoteLink(nextvl.voterid, abs(weightdiff), nextvl.candidatecode, nextvl.status))


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
                    self.candidates = {c.code: c for c in newpos.active}

                currentpos = newpos

    def get_tansform_and_position(self):
        yield None, self.startpos
        t = self.startpos.nexttransform
        while t is not None:
            yield t, t.nextposition
            t = t.nextposition.nexttransform


def test_using_shell():
    try:
        from shell_interface import setup
    except ImportError:
        print('Could not import Shell Interface\nExiting')
        return

    print('Options:\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewmode = input('Type any number of options: ')

    stvp = STVProgress(setup('g' in viewmode, 'n' not in viewmode))
    candidates = stvp.candidates

    for t, pos in stvp.get_tansform_and_position():
        print('\n\nRound: {}.{}.{}'.format(pos.round, pos.subround, pos.loopcount))
        print(pos.message)
        print()

        if t is not None:
            vlformat = '{0:<10}{3} {1:.2f} {3} {2}'
            if t.returnvls:
                print('Return Fractions')
                for vl in t.returnvls:
                    print(vlformat.format(vl.voterid, vl.weight, candidates[vl.candidatecode].name, '<'))
            if t.sendvls:
                print('Send Fractions')
                for vl in t.sendvls:
                    print(vlformat.format(vl.voterid, vl.weight, candidates[vl.candidatecode].name, '>'))


if __name__ == '__main__':
    test_using_shell()
