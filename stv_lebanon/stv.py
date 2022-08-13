from typing import List, Dict, Generator, Final, Optional


class STVSetupException(Exception):
    pass


class Group:
    def __init__(self, name: str, seats: int):
        self.name = name
        self.seats = seats
        self.seatswon = 0

    @property
    def is_full(self) -> bool:
        return self.seatswon >= self.seats


class Candidate:
    def __init__(self, code: str, name: str, group: Group):
        self.code = code
        self.name = name
        self.group = group
        self.votelinks: List[VoteLink] = []

        # Running Attributes
        self._votes: float = 0
        self.dorefreshvotes = True
        self.wonatquota: float = 0
        self.doreduction = False

    def __repr__(self):
        return f"Candidate({self.code}, {self.name})"

    @property
    def votes(self) -> float:
        """ Cache result to improve performance """
        if self.dorefreshvotes:
            self.dorefreshvotes = False
            self._votes = 0
            for vl in self.votelinks:
                self._votes += vl.weight
        return self._votes

    def reduce(self) -> None:
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
            elif vl.status == vl.PARTIAL and vl.weight > 0:
                partialvls.append(vl)
        partialvls.sort(key=lambda x: x.weight)

        totalsupporters = len(fullvls) + len(partialvls)
        partialcount = 0
        partialweight: float = 0
        for vl in partialvls + fullvls:
            threshold = (self.wonatquota - partialweight) / (totalsupporters - partialcount)
            # Threshold is the weight at which a VoteLink can qualify as FULL and the weight at which FULL support
            # will be reduced.
            # As loop progresses, the threshold will increase than stabilize when supporters are able to
            # become full supporters
            if vl.status == vl.PARTIAL:
                if vl.weight < threshold:
                    # Phase 1. partial supporters who cannot give full support
                    partialcount += 1
                    partialweight += vl.weight
                    # This will increase  the threshold on next iteration
                else:
                    # Phase 2. partial supporter can now fully support candidate
                    vl.status = vl.FULL

            # Reduce full support weight for old and new full supporters
            if vl.status == vl.FULL:
                vl.weight = threshold
                self.dorefreshvotes = True  # Have to recalculate weight
                vl.voter.doallocate = True
                vl.voter.dorefreshwaste = True  # Have to recalculate waste


class Voter:
    def __init__(self, uid: str):
        self.uid = uid
        self.votelinks: List[VoteLink] = []  # Links to candidate in order of preference
        self._waste: float = 1
        self.dorefreshwaste = False  # Used to trigger recalculation of waste. Reduces computation
        self.doallocate = True

    def __repr__(self):
        return f"Voter({self.uid})"

    @property
    def waste(self) -> float:
        if self.dorefreshwaste:
            self.dorefreshwaste = False
            self._waste = 1 - sum(vl.weight for vl in self.votelinks)
        return self._waste

    def allocate_votes(self) -> None:
        self.doallocate = False

        # Collect all fixed weight and reset unfixed weight
        total = 1.0  # Total to allocate
        for vl in self.votelinks:
            if vl.status in [vl.PARTIAL, vl.FULL]:
                total -= vl.weight  # Removing fixed weight
            elif vl.weight > 0:
                vl.weight = 0
                vl.candidate.dorefreshvotes = True

        # Spread unfixed weight to first Active or Partial votelinks
        if total > 0.005:  # Due to floating point inaccuracy dont compare to 0
            for vl in self.votelinks:
                if vl.status in [vl.ACTIVE, vl.PARTIAL]:
                    vl.weight += total
                    total = 0
                    vl.candidate.dorefreshvotes = True
                    # New available support to previous winner
                    if vl.candidate.wonatquota > 0:
                        vl.candidate.doreduction = True
                    break

        self._waste = total


class VoteLink:
    EXCLUDED: Final = -2  # Permanent Lost support
    DEACTIVATED: Final = -1  # Temporary Lost support
    ACTIVE: Final = 0  # Active support
    PARTIAL: Final = 1  # Partial support
    FULL: Final = 2  # Full support

    def __init__(self, voter: Voter, candidate: Candidate):
        self.voter = voter
        self.candidate = candidate
        self.weight: float = 0

        self.voter.votelinks.append(self)
        self.candidate.votelinks.append(self)

        self.status = self.ACTIVE

    def __repr__(self):
        return f"VoteLink({self.voter}, {self.candidate}, {self.weight:.3f}, {self.status})"


class STVStatus:
    """ Result of each counting round """
    # Yield Levels. Used to see level of details
    INITIAL: Final = -1
    BEGIN: Final = 0
    END: Final = 1
    ROUND: Final = 2
    SUBROUND: Final = 3
    LOOP: Final = 4

    def __init__(self, yieldlevel: int = None):
        self.yieldlevel = yieldlevel  # Tells where in the algorithm the yield happened
        self.winner: Optional[Candidate] = None
        self.loser: Optional[Candidate] = None
        self.excluded_by_group: List[Candidate] = []
        self.reactivated: Optional[List[Candidate]] = None


class STV:
    """ Contains the whole voting system and does the counting """
    def __init__(self, usegroups: bool = False, reactivationmode: bool = False):
        # Static attributes
        self.usegroups = usegroups
        self.reactivationmode = reactivationmode

        # Input Attributes
        self.groups: Dict[str, Group] = {}
        self.candidates: Dict[str, Candidate] = {}
        self.voters: Dict[str, Voter] = {}

        # Variable Running Attributes
        self.totalseats = 0
        self.rounds = 0
        self.issubround = False
        self.subrounds = 0
        self.loopcount = 0
        self.allocationcount = 0
        self.reductioncount = 0

        self.winners: List[Candidate] = []
        self.active: List[Candidate] = []
        self.deactivated: List[Candidate] = []
        self.excluded: List[Candidate] = []

    # Setup Methods
    def add_group(self, name: str, seats: int) -> None:
        if name in self.groups:
            raise STVSetupException(f"Group {name} was already added")
        self.groups[name] = Group(name, seats)
        self.totalseats += seats

    def add_candidate(self, code: str, name: str, groupname: str) -> None:
        if code in self.candidates:
            raise STVSetupException(f"Candidate {code} was already added")
        try:
            group = self.groups[groupname]
        except KeyError:
            raise STVSetupException(f"Cannot find Group with name: {groupname}")
        self.candidates[code] = candidate = Candidate(code, name, group)
        self.active.append(candidate)  # Put all Candidates in the active list

    def add_voter(self, uid: str, candlist: List[str]) -> None:
        if not uid:
            raise STVSetupException("Cannot add Voter with empty code")
        if uid in self.voters:
            raise STVSetupException(f"Voter {uid} was already added")
        self.voters[uid] = newvoter = Voter(uid)
        addedcandidates = set()  # Used to check duplicate candidate code
        for ccode in candlist:
            try:
                if ccode not in addedcandidates:
                    VoteLink(newvoter, self.candidates[ccode])
                    addedcandidates.add(ccode)
                else:
                    print(f"Warning: Voter {uid} already specified candidate ({ccode}). Ignoring")
            except KeyError:
                print(f"Warning: Voter {uid} voted used an invalid Candidate Code ({ccode}). Ignoring")

    @property
    def quota(self) -> float:
        return len(self.voters) / self.totalseats

    @property
    def totalwaste(self) -> float:
        return float(len(self.voters)) - sum(c.votes for c in self.active + self.winners)

    def _sort_active(self) -> None:
        self.active.sort(key=lambda candidate: candidate.votes, reverse=True)

    def start(self) -> Generator:
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

            repeatmainloop = True
            while repeatmainloop:  # Main Loop
                repeatmainloop = False
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
                        repeatmainloop = True  # Repeat Main loop
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
                self._process_candidate(topcandidate, self.active, self.winners, VoteLink.PARTIAL, False)
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
                            self._process_candidate(c, fromlist, self.excluded, VoteLink.EXCLUDED, True)
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
                self._process_candidate(roundloser, self.active, self.deactivated, VoteLink.DEACTIVATED, True)
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
    def _process_candidate(candidate: Candidate,
                           fromlist: List[Candidate],
                           tolist: List[Candidate],
                           new_vl_status,
                           votersdoallocate
                           ) -> None:
        """ Transfer candidate and update its votelinks """
        fromlist.remove(candidate)
        tolist.append(candidate)

        for vl in candidate.votelinks:
            vl.status = new_vl_status
            vl.voter.doallocate = votersdoallocate

    def _reactivate(self, limit: Optional[int] = None) -> List[Candidate]:
        """ Reactivates deactivated Candidates """
        reactivated = []
        for c in self.deactivated[::-1]:
            self._process_candidate(c, self.deactivated, self.active, VoteLink.ACTIVE, True)
            reactivated.append(c)

            # If limit is set return the specified amount instead of all deactivated
            if limit is not None and len(reactivated) >= limit:
                break

        return reactivated
