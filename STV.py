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
        self.quota = 0
        self.totalseats = 0
        self.totalwaste = 0
        self.rounds = 0
        self.issubround = False
        self.subrounds = 0
        self.isprepared = False

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
        self.candidates[code] = _Candidate(code, name, self.groups[groupname])

    def add_voter(self, uid, candlist):
        if uid in self.voters:
            raise Exception('Voter {} was already added'.format(uid))
        self.voters[uid] = newvoter = _Voter(uid)
        for ccode in candlist:
            try:
                _VoteLink(newvoter, self.candidates[ccode])
            except KeyError:
                raise Exception('Voter {} voted used an invalid Candidate Code ({})'.format(uid, ccode))

    def prepare_for_count(self):
        """ Used once to prepare for counting """
        for c in self.candidates.values():
            self.active.append(c)  # Put all Candidates in the active list

        self.quota = len(self.voters) / self.totalseats
        # Initial allocation of votes to top candidate on ballot
        for v in self.voters.values():
            v.allocate_votes()
        self._sort_by_vote()
        self.isprepared = True

    def _sort_by_vote(self):
        """ Recalculates all votes and sorts the active list """
        for c in self.candidates.values():
            c.sum_votes()
        self.totalwaste = 0
        for v in self.voters.values():
            self.totalwaste += v.waste

        self.active.sort(key=lambda candidate: candidate.votes, reverse=True)

    def __iter__(self):
        """ Return self to loop through rounds """
        if not self.isprepared:
            raise Exception('Not prepared. use STV.prepare_for_count() before iterating')
        return self

    def __next__(self):
        """ Advance to next Round. Either there will be a win, a loss or reactivation. Then do heavy counting """
        # Manage Round counting
        if self.issubround:
            self.subrounds += 1
        else:
            self.rounds += 1
            self.subrounds = 1
        self.issubround = self.reactivationmode

        status = STVStatus()

        topcandidate = self.active[0]
        missingseats = self.totalseats - len(self.winners) - len(self.active)
        if missingseats > 0:
            # Unexpected Reactivation Round
            # If there are not enough active candidates, reactivate some.
            # This can happen if reactivationmode is off and group quotas exclude too many candidates
            status.result = status.REACTIVATION
            status.reactivated = self._reactivate(missingseats)
            if len(status.reactivated) != missingseats:
                raise Exception('Reactivation failed in Round {}.{}'.format(self.rounds, self.subrounds))

        elif topcandidate.votes >= self.quota or len(self.winners) + len(self.active) == self.totalseats:
            # Win. Either Quota is reached, or cannot lose a candidate because active list becomes too small
            topcandidate.wonatquota = self.quota if topcandidate.votes > self.quota else topcandidate.votes
            # Register at which vote amount the winner won in case he won below the quota
            self._process_candidate(topcandidate, self.active, self.winners, _VoteLink.PARTIAL)
            # Status set to PARTIAL and let Candidate's Reduce function decide if FULL

            status.candidate = topcandidate  # Update status
            status.result = status.WIN

            wgroup = topcandidate.group  # Update candidate's group
            wgroup.seatswon += 1

            # Process group constraints if groupquota is on
            if self.usegroups and wgroup.is_full:
                for c in self.active + self.deactivated:
                    if c.group == wgroup:
                        fromlist = self.active if c in self.active else self.deactivated
                        self._process_candidate(c, fromlist, self.excluded, _VoteLink.EXCLUDED)
                        status.deleted_by_group.append(c)

            # Finish
            if len(self.winners) == self.totalseats:
                status.finished = True
                raise StopIteration
            elif self.reactivationmode:  # If win and not finished and reactivationmode is on
                status.reactivated = self._reactivate()
            self.issubround = False

        else:  # Lose
            # Remove last active candidate
            roundloser = self.active[-1]
            self._process_candidate(roundloser, self.active, self.deactivated, _VoteLink.DEACTIVATED)

            status.candidate = roundloser
            status.result = status.LOSS

        # General Redistribution of votes
        repeatreduce = True
        while repeatreduce:  # Main Loop
            repeatreduce = False
            for voter in self.voters.values():
                if voter.doallocate:
                    voter.allocate_votes()  # This can give surplus votes to candidates
            for winner in self.winners[::-1]:
                if winner.doreduce:  # If candidate received surplus votes allocate_votes above
                    repeatreduce = True  # Repeat Main loop
                    winner.reduce()  # Return surplus votes to voters and trigger doallocate

        self._sort_by_vote()
        return status

    @staticmethod
    def _process_candidate(candidate, fromlist, tolist, new_vl_status):
        """ Transfer candidate and update its votelinks """
        fromlist.remove(candidate)
        tolist.append(candidate)

        for vl in candidate.votelinks:
            vl.status = new_vl_status
            vl.voter.doallocate = True

    def _reactivate(self, limit=None):
        """ Reactivates deactivated Candidates """
        reactivated = []
        for c in self.deactivated[::-1]:
            self._process_candidate(c, self.deactivated, self.active, _VoteLink.OPEN)
            reactivated.append(c)

            # If limit is set return the specified amount instead of all deactivated
            if limit is not None and len(reactivated) >= limit:
                break

        return reactivated


class STVStatus:
    """ Result of each counting round """
    WIN = 1
    REACTIVATION = 0
    LOSS = -1

    def __init__(self):
        self.candidate = None
        self.result = None
        self.deleted_by_group = []
        self.reactivated = None
        self.finished = False


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
        self.votes = 0
        self.wonatquota = 0
        self.doreduce = False

    def __repr__(self):
        return 'Candidate({}, {})'.format(self.code, self.name)

    def sum_votes(self):
        self.votes = 0
        for vl in self.votelinks:
            self.votes += vl.weight

    def reduce(self):
        """
        Now that the candidate has surplus votes,
        see who from the partial supporters can become full supporters,
        then reduce the weight taken from all full supporters
        """
        self.doreduce = False

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
                vl.voter.doallocate = True


class _Voter:
    def __init__(self, uid):
        self.uid = uid
        self.votelinks = []  # Links to candidate in order of preference
        self.waste = 0
        self.doallocate = False

    def __repr__(self):
        return 'Voter({})'.format(self.uid)

    def allocate_votes(self):
        self.doallocate = False

        # Collect all fixed weight and reset unfixed weight
        total = 1
        for vl in self.votelinks:
            if vl.status in [vl.PARTIAL, vl.FULL]:
                total -= vl.weight
            else:
                vl.weight = 0

        # Spread unfixed weight to first Open or Partial votelinks
        if total > 0:
            for vl in self.votelinks:
                if vl.status in [vl.OPEN, vl.PARTIAL]:
                    vl.weight += total
                    total = 0
                    # New available support to previous winner
                    if vl.candidate.wonatquota > 0:
                        vl.status = vl.PARTIAL
                        vl.candidate.doreduce = True
                    break

        self.waste = total


class _VoteLink:
    EXCLUDED = -2  # Permanent Lost support
    DEACTIVATED = -1  # Temporary Lost support
    OPEN = 0  # Open support
    PARTIAL = 1  # Partial support
    FULL = 2  # Full support

    statusdescriptions = {EXCLUDED: 'Excluded', DEACTIVATED: 'Deactivated',
                          OPEN: 'Open', PARTIAL: 'Partial', FULL: 'Full'}

    def __init__(self, voter, candidate):
        self.voter = voter
        self.candidate = candidate
        self.weight = 0

        self.voter.votelinks.append(self)
        self.candidate.votelinks.append(self)

        self.status = self.OPEN

    def __repr__(self):
        return 'VoteLink({}, {}, {})'.format(self.voter, self.candidate, self.statustext)

    @property
    def statustext(self):
        return self.statusdescriptions[self.status]
