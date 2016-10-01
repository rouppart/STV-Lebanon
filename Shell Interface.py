from STV import STV

# Fill Objects

f = open('Area.csv', 'r')
areaname, groups = f.readline().strip().split(',')
stv = STV(areaname, True)
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
voteformat = '{:.2g}'
ratioformat = '{:.0%}'

viewvoter = input('Please enter your unique id to see the progression of your vote: ')
viewmode = input('Pleater enter "r" to view the count by round: ')

print('\nArea:', stv.areaname, '  Seats:', stv.totalseats, '\nTotal Votes:', len(stv.voters),
      '  Quota:', voteformat.format(stv.quota), '\n')


def print_status():
    statcands = [('W', stv.winners), ('A', stv.active), ('L', stv.losers[::-1])]

    for status, candidates in statcands:
        for candidate in candidates:
            print(nameformat.format(candidate.name)+status, voteformat.format(candidate.votes))
    print('------------')
    print(nameformat.format('Total Waste')+' ', voteformat.format(stv.totalwaste))

    if viewvoter in stv.voters.keys():
        vlstatus = {-1: 'Lost', 0: 'Open', 1: 'Partial', 2: 'Full'}
        print('\n'+stv.voters[viewvoter].uid, 'list:')
        for vl in stv.voters[viewvoter].votelinks:
            print(nameformat.format(vl.candidate.name), ratioformat.format(vl.weight), '\t'+vlstatus[vl.status])
        print(nameformat.format('Waste'), ratioformat.format(stv.voters[viewvoter].waste))
    print()

print('Initial List:')
print_status()
print('---------------------------\n')

laststatus = stv.next_round()
while laststatus.continuepossible:
    if viewmode == 'r':
        input('Press any key to continue to next round...')
    print('Round:', stv.rounds, '\n')

    resulttranslate = {1: 'Won', 0: 'been returned to the active list.', -1: 'Lost'}
    print(laststatus.candidate.name, 'has', resulttranslate[laststatus.result], '\n')

    if laststatus.deleted_by_group:
        print('The following candidates lost because their group quota has been met:')
        for c in laststatus.deleted_by_group:
            print(c.name, )
        print()
    print_status()
    print('---------------------------\n')
    laststatus = stv.next_round()


print('Votes finished' if laststatus.finished else laststatus.message)

for group in stv.groups.values():
    print(group.name, group.seatswon, '/', group.seats)

input('Press any key to exit...')
