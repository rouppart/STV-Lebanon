LOST = -1
OPEN = 0
ALLOCATE = 1
PARTIAL = 2
FULL = 3


# Area
class STV:
    def __init__(self, areanamep, usegroupsp=False, adaptivequotap=False):
        self.areaname = areanamep
        self.usegroups = usegroupsp
        self.adaptivequota = adaptivequotap

        self.quota = 0
        self.totalseats = 0
        self.totalwaste = 0
        self.rounds = 0
        self.groups = dict()
        self.candidates = dict()
        self.voters = dict()

        self.active = []
        self.winners = []
        self.losers = []

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
            c.refresh_votes()

        act = self.active
        end = len(act)
        for i in range(0, end-1):
            imax = i
            for j in range(i, end):
                if act[imax].votes < act[j].votes:
                    temp = act[imax]
                    act[imax] = act[j]
                    act[j] = temp

    def prepare_for_count(self):
        for c in self.candidates.values():
            self.active.append(c)

        self.quota = len(self.voters) / self.totalseats
        for v in self.voters.values():
            v.allocate_votes()
        self._sort_by_vote()

    def update_waste(self):
        self.totalwaste = 0
        for v in self.voters.values():
            self.totalwaste += v.waste

    def next_round(self):
        status = STVStatus()
        if len(self.winners) == self.totalseats:  # finish
            status.finished = True
        elif len(self.winners) + len(self.active) < self.totalseats:  # repechage
            roundreturned = None
            for c in self.losers[::-1]:
                if not c.group.is_full():
                    roundreturned = c
                    break

            if roundreturned is not None:
                self.losers.remove(roundreturned)
                self.active.append(roundreturned)
                roundreturned.update_votelinks(OPEN)

                status.candidate = roundreturned
                status.result = 0
                status.continuepossible = True
            else:
                status.message = 'Repechage failed'
        else:  # continue elimination
            roundwinner = self.active[0]

            if roundwinner.votes >= self.quota or len(self.winners) + len(self.active) == self.totalseats:  # fixitlater
                status.candidate = roundwinner
                status.result = 1

                self.winners.append(self.active.pop(0))

                roundwinner.wonatquota = self.quota if roundwinner.votes > self.quota else roundwinner.votes
                roundwinner.update_votelinks(ALLOCATE)

                wgroup = roundwinner.group
                wgroup.seatswon += 1
                if self.usegroups and wgroup.is_full():
                    for c in self.active:
                        if c.group == wgroup:
                            grouploser = c
                            self.active.remove(c)
                            status.deleted_by_group.append(grouploser)
                            self.losers.append(grouploser)
                            grouploser.update_votelinks(LOST)
            else:
                roundloser = self.active.pop()
                status.candidate = roundloser
                status.result = -1
                self.losers.append(roundloser)
                roundloser.update_votelinks(LOST)

            # General Redistribution of votes
            doreduce = True
            while doreduce:
                doreduce = False
                for winner in self.winners[::-1]:
                    doreduce = doreduce or winner.doreduce
                    winner.reduce()
                    for vl in winner.votelinks:
                        vl.voter.allocate_votes()

            status.continuepossible = True
        self._sort_by_vote()
        self.rounds += 1
        self.update_waste()

        if self.adaptivequota and self.totalseats - len(self.winners) != 0:
            totalactivevotes = 0
            for ca in self.active:
                totalactivevotes += ca.votes
            self.quota = totalactivevotes / (self.totalseats - len(self.winners))

        return status


# Status
class STVStatus:
    def __init__(self):
        self.candidate = None
        self.result = None
        self.deleted_by_group = []
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

    def refresh_votes(self):
        self.votes = 0
        for l in self.votelinks:
            self.votes += l.weight

    def update_votelinks(self, newstatus):
        self.doreduce = True
        for vl in self.votelinks:
            vl.update_status(newstatus)

        for vl in self.votelinks:
            vl.voter.allocate_votes()

    def reduce(self):
        self.doreduce = False
        votersallocated = 0
        for vl in self.votelinks:  # count voters and set allocate to partial
            if vl.status > OPEN:
                votersallocated += 1
                if vl.status == ALLOCATE:
                    vl.update_status(PARTIAL)

        partialvls = []
        for vl in self.votelinks:  # create ordered list of partial votelinks
            if vl.status == PARTIAL:
                i = 0
                while i < len(partialvls):
                    if vl.weight <= partialvls[i].weight:
                        break
                    i += 1
                partialvls.insert(i, vl)

        i = 0
        partialtotweight = 0
        fullfraction = self.wonatquota / votersallocated
        while i < len(partialvls) and fullfraction > partialvls[i].weight:  # calculate new full support fraction
            partialtotweight += partialvls[i].weight
            i += 1
            if votersallocated - i > 0:
                fullfraction = (self.wonatquota - partialtotweight) / (votersallocated - i)

        while i < len(partialvls):  # fix status of partials who can now support fully
            partialvls[i].update_status(FULL)
            i += 1

        for vl in self.votelinks:  # reduce full support
            if vl.status == FULL:
                vl.weight = fullfraction


# Voter
class _Voter:
    def __init__(self, uidp):
        self.uid = uidp
        self.votelinks = []
        self.waste = 0

    def pk(self):
        return self.uid

    def add_vote_link(self, votelinkp):
        self.votelinks.append(votelinkp)

    def allocate_votes(self):
        total = 1
        for vl in self.votelinks:
            if vl.status in [PARTIAL, FULL]:
                total -= vl.weight

        for vl in self.votelinks:
            if vl.status in [OPEN, ALLOCATE]:
                vl.weight = total
                total = 0

                if vl.weight > 0 and vl.candidate.wonatquota > 0:
                    vl.update_status(ALLOCATE)
                    vl.candidate.doreduce = True
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
        allowed = (self.status == OPEN and newstatus == LOST) or (self.status <= newstatus and self.weight > 0) \
                   or (self.status == LOST and newstatus == OPEN)
        if allowed:
            self.status = newstatus
            if newstatus == LOST:
                self.weight = 0

        return allowed
