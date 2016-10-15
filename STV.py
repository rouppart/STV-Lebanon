LOST = -1  # Lost support
OPEN = 0  # Open support
PARTIAL = 1  # Partial support
FULL = 2  # Full support


# Area
class STV:
    def __init__(self, areanamep, usegroupsp=False, nolosersp=False):
        self.areaname = areanamep
        self.usegroups = usegroupsp
        self.nolosers = nolosersp

        self.quota = 0
        self.totalseats = 0
        self.totalwaste = 0
        self.rounds = 0
        self.issubround = False
        self.subrounds = 0
        self.groups = dict()
        self.candidates = dict()
        self.voters = dict()

        self.winners = []
        self.active = []
        self.losers = []

        self.doreactivate = False

    def add_group(self, namep, seatsp):
        newgroup = _Group(namep, seatsp)
        self.groups[newgroup.pk()] = newgroup
        self.totalseats += seatsp

    def add_candidate(self, codep, namep, groupnamep):
        newcandidate = _Candidate(codep, namep, self.groups[groupnamep])
        self.candidates[newcandidate.pk()] = newcandidate

    def add_voter(self, uidp, candlistp):
        newvoter = _Voter(uidp)
        self.voters[newvoter.pk()] = newvoter
        for c in candlistp:
            _VoteLink(newvoter, self.candidates[c])

    def _sort_by_vote(self):
        for c in self.candidates.values():
            c.sum_votes()
        self.totalwaste = 0
        for v in self.voters.values():
            self.totalwaste += v.waste

        self.active.sort(key=lambda candidate: candidate.votes, reverse=True)

    def prepare_for_count(self):
        for c in self.candidates.values():
            self.active.append(c)

        self.quota = len(self.voters) / self.totalseats
        for v in self.voters.values():
            v.allocate_votes()
        self._sort_by_vote()

    def _process_candidate(self, candidate, newstatus):
        if newstatus == LOST:
            self.active.remove(candidate)
            self.losers.append(candidate)
        elif newstatus == OPEN:
            self.losers.remove(candidate)
            self.active.append(candidate)
        elif newstatus in [PARTIAL, FULL]:
            self.active.remove(candidate)
            self.winners.append(candidate)

        candidate.update_votelinks(newstatus)

    def next_round(self):
        if self.issubround:
            self.subrounds += 1
        else:
            self.rounds += 1
            self.subrounds = 1
        self.issubround = self.nolosers

        status = STVStatus()

        # finish
        if len(self.winners) == self.totalseats:
            status.finished = True

        # reactivation
        elif not self.nolosers and len(self.winners) + len(self.active) < self.totalseats\
                or self.nolosers and len(self.active) == 0\
                or self.doreactivate:
            self.doreactivate = False
            status.result = 0
            for c in self.losers[::-1]:
                if not self.usegroups or not c.group.is_full():
                    self._process_candidate(c, OPEN)

                    status.continuepossible = True
                    status.reactivated.append(c)

                    if not self.nolosers:
                        break

            if not status.continuepossible:
                status.message = 'Reactivation failed'

        # elimination
        else:
            topcandidate = self.active[0]

            # Win
            if topcandidate.votes >= self.quota \
                    or not self.nolosers and len(self.winners) + len(self.active) == self.totalseats \
                    or self.nolosers and len(self.active) == 1:
                roundwinner = topcandidate
                roundwinner.wonatquota = self.quota if roundwinner.votes > self.quota else roundwinner.votes
                self._process_candidate(roundwinner, PARTIAL)

                status.candidate = roundwinner
                status.result = 1

                wgroup = roundwinner.group
                wgroup.seatswon += 1
                if self.usegroups and wgroup.is_full():
                    for c in self.active[:]:
                        if c.group == wgroup:
                            self._process_candidate(c, LOST)

                            status.deleted_by_group.append(c)
                if self.nolosers and self.losers:
                    self.doreactivate = True

                self.issubround = False
            # Lose
            else:
                roundloser = self.active[-1]
                self._process_candidate(roundloser, LOST)

                status.candidate = roundloser
                status.result = -1

            status.continuepossible = True

        # General Redistribution of votes
        repeatreduce = True
        while repeatreduce:
            repeatreduce = False
            for voter in self.voters.values():
                if voter.doallocate:
                    voter.allocate_votes()
            for winner in self.winners[::-1]:
                if winner.doreduce:
                    repeatreduce = True
                    winner.reduce()

        self._sort_by_vote()

        return status


# Status
class STVStatus:
    def __init__(self):
        self.candidate = None
        self.result = None
        self.deleted_by_group = []
        self.reactivated = []
        self.message = ''
        self.continuepossible = False
        self.finished = False


# Seat
class _Group:
    def __init__(self, namep, seatsp):
        self.name = namep
        self.seats = seatsp
        self.seatswon = 0

    def pk(self):
        return self.name

    def is_full(self):
        return self.seatswon >= self.seats


# Candidate
class _Candidate:
    def __init__(self, codep, namep, groupp):
        self.code = codep
        self.name = namep
        self.group = groupp

        self.votelinks = []
        self.votes = 0
        self.wonatquota = 0
        self.doreduce = False

    def pk(self):
        return self.code

    def add_vote_link(self, votelinkp):
        self.votelinks.append(votelinkp)

    def sum_votes(self):
        self.votes = 0
        for l in self.votelinks:
            self.votes += l.weight

    def update_votelinks(self, newstatus):
        self.doreduce = True
        for vl in self.votelinks:
            vl.update_status(newstatus)

        for vl in self.votelinks:
            vl.voter.doallocate = True

    def reduce(self):
        self.doreduce = False
        supportingvoters = 0

        # Count voters and set allocate to partial
        for vl in self.votelinks:
            if vl.status > OPEN:
                supportingvoters += 1

        # Create ordered list of partial votelinks
        partialvls = []
        for vl in self.votelinks:
            if vl.status == PARTIAL:
                i = 0
                while i < len(partialvls):
                    if vl.weight <= partialvls[i].weight:
                        break
                    i += 1
                partialvls.insert(i, vl)

        # Calculate new full support fraction
        i = 0
        totalpartialweight = 0
        fullsupportfraction = self.wonatquota / supportingvoters
        while i < len(partialvls) and fullsupportfraction > partialvls[i].weight:
            totalpartialweight += partialvls[i].weight
            i += 1
            if supportingvoters - i > 0:
                fullsupportfraction = (self.wonatquota - totalpartialweight) / (supportingvoters - i)

        # Fix status of partials who can now support fully
        while i < len(partialvls):
            partialvls[i].update_status(FULL)
            i += 1

        # Reduce full support
        for vl in self.votelinks:
            if vl.status == FULL:
                vl.weight = fullsupportfraction
                vl.voter.doallocate = True


# Voter
class _Voter:
    def __init__(self, uidp):
        self.uid = uidp
        self.votelinks = []
        self.waste = 0
        self.doallocate = False

    def pk(self):
        return self.uid

    def add_vote_link(self, votelinkp):
        self.votelinks.append(votelinkp)

    def allocate_votes(self):
        self.doallocate = False

        # Collect all fixed weight and reset unfixed weight
        total = 1
        for vl in self.votelinks:
            if vl.status in [PARTIAL, FULL]:
                total -= vl.weight
            else:
                vl.weight = 0

        # Give unfixed weight to first Open votelink
        for vl in self.votelinks:
            if vl.status == OPEN:
                vl.weight = total
                total = 0

                # New available support to previous winner
                if vl.weight > 0 and vl.candidate.wonatquota > 0:
                    vl.update_status(PARTIAL)
                    vl.candidate.doreduce = True
                break

        self.waste = total


# VoteLink
class _VoteLink:
    def __init__(self, voterp, candidatep):
        self.voter = voterp
        self.candidate = candidatep
        self.weight = 0

        self.voter.add_vote_link(self)
        self.candidate.add_vote_link(self)

        self.status = OPEN

    def update_status(self, newstatus):
        if (self.status == OPEN and newstatus == LOST) or (self.status <= newstatus and self.weight > 0)\
                or (self.status == LOST and newstatus == OPEN):
            self.status = newstatus
            return True
        else:
            return False
