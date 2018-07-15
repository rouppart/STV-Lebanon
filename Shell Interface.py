from STV import STV


# Setup
print('Options:\n'
      '"r" to view the count by round\n'
      '"g" to use group quotas\n'
      '"n" for no reactivation')
viewmode = input('Type any number of options: ')
viewbyround = 'r' in viewmode
viewvoter = input('Please enter your unique id to see the progression of your vote: ')


# Fill Objects
f = open('Area.csv', 'r')
areaname, groups = f.readline().strip().split(',')
stv = STV(areaname, 'g' in viewmode, 'n' not in viewmode)
for group in groups.split(';'):
    groupname, seats = group.split(':')
    stv.add_group(groupname, int(seats))
f.close()

f = open('Candidates.csv', 'r')
for l in f:
    uid, name, groupname = l.strip().split(',')
    stv.add_candidate(uid, name, groupname)
f.close()

f = open('Votes.csv', 'r')
for l in f:
    uid, votes = l.strip().split(',')
    stv.add_voter(uid, votes)
f.close()

# Count
stv.prepare_for_count()

nameformat = '{:<20}'
voteformat = '{:.3g}'
ratioformat = '{:>5.0%}'

print('\nArea:', stv.areaname, '  Seats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
      '  Quota:', voteformat.format(stv.quota), '\n')


def print_status():
    statcands = [('W', stv.winners), ('A', stv.active), ('D', stv.deactivated[::-1]), ('E', stv.excluded[::-1])]

    for status, candidates in statcands:
        for candidate in candidates:
            print(nameformat.format(candidate.name)+status, voteformat.format(candidate.votes))
    print('------------')
    print(nameformat.format('Total Waste')+' ', voteformat.format(stv.totalwaste))

    if viewvoter in stv.voters.keys():
        vlstatus = {-2:'Excluded', -1: 'Deactivated', 0: 'Open', 1: 'Partial', 2: 'Full'}
        print('\n'+stv.voters[viewvoter].uid, 'list:')
        for vl in stv.voters[viewvoter].votelinks:
            print(nameformat.format(vl.candidate.name), ratioformat.format(vl.weight), '\t'+vlstatus[vl.status])
        print(nameformat.format('Waste'), ratioformat.format(stv.voters[viewvoter].waste))
    print()


print('Initial List:')
print_status()
print('---------------------------\n')
if viewbyround:
    input('Press any key to continue to start')

try:
    for laststatus in stv:
        if viewbyround:
            print('Round:', stv.rounds)
            print('Subround:', stv.subrounds) if stv.reactivation else None
            print()

            if laststatus.result != 0:
                resulttranslate = {1: 'Won', -1: 'Lost'}
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

            print_status()
            print('---------------------------\n')
            input('Press any key to continue to next round...')
except Exception as e:
    print('Error: ' + str(e))
else:
    print('Votes finished\n')
    print_status()
    for group in stv.groups.values():
        print(group.name, group.seatswon, '/', group.seats)

input('Press any key to exit...')
