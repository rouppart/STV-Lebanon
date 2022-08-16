import argparse
import sys
from importlib import resources
from .stv import STV, STVStatus, STVSetupException


def main() -> None:
    parser = argparse.ArgumentParser(prog='stvlebanon', description="Command-Line interface to STV Lebanon")
    parser.add_argument('-g', dest='group', action='store_true', help="Use group quotas")
    parser.add_argument('-n', dest='reactivation', action='store_false', help="No reactivation")
    parser.add_argument('-l', dest='level', type=int, default=0, help="Level of monitoring. 1=Round 2=Subround 3=Loop")
    parser.add_argument('-w', dest='watch', default="", metavar="VOTERID", help="View Voter Situation at every round")
    parser.add_argument('-s', dest='sample', action='store_true', help="Load sample data")
    parser_result = parser.parse_args()

    use_groups: bool = parser_result.group
    reactivation: bool = parser_result.reactivation
    viewlevel: int = min(max(parser_result.level, 0), 3) + 1  # So it matches STVStatus levels
    viewvoter: str = parser_result.watch
    load_samples: bool = parser_result.sample

    print("Use -h to see running options\n")
    print("Groups:", use_groups)
    print("Reactivation:", reactivation)
    print("View Level:", {STVStatus.END: "Result", STVStatus.ROUND: "Round", STVStatus.SUBROUND: "Subround",
                          STVStatus.LOOP: "Loop"}[viewlevel])
    print("Watching:", viewvoter or "<None>")

    stv = setup(use_groups, reactivation, load_samples)

    if viewvoter and viewvoter not in stv.voters:
        print(f"\nWarning: Could not find Voter with ID: {viewvoter}")
        viewvoter = ""

    print(f"\nSeats: {stv.totalseats}\nTotal Votes: {len(stv.voters)}  Quota: {formatvote(stv.quota)}\n")
    
    for status in stv.start():
        if status.yieldlevel <= viewlevel and status.yieldlevel != status.BEGIN:
            if status.yieldlevel == status.INITIAL:
                print("Initial Round\n")
            elif viewlevel >= status.ROUND:
                print("Round:", '.'.join(map(str, [stv.rounds, stv.subrounds, stv.loopcount][:viewlevel-status.END])))

                if status.winner is not None:
                    print("Win:", status.winner.name)
                elif status.loser is not None:
                    print("Loss:", status.loser.name)
                elif stv.allocationcount > 0:
                    print("Allocations:", stv.allocationcount)
                elif stv.reductioncount > 0:
                    print("Reductions:", stv.reductioncount)
                print()

            if status.excluded_by_group:
                print("The following candidates have been excluded because their group quota has been met:")
                for c in status.excluded_by_group:
                    print(c.name)
                print()

            if status.reactivated:
                print("The following candidates have been returned to the active list:")
                for c in status.reactivated:
                    print(c.name)
                print()

            print_lists(stv, viewvoter)

            print("---------------------------\n")
            if not status.yieldlevel == status.END:
                try:
                    input("Press any key to continue to next round...")
                except KeyboardInterrupt:
                    print("\n\nExiting program...\n")
                    sys.exit()
                print()
            else:
                print("Votes Finished")
                for group in stv.groups.values():
                    print(group.name, group.seatswon, '/', group.seats)
                print("Waste Percentage:", formatratio(stv.totalwaste / len(stv.voters)))


def setup(usegroups: bool, reactivationmode: bool, load_samples: bool = False) -> STV:
    """ Import from local files, create and return STV instance """

    def local_or_sample(filename: str) -> str:
        if load_samples:
            with resources.path('stv_lebanon.samples', filename) as new_filename:
                filename = new_filename
            print("Using sample:", filename)
        return filename

    stv = STV(usegroups, reactivationmode)
    try:
        # Fill Objects
        with open(local_or_sample('Groups.csv'), 'r') as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()  # Skip empty lines
                try:
                    groupname, seats = line.split(',')
                    stv.add_group(groupname, int(seats))
                except ValueError:
                    raise STVSetupException(f"Could not decode group at line {i}")

        with open(local_or_sample('Candidates.csv'), 'r') as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        uid, name, groupname = line.split(',')
                        stv.add_candidate(uid, name, groupname)
                    except ValueError:
                        raise STVSetupException(f"Could not decode candidate at line {i}")

        with open(local_or_sample('Votes.csv'), 'r') as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        uid, *ballot = line.split(',')
                        stv.add_voter(uid, ballot)
                    except ValueError:
                        print("Setup Warning: Could not decode voter at line", i)

    except (FileNotFoundError, STVSetupException) as e:
        if isinstance(e, FileNotFoundError):
            print(f"\nError: Missing file '{e.filename}'. Please make sure you have the following 3 files in your "
                  "current directory: 'Groups.csv', 'Candidates.csv', 'Votes.csv'")
        else:
            print("\nSetup Error:", e)
        sys.exit(1)
    return stv


def print_lists(stv: STV, voterid: str) -> None:
    """ Prints candidate list and optionally, voter's ballot """
    statcands = [('W', stv.winners), ('A', stv.active), ('D', stv.deactivated[::-1]), ('E', stv.excluded[::-1])]

    for status, candidates in statcands:
        for candidate in candidates:
            print(formatname(candidate.name) + status, formatvote(candidate.votes))
    print('------------')
    print(formatname('Total Waste') + ' ', formatvote(stv.totalwaste))

    if voterid:  # If not empty string. Already checked after setup
        voter = stv.voters[voterid]
        print('\n' + voter.uid, 'list:')
        for vl in voter.votelinks:
            statusdescription = {vl.EXCLUDED: 'Excluded', vl.DEACTIVATED: 'Deactivated', vl.ACTIVE: 'Active',
                                 vl.PARTIAL: 'Partial', vl.FULL: 'Full'}[vl.status]
            print(formatname(vl.candidate.name), formatratio(vl.weight), ' ' + statusdescription)
        print(formatname('Waste'), formatratio(voter.waste))


def formatname(v):
    return '{:<20}'.format(v)


def formatvote(v):
    return '{:,.2f}'.format(v)


def formatratio(v):
    return '{:>5.0%}'.format(v)
