from STV import STV


def formatname(v):
    return '{:<20}'.format(v)


def formatvote(v):
    return '{:,.2f}'.format(v)


def formatratio(v):
    return '{:>5.0%}'.format(v)


def print_lists(stv, voterid):
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


def main():
    # Setup
    print('Options:\n'
          '"r" to view the count by round or "l" by loop\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewmode = input('Type any number of options: ')
    viewloop = 'l' in viewmode
    viewbyround = 'r' in viewmode or viewloop
    viewvoter = input('Please enter your unique id to see the progression of your vote: ')

    # Fill Objects
    with open('Area.csv', 'r') as f:
        areaname, groups = f.readline().strip().split(',')
        stv = STV(areaname, 'g' in viewmode, 'n' not in viewmode)
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

    print('\nArea:', stv.areaname, '  Seats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
          '  Quota:', formatvote(stv.quota), '\n')
    
    for status in stv.start():
        if viewloop or (viewbyround and status.result > 0) or status.result == status.INITIAL:
            print('Round:', stv.rounds, end='')
            print('.{}'.format(stv.subrounds) if stv.reactivationmode else '')

            if status.result in (status.LOSS, status.WIN):
                resulttranslate = {status.WIN: 'Win', status.LOSS: 'Loss'}
                print(resulttranslate[status.result]+':', status.candidate.name)
            elif status.result == status.REACTIVATION:
                print('Reactivation Round')
            elif status.result == status.INITIAL:
                print('Initial Round')
            elif status.result == status.ALLOCATION:
                print('Allocation Loops:', status.allocationcount)
            elif status.result == status.REDUCE:
                print('Reduce Loops:', status.reducecount)
            print()

            if status.reactivated:
                print('The following candidates have been returned to the active list:')
                for c in status.reactivated:
                    print(c.name)
                print()

            if status.deleted_by_group:
                print('The following candidates lost because their group quota has been met:')
                for c in status.deleted_by_group:
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


if __name__ == '__main__':
    main()
