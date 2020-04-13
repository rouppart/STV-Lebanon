class STV:
    """ Contains the whole voting system and does the counting """
    def __init__(self, areaname, usegroups=False, reactivationmode=False):
        # Static attributes
        self.areaname = areaname
        self.usegroups = usegroups
        self.reactivationmode = reactivationmode

        # Input Attributes
        self.groups = {}
        self.candidates = {}
        self.voters = {}

        # Variable Running Attributes
        self.totalseats = 0
        self.rounds = 0
        self.issubround = False
        self.subrounds = 0
        self.loopcount = 0
        self.allocationcount = 0
        self.reductioncount = 0

        self.winners = []
        self.active = []
        self.deactivated = []
        self.excluded = []

    # Setup Methods
    def add_group(self, name, seats):
        if name in self.groups:
            raise Exception('Group {} was already added'.format(name))
        self.groups[name] = _Group(name, seats)
        self.totalseats += seats

    def add_candidate(self, code, name, groupname):
        if code in self.candidates:
            raise Exception('Candidate {} was already added'.format(code))
        self.candidates[code] = candidate = _Candidate(code, name, self.groups[groupname])
        self.active.append(candidate)  # Put all Candidates in the active list

    def add_voter(self, uid, candlist):
        if uid in self.voters:
            raise Exception('Voter {} was already added'.format(uid))
        self.voters[uid] = newvoter = _Voter(uid)
        for ccode in candlist:
            try:
                _VoteLink(newvoter, self.candidates[ccode])
            except KeyError:
                raise Exception('Voter {} voted used an invalid Candidate Code ({})'.format(uid, ccode))

    @property
    def quota(self):
        return len(self.voters) / self.totalseats

    @property
    def totalwaste(self):
        return len(self.voters) - sum(c.votes for c in self.active + self.winners)

    def _sort_active(self):
        self.active.sort(key=lambda candidate: candidate.votes, reverse=True)

    def start(self):
        """ Advance to next Round. Either there will be a win, a loss or reactivation. Then do heavy counting """
        yield STVStatus(STVStatus.BEGIN)

        while True:
            # Manage Round counting
            if self.issubround:
                self.subrounds += 1
            else:
                self.rounds += 1
                self.subrounds = 1
            self.issubround = True
            self.loopcount = 0

            # Part 1: General Redistribution of votes
            loopstatus = STVStatus(STVStatus.LOOP)

            repeatreduce = True
            while repeatreduce:  # Main Loop
                repeatreduce = False
                self.loopcount += 1

                for voter in self.voters.values():  # Allocation Loop
                    if voter.doallocate:
                        voter.allocate_votes()  # This can give surplus votes to candidates
                        self.allocationcount += 1
                if self.allocationcount > 0:
                    yield loopstatus
                    self.allocationcount = 0

                for winner in self.winners:  # Reduction Loop
                    if winner.doreduction:  # If candidate received surplus votes allocate_votes above
                        repeatreduce = True  # Repeat Main loop
                        winner.reduce()  # Return surplus votes to voters and trigger doallocate
                        self.reductioncount += 1
                if self.reductioncount > 0:
                    yield loopstatus
                    self.reductioncount = 0

            self._sort_active()

            if self.rounds == 1 and self.subrounds == 1:  # Show pretty Initial Round for humans
                yield STVStatus(STVStatus.INITIAL)

            # Part 2: Decide
            decstatus = STVStatus()
            topcandidate = self.active[0]
            # Win. Either Quota is reached, or cannot lose a candidate because active list becomes too small
            if self.active[0].votes >= self.quota or len(self.winners) + len(self.active) == self.totalseats:
                # Register at which vote amount the winner won in case he won below the quota
                topcandidate.wonatquota = self.quota if topcandidate.votes > self.quota else topcandidate.votes
                # Status set to PARTIAL and let Candidate's Reduce function decide if FULL
                self._process_candidate(topcandidate, self.active, self.winners, _VoteLink.PARTIAL, False)
                topcandidate.doreduction = True

                # Update status
                decstatus.winner = topcandidate

                # Update candidate's group
                wgroup = topcandidate.group
                wgroup.seatswon += 1

                # Process group constraints if groupquota is on
                if self.usegroups and wgroup.is_full:
                    for c in self.active + self.deactivated:
                        if c.group == wgroup:
                            fromlist = self.active if c in self.active else self.deactivated
                            self._process_candidate(c, fromlist, self.excluded, _VoteLink.EXCLUDED, True)
                            decstatus.excluded_by_group.append(c)

                if len(self.winners) == self.totalseats:  # Finish and exit loop
                    decstatus.yieldlevel = decstatus.END
                    yield decstatus
                    return
                elif self.reactivationmode:  # If win and not finished and reactivationmode is on
                    decstatus.reactivated = self._reactivate()
                self.issubround = False

            else:  # Lose
                # Remove last active candidate
                roundloser = self.active[-1]
                self._process_candidate(roundloser, self.active, self.deactivated, _VoteLink.DEACTIVATED, True)
                decstatus.loser = roundloser

            # If there are not enough active candidates, reactivate some.
            missingseats = self.totalseats - len(self.winners) - len(self.active)
            if missingseats > 0:
                # This can happen if reactivationmode is off and group quotas exclude too many candidates
                decstatus.reactivated = self._reactivate(missingseats)
                if len(decstatus.reactivated) != missingseats:
                    raise Exception('Reactivation failed in Round {}.{}'.format(self.rounds, self.subrounds))

            decstatus.yieldlevel = decstatus.SUBROUND if self.issubround else decstatus.ROUND
            yield decstatus

    @staticmethod
    def _process_candidate(candidate, fromlist, tolist, new_vl_status, votersdoallocate):
        """ Transfer candidate and update its votelinks """
        fromlist.remove(candidate)
        tolist.append(candidate)

        for vl in candidate.votelinks:
            vl.status = new_vl_status
            vl.voter.doallocate = votersdoallocate

    def _reactivate(self, limit=None):
        """ Reactivates deactivated Candidates """
        reactivated = []
        for c in self.deactivated[::-1]:
            self._process_candidate(c, self.deactivated, self.active, _VoteLink.OPEN, True)
            reactivated.append(c)

            # If limit is set return the specified amount instead of all deactivated
            if limit is not None and len(reactivated) >= limit:
                break

        return reactivated


class STVStatus:
    """ Result of each counting round """
    # Yield Levels. Used to see level of details
    INITIAL = -1
    BEGIN = 0
    END = 1
    ROUND = 2
    SUBROUND = 3
    LOOP = 4

    def __init__(self, yieldlevel=None):
        self.yieldlevel = yieldlevel  # Tells where in the algorithm the yield happened
        self.winner = None
        self.loser = None
        self.excluded_by_group = []
        self.reactivated = None


class _Group:
    def __init__(self, name, seats):
        self.name = name
        self.seats = seats
        self.seatswon = 0

    @property
    def is_full(self):
        return self.seatswon >= self.seats


class _Candidate:
    def __init__(self, code, name, group):
        self.code = code
        self.name = name
        self.group = group
        self.votelinks = []

        # Running Attributes
        self._votes = 0
        self.dorefreshvotes = True
        self.wonatquota = 0
        self.doreduction = False

    def __repr__(self):
        return 'Candidate({}, {})'.format(self.code, self.name)

    @property
    def votes(self):
        """ Cache result to improve performance """
        if self.dorefreshvotes:
            self.dorefreshvotes = False
            self._votes = 0
            for vl in self.votelinks:
                self._votes += vl.weight
        return self._votes

    def reduce(self):
        """
        Now that the candidate has surplus votes,
        see who from the partial supporters can become full supporters,
        then reduce the weight taken from all full supporters
        """
        self.doreduction = False

        # Create ordered list of partial votelinks from lowest to highest and list of full votelinks
        partialvls = []
        fullvls = []
        for vl in self.votelinks:
            if vl.status == vl.FULL:
                fullvls.append(vl)
            elif vl.status == vl.PARTIAL:
                partialvls.append(vl)
        partialvls.sort(key=lambda x: x.weight)

        totalsupporters = len(fullvls) + len(partialvls)
        partialcount = 0
        partialweight = 0
        for vl in partialvls + fullvls:
            fullsupportweight = (self.wonatquota - partialweight) / (totalsupporters - partialcount)
            # As loop progress, the fullsupportweight will increase than stabilize when supporters are able to
            # become full supporters
            if vl.status == vl.PARTIAL:
                if vl.weight < fullsupportweight:
                    # Phase 1. partial supporters who cannot give full support
                    partialcount += 1
                    partialweight += vl.weight
                    # This will increase  the fullsupportweight on next iteration
                else:
                    # Phase 2. partial supporter can now fully support candidate
                    vl.status = vl.FULL

            # Reduce full support weight for old and new full supporters
            if vl.status == vl.FULL:
                vl.weight = fullsupportweight
                self.dorefreshvotes = True  # Have to recalculate weight
                vl.voter.doallocate = True


class _Voter:
    def __init__(self, uid):
        self.uid = uid
        self.votelinks = []  # Links to candidate in order of preference
        self.waste = 0
        self.doallocate = True

    def __repr__(self):
        return 'Voter({})'.format(self.uid)

    def allocate_votes(self):
        self.doallocate = False

        # Collect all fixed weight and reset unfixed weight
        total = 1
        for vl in self.votelinks:
            if vl.status in [vl.PARTIAL, vl.FULL]:
                total -= vl.weight
            elif vl.weight > 0:
                vl.weight = 0
                vl.candidate.dorefreshvotes = True

        # Spread unfixed weight to first Open or Partial votelinks
        if total > 0.005:  # Due to floating point inaccuracy dont compare to 0
            for vl in self.votelinks:
                if vl.status in [vl.OPEN, vl.PARTIAL]:
                    vl.weight += total
                    total = 0
                    vl.candidate.dorefreshvotes = True
                    # New available support to previous winner
                    if vl.candidate.wonatquota > 0:
                        vl.status = vl.PARTIAL
                        vl.candidate.doreduction = True
                    break

        self.waste = total


class _VoteLink:
    EXCLUDED = -2  # Permanent Lost support
    DEACTIVATED = -1  # Temporary Lost support
    OPEN = 0  # Open support
    PARTIAL = 1  # Partial support
    FULL = 2  # Full support

    def __init__(self, voter, candidate):
        self.voter = voter
        self.candidate = candidate
        self.weight = 0

        self.voter.votelinks.append(self)
        self.candidate.votelinks.append(self)

        self.status = self.OPEN

    def __repr__(self):
        return 'VoteLink({}, {}, {})'.format(self.voter, self.candidate, self.status)
