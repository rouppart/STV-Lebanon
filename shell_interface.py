from stv import STV, STVStatus


def main():
    print('Options:\n'
          '"r" to view the count by round, "s" by subround or "l" by loop\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewoptions = input('Type any number of options: ')
    if 'l' in viewoptions:
        viewlevel = STVStatus.LOOP
    elif 's' in viewoptions:
        viewlevel = STVStatus.SUBROUND
    elif 'r' in viewoptions:
        viewlevel = STVStatus.ROUND
    else:
        viewlevel = STVStatus.END
    viewvoter = input('Please enter your unique id to see the progression of your vote: ')

    stv = setup('g' in viewoptions, 'n' not in viewoptions)

    print('\nSeats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
          '  Quota:', formatvote(stv.quota), '\n')
    
    for status in stv.start():
        if status.yieldlevel <= viewlevel and status.yieldlevel != status.BEGIN:
            if status.yieldlevel == status.INITIAL:
                print('Initial Round\n')
            elif viewlevel >= status.ROUND:
                print('Round: ' + '.'.join(map(str, [stv.rounds, stv.subrounds, stv.loopcount][:viewlevel-status.END])))

                if status.winner is not None:
                    print('Win:', status.winner.name)
                elif status.loser is not None:
                    print('Loss:', status.loser.name)
                elif stv.allocationcount > 0:
                    print('Allocations:', stv.allocationcount)
                elif stv.reductioncount > 0:
                    print('Reductions:', stv.reductioncount)
                print()

            if status.excluded_by_group:
                print('The following candidates have been excluded because their group quota has been met:')
                for c in status.excluded_by_group:
                    print(c.name)
                print()

            if status.reactivated:
                print('The following candidates have been returned to the active list:')
                for c in status.reactivated:
                    print(c.name)
                print()

            print_lists(stv, viewvoter)

            print('---------------------------\n')
            if not status.yieldlevel == status.END:
                input('Press any key to continue to next round...')
                print()
            else:
                print('Votes Finished')
                for group in stv.groups.values():
                    print(group.name, group.seatswon, '/', group.seats)
                print('Waste Percentage:', formatratio(stv.totalwaste / len(stv.voters)))


def setup(usegroups, reactivationmode):
    """ Import from local files, create and return STV instance """

    # Fill Objects
    with open('Groups.csv', 'r') as f:
        try:
            stv = STV(usegroups, reactivationmode)
            for group in f.readline().strip().split(','):
                groupname, seats = group.split(':')
                stv.add_group(groupname, int(seats))
        except ValueError:
            raise Exception('Setup Error: Could not decode Groups')

    with open('Candidates.csv', 'r') as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if line:  # Skip empty lines
                try:
                    uid, name, groupname = line.split(',')
                    stv.add_candidate(uid, name, groupname)
                except ValueError:
                    print('Setup Warning: Could not decode candidate at line', i)

    with open('Votes.csv', 'r') as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if line:
                try:
                    uid, ballot = line.split(':')
                    stv.add_voter(uid, ballot.split(','))
                except ValueError:
                    print('Setup Warning: Could not decode voter at line', i)

    return stv


def print_lists(stv, voterid):
    """ Prints candidate list and optionally, voter's ballot """
    statcands = [('W', stv.winners), ('A', stv.active), ('D', stv.deactivated[::-1]), ('E', stv.excluded[::-1])]

    for status, candidates in statcands:
        for candidate in candidates:
            print(formatname(candidate.name) + status, formatvote(candidate.votes))
    print('------------')
    print(formatname('Total Waste') + ' ', formatvote(stv.totalwaste))

    try:
        voter = stv.voters[voterid]
        print('\n' + voter.uid, 'list:')
        for vl in voter.votelinks:
            statusdescription = {vl.EXCLUDED: 'Excluded', vl.DEACTIVATED: 'Deactivated', vl.ACTIVE: 'Active',
                                 vl.PARTIAL: 'Partial', vl.FULL: 'Full'}[vl.status]
            print(formatname(vl.candidate.name), formatratio(vl.weight), '\t' + statusdescription)
        print(formatname('Waste'), formatratio(voter.waste))
    except KeyError:
        pass


def formatname(v):
    return '{:<20}'.format(v)


def formatvote(v):
    return '{:,.2f}'.format(v)


def formatratio(v):
    return '{:>5.0%}'.format(v)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
    input('\nPress any key to exit...')
