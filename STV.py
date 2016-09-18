# Area
class STV:
    def __init__(self, areanamep, usegroupsp=False, adaptivequotap = False):
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
        for c in self.active:
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
            self._redistribute_votes(v)
        self._sort_by_vote()

    def _recycle(self, candidatep, recycleratio):
        for vl in candidatep.votelinks:
            vl.weight -= vl.weight * recycleratio
            self._redistribute_votes(vl.voter)
        candidatep.refresh_votes()

    def _redistribute_votes(self, voterp):
        total = 1
        for vl in voterp.votelinks:
            if vl.candidate in self.winners:
                total -= vl.weight
            else:
                vl.weight = 0
        for vl in voterp.votelinks:
            if vl.candidate in self.active:
                vl.weight = total
                total = 0
                break
        voterp.waste = total  # waste

    def update_waste(self):
        self.totalwaste = 0
        for v in self.voters.values():
            self.totalwaste += v.waste

    def next_round(self):
        status = STVStatus()
        if len(self.winners) == self.totalseats:
            status.finished = True
        elif len(self.winners) + len(self.active) < self.totalseats:
            roundreturned = None
            for c in self.losers[::-1]:
                if not c.group.is_full():
                    roundreturned = c
                    break

            if roundreturned is not None:
                self.losers.remove(roundreturned)
                self.active.append(roundreturned)
                self._recycle(roundreturned, 0)

                status.candidate = roundreturned
                status.result = 0
                status.continuepossible = True
            else:
                status.message = 'Repechage failed'
        else:
            roundwinner = self.active[0]

            if roundwinner.votes >= self.quota or len(self.winners) + len(self.active) == self.totalseats:
                status.candidate = roundwinner
                status.result = 1

                self.winners.append(self.active.pop(0))

                surplus = roundwinner.votes - self.quota
                if surplus > 0:
                    recycleratio = surplus / roundwinner.votes
                    roundwinner.votes = self.quota
                    self._recycle(roundwinner, recycleratio)

                wgroup = roundwinner.group
                wgroup.seatswon += 1
                if self.usegroups and wgroup.is_full():
                    for c in self.active:
                        if c.group == wgroup:
                            grouploser = c
                            self.active.remove(c)
                            status.deleted_by_group.append(grouploser)
                            self.losers.append(grouploser)
                            self._recycle(grouploser, 1)
            else:
                roundloser = self.active.pop()
                status.candidate = roundloser
                status.result = -1
                self.losers.append(roundloser)
                self._recycle(roundloser, 1)
            status.continuepossible = True
        self._sort_by_vote()
        self.rounds += 1
        self.update_waste()

        if self.adaptivequota:
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

    def pk(self):
        return self.code

    def add_vote_link(self, votelinkp):
        self.votelinks.append(votelinkp)

    def refresh_votes(self):
        self.votes = 0
        for l in self.votelinks:
            self.votes += l.weight


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


# VoteLink
class _VoteLink:
    def __init__(self, voterp, candidatep):
        self.voter = voterp
        self.candidate = candidatep

        self.voter.add_vote_link(self)
        self.candidate.add_vote_link(self)
