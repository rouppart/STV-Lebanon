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
          '"r" to view the count by round\n'
          '"g" to use group quotas\n'
          '"n" for no reactivation')
    viewmode = input('Type any number of options: ')
    viewbyround = 'r' in viewmode
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

    # Count
    stv.prepare_for_count()

    print('\nArea:', stv.areaname, '  Seats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
          '  Quota:', formatvote(stv.quota), '\n')
    
    print('Initial List:')
    print_lists(stv, viewvoter)
    print('---------------------------\n')

    if viewbyround:
        input('Press any key to continue to start')
        print()
    try:
        for laststatus in stv:
            if viewbyround:
                print('Round:', stv.rounds)
                print('Subround:', stv.subrounds) if stv.reactivationmode else None
                print()

                if laststatus.result != laststatus.REACTIVATION:
                    resulttranslate = {laststatus.WIN: 'Won', laststatus.LOSS: 'Lost'}
                    print(laststatus.candidate.name, 'has', resulttranslate[laststatus.result], '\n')
                else:
                    print('Reactivation Round\n')

                if laststatus.reactivated:
                    print('The following candidates have been returned to the active list:')
                    for c in laststatus.reactivated:
                        print(c.name)
                    print()

                if laststatus.deleted_by_group:
                    print('The following candidates lost because their group quota has been met:')
                    for c in laststatus.deleted_by_group:
                        print(c.name)
                    print()

                print_lists(stv, viewvoter)
                print('---------------------------\n')
                input('Press any key to continue to next round...')
                print()
    except Exception as e:
        print('Error: ' + str(e))
    else:
        print('Votes finished\n')
        print_lists(stv, viewvoter)
        for group in stv.groups.values():
            print(group.name, group.seatswon, '/', group.seats)
        print('Waste Percentage:', formatratio(stv.totalwaste / len(stv.voters)))

    input('\nPress any key to exit...')


if __name__ == '__main__':
    main()
