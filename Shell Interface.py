from stv import STV


def main():
    print('Options:\n'
          '"r" to view the count by round or "l" by loop\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewmode = input('Type any number of options: ')
    viewloop = 'l' in viewmode
    viewbyround = 'r' in viewmode or viewloop
    viewvoter = input('Please enter your unique id to see the progression of your vote: ')

    stv = setup('g' in viewmode, 'n' not in viewmode)

    print('\nArea:', stv.areaname, '  Seats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
          '  Quota:', formatvote(stv.quota), '\n')
    
    for status in stv.start():
        if viewloop or (viewbyround and status.loopcount == 0) or status.initial:
            print('Round: {}.{}'.format(stv.rounds, stv.subrounds))

            if status.winner is not None:
                print('Win:', status.winner.name)
            elif status.loser is not None:
                print('Loss:', status.loser.name)
            elif status.reactivated:
                print('Reactivation Round')
            elif status.allocationcount > 0:
                print('Loop:', status.loopcount, 'Allocations:', status.allocationcount)
            elif status.reducecount > 0:
                print('Loop:', status.loopcount, 'Reductions:', status.reducecount)
            else:
                print('Initial Round')
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
            input('Press any key to continue to next round...')
            print()

    print('Votes finished\n')
    print_lists(stv, viewvoter)
    for group in stv.groups.values():
        print(group.name, group.seatswon, '/', group.seats)
    print('Waste Percentage:', formatratio(stv.totalwaste / len(stv.voters)))

    input('\nPress any key to exit...')


def setup(usegroups, reactivationmode):
    """ Import from local files, create and return STV instance """

    # Fill Objects
    with open('Area.csv', 'r') as f:
        areaname, groups = f.readline().strip().split(',')
        stv = STV(areaname, usegroups, reactivationmode)
        for group in groups.split(';'):
            groupname, seats = group.split(':')
            stv.add_group(groupname, int(seats))

    with open('Candidates.csv', 'r') as f:
        for line in f:
            uid, name, groupname = line.strip().split(',')
            stv.add_candidate(uid, name, groupname)

    with open('Votes.csv', 'r') as f:
        for line in f:
            uid, votes = line.strip().split(',')
            stv.add_voter(uid, votes)

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
            statusdescription = {vl.EXCLUDED: 'Excluded', vl.DEACTIVATED: 'Deactivated', vl.OPEN: 'Open',
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
    main()
