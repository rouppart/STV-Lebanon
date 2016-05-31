## Define Objects

# Area
areaname = seats = quota = None;
totalvotes = 0;
totalwaste = 0;
winners = losers = 0;

ol = [];


def add(args):
    global areaname, seats;
    s = args.split(',');
    areaname = s[0];
    seats = int(s[1]);


# Candidate
candidates = dict();
class Candidate:
    def __init__(self, codep, namep):
        namep = namep.strip();
        
        self.code = codep;
        self.name = namep;
        
        self.status = 'A'; #A = active, W = winner, L = loser
        
        self.votelinks = [];
        self.votes = 0;

    def pk(self):
        return self.code;

    def add(args):
        s = args.split(',');
        o = Candidate(s[0],s[1]);
        candidates[o.pk()] = o;

    def addVoteLink(self, votelinkp):
        self.votelinks.append(votelinkp);

    def updateVotes(self):
        self.votes = 0;
        for l in self.votelinks:
            self.votes += l.weight;

    def setWinner(self, recycleratio):
        global winners;
        winners += 1;
        self.status = 'W';
        for l in self.votelinks:
            l.transferToNextCandidate(recycleratio);
        self.updateVotes();

    def setLost(self):
        global losers;
        losers += 1;
        self.status = 'L';
        for l in self.votelinks:
            l.transferToNextCandidate(1);
        self.updateVotes();
            

# Voter
voters = dict();
class Voter:
    def __init__(self, uidp, votep):
        votep = votep.strip();
        
        self.uid = uidp;
        self.candlist = [];
        for c in votep:
            self.candlist.append(VoteLink(self, candidates[c]));
            try:
                self.candlist[0].weight = 1;
            except:
                pass;
        self.waste = 0;

    def pk(self):
        return self.uid;

    def add(args):
        s = args.split(',');
        o = Voter(s[0], s[1]);
        voters[o.pk()] = o;

#VoteLink
class VoteLink:
    def __init__(self, voterp, candidatep):
        self.voter = voterp;
        self.candidate = candidatep;
        self.candidate.addVoteLink(self);
        self.weight = 0;

    def transferToNextCandidate(self, recycleratio):
        i = self.voter.candlist.index(self)+1;
        while i < len(self.voter.candlist):
            nextvl = self.voter.candlist[i];
            if nextvl.candidate.status == 'A':
                nextvl.weight += self.weight * recycleratio;
                break;
            i += 1;
        else: #waste
            self.voter.waste += self.weight * recycleratio;
            global totalwaste;
            totalwaste += self.weight * recycleratio;
        
        self.weight -= self.weight * recycleratio;
        

#Sort Candidates by vote
def sortByVote():
    for c in ol[winners:len(ol)-losers]: #make that more efficient later
        c.updateVotes();

    start = winners;
    end = len(ol)-losers;
        
    for i in range(winners, end-1):
        imax = i;
        for j in range(i, end):
            if ol[imax].votes < ol[j].votes:
                temp = ol[imax];
                ol[imax] = ol[j];
                ol[j] = temp;

## Fill Objects
        
f = open('Area.csv','r');
add(f.readline());
f.close();

f = open('Candidates.csv', 'r');
for l in f:
    Candidate.add(l);
f.close();

f = open('Votes.csv', 'r');
for l in f:
    Voter.add(l);
f.close();


viewvoter = input('Please enter your unique id to see the progression of your vote: ');
viewmode = input('Pleater enter "r" to view the count by round or "q" to jump to final result: ');

## Count
nameformat = '{:<20}';
statusformat = '{:<3}';
voteformat = '{:.2g}';
ratioformat = '{:.0%}';

# Initialisation
for k,v in voters.items():
    totalvotes += 1;

for k, c in candidates.items():
    ol.append(c);

quota = totalvotes / seats;
print('\nArea:', areaname, '  Seats:', seats, '\nTotal Votes:',totalvotes, '  Quota:', voteformat.format(quota), '\n');


#Start loop
rounds = 0;

while losers < len(candidates) - seats:
    sortByVote();

    if viewmode != 'q':
        for c in ol: #see candidates
            print(nameformat.format(c.name), statusformat.format(c.status), voteformat.format(c.votes) if c.status != 'L' else '');
        print();

        if viewvoter in voters.keys():
            print('Your list looks like this now:');
            for l in voters[viewvoter].candlist:
                print(nameformat.format(l.candidate.name),statusformat.format(l.candidate.status), ratioformat.format(l.weight));
            print('Waste:', ratioformat.format(voters[viewvoter].waste),'\n');

    roundwinner = ol[winners];
    if roundwinner.votes >= quota:
        surplus = roundwinner.votes - quota;
        recycleratio = surplus / roundwinner.votes;
        roundwinner.votes = quota;
        print(roundwinner.name, 'has', voteformat.format(surplus), 'extra votes so', ratioformat.format(recycleratio), ' of his votes will be recycled') if viewmode != 'q' else None;
        roundwinner.setWinner(recycleratio);

    else:
        roundloser = ol[-1-losers];
        surplus = roundloser.votes;
        print(roundloser.name, 'has lost, so his', voteformat.format(surplus), 'votes will be recycled.') if viewmode != 'q' else None;
        roundloser.setLost();
        
    rounds += 1;
    print('End of round:',rounds,'\n') if viewmode != 'q' else None;

    if viewmode == 'r':
        input('Press any key to continue...');

print('\nFinal list is:\n');
sortByVote();
for c in ol[:-losers]:
    print(nameformat.format(c.name),statusformat.format(c.status), voteformat.format(c.votes));
print('Total Waste:', voteformat.format(totalwaste), ' ('+ratioformat.format(totalwaste/totalvotes)+')');

if viewvoter in voters.keys():
    print('\nYour results:\n');
    for l in voters[viewvoter].candlist:
        print(nameformat.format(l.candidate.name),statusformat.format(l.candidate.status), ratioformat.format(l.weight));
    print('Waste:', ratioformat.format(voters[viewvoter].waste));
