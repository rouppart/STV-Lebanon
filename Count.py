## Define Objects

# Area
areas = dict();
class Area:
    def __init__(self, namep, seatsp):
        self.name = namep;
        self.seats = int(seatsp);

        self.totalvotes = 0;
        self.quota = None;

    def pk(self):
        return self.name;

    def add(args):
        s = args.split(',');
        o = Area(s[0], s[1]);
        areas[o.pk()] = o;

# Candidate
candidates = dict();
class Candidate:
    def __init__(self, areap, codep, namep):
        namep = namep.strip();
        
        self.code = codep;
        self.name = namep;
        self.area = areas[areap];

        self.votes = 0;

    def pk(self):
        return self.code;

    def add(args):
        s = args.split(',');
        o = Candidate(s[0],s[1],s[2]);
        candidates[o.pk()] = o;

# Vote
votes = dict();
class Vote:
    def __init__(self, uidp, areap, votep):
        votep = votep.strip();
        
        self.uid = uidp;
        self.area = areas[areap];
        self.vote = [];
        for c in votep:
            self.vote.append(candidates[c]);

    def pk(self):
        return self.uid;

    def add(args):
        s = args.split(',');
        o = Vote(s[0], s[1], s[2]);
        votes[o.pk()] = o;
        

#Sort Candidates by vote
def sortByVote

## Fill Objects
        
f = open('Areas.csv','r');
for l in f:
    Area.add(l);
f.close();

f = open('Candidates.csv', 'r');
for l in f:
    Candidate.add(l);
f.close();

f = open('Votes.csv', 'r');
for l in f:
    Vote.add(l);
f.close();


## Count

# Initialisation
for k,v in votes.items():
    v.area.totalvotes += 1;

    #Check candidate's area matches voter's
    voterarea = v.area;
    deletec = [];
    for c in v.vote:
        if c.area != voterarea:
            deletec.append(c);
        
    for c in deletec:
        v.vote.remove(c);
        print('Warning: candidate '+ c.name +' not in '+ v.uid +'\'s area');
        
for k,a in areas.items():
    a.quota = a.totalvotes / a.seats;
    print(a.name, '\nTotal Votes:',a.totalvotes, 'Quota:', a.quota, '\n');

#First round

for k, v in votes.items():
    v.vote[0].votes += 1;

for k, c in candidates.items():
    print('{:<20}'.format(c.name), c.votes);


