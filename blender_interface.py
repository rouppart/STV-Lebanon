from collections import namedtuple
from math import sqrt, ceil
from stv_progress import STVProgress


Location = namedtuple('Location', ['x', 'y', 'z'])


def add_z_location(loc, z):
    return Location(loc.x, loc.y, loc.z + z)


def get_last_frame(adata, maxf):
    if maxf is None:
        return max(adata.keys())
    else:
        return max(k for k in adata.keys() if k <= maxf)


class BucketG:
    def __init__(self, candidatecode, width, heightratio, votefillheightratio, border):
        self.candidatecode = candidatecode
        self.width = width
        self.heightratio = heightratio
        self.votefillheightratio = votefillheightratio
        self.border = border
        self.animation_location = {}
        self.animation_fill = {0: 0}

    def get_last_location(self, maxf=None):
        return self.animation_location[get_last_frame(self.animation_location, maxf)]

    def get_last_votes(self, maxf=None):
        return self.animation_fill[get_last_frame(self.animation_fill, maxf)]

    def get_last_fill_location(self, maxf=None):
        zoffset = self.border + self.fraction_to_height(self.get_last_votes(maxf))
        return add_z_location(self.get_last_location(maxf), zoffset)

    def move(self, frame, duration, tolocation, votes):
        if self.animation_location:
            self.animation_location[frame] = self.get_last_location()
        self.animation_location[frame + duration] = tolocation
        # Make sure votes a stable during move and readjust to real value
        self.animation_fill[frame] = votes

    def fraction_to_height(self, fraction):
        return self.width * self.votefillheightratio * fraction


class VoteBaseG:
    def __init__(self, voterid, width, heightratio, location):
        self.voterid = voterid
        self.width = width
        self.heightratio = heightratio
        self.location = location

        self.animation_fill = {0: 1}

    def get_last_location(self, _=None):
        return self.location

    def fraction_to_height(self, fraction):
        return self.width * self.heightratio * fraction

    def get_last_votes(self, maxf=None):
        return self.animation_fill[get_last_frame(self.animation_fill, maxf)]

    def get_last_fill_location(self, maxf=None):
        return add_z_location(self.get_last_location(), self.fraction_to_height(self.get_last_votes(maxf)))


class VoteFractionG:
    def __init__(self, voterid, bucket: BucketG, vbase: VoteBaseG, width, heightratio, initlocation):
        self.voterid = voterid
        self.bucket = bucket
        self.candidatecode = bucket.candidatecode if bucket is not None else None
        self.vbase = vbase
        self.width = width
        self.heightratio = heightratio

        self.animation_location = {0: initlocation}
        self.animation_fill = {0: 0}

    def extract(self, startframe, endframe, extractdur, fraction):
        self.animation_fill[startframe] = 0
        self.animation_fill[startframe + extractdur] = fraction
        self.animation_fill[endframe - extractdur] = fraction
        self.animation_fill[endframe] = 0

    def transfer(self, issend, frame, movedur, extractdur, fraction):
        """ Animate the move of VF in either direction """
        startf = frame
        endf = frame + movedur

        startobj = self.vbase if issend else self.bucket
        start_loc = startobj.get_last_fill_location()
        start_loc2 = add_z_location(start_loc, -startobj.fraction_to_height(fraction))

        endobj = self.bucket if issend else self.vbase
        end_loc = endobj.get_last_fill_location()
        end_loc2 = add_z_location(end_loc, endobj.fraction_to_height(fraction))

        self.extract(startf, endf, extractdur, fraction)

        self.animation_location[startf - 0.5] = start_loc
        self.animation_location[startf] = start_loc
        adjust_fill(startobj, startf, extractdur, -fraction)
        self.animation_location[startf + extractdur] = start_loc2
        self.animation_location[startf + extractdur + 0.5] = start_loc2

        self.animation_location[endf - extractdur - 0.5] = end_loc
        self.animation_location[endf - extractdur] = end_loc
        adjust_fill(endobj, endf - extractdur, extractdur, fraction)
        self.animation_location[endf] = end_loc2
        self.animation_location[endf + 0.5] = end_loc2


def adjust_fill(objg: BucketG or VoteBaseG, frame, extractdur, fraction):
    fdata = objg.animation_fill
    startf = frame
    endf = frame + extractdur

    prev_endf = get_last_frame(fdata, endf)

    fdata[endf] = fdata[prev_endf] + fraction

    if startf > prev_endf:  # Skip adding start keyframe
        fdata[startf] = fdata[prev_endf]


def build(stv):
    stvp = STVProgress(stv)

    vfwidth = 0.05  # Cm
    votercount = len(stv.voters)

    bucketheightratio = 2
    bucketwidth = (votercount / bucketheightratio) ** (1/3) * vfwidth
    votefillheightratio = stv.totalseats * bucketheightratio / votercount

    buckgs = {}
    vbgs = {}
    vfgs = {}

    # Build buckets and fill
    for cand in stv.candidates.values():
        buckgs[cand.code] = BucketG(cand.code, bucketwidth, bucketheightratio, votefillheightratio, bucketwidth / 20)

    # Build Vote Base
    voterspacing = 0.5
    gridwidth_units = ceil(sqrt(votercount * 2))
    votersstartlocx = -(gridwidth_units - 1) * voterspacing / 2
    votersstartlocy = -2
    votersstartlocz = 0
    for i, voter in enumerate(stv.voters.values()):
        dx = i % gridwidth_units * voterspacing
        dy = i // gridwidth_units * -voterspacing
        dz = i // gridwidth_units * voterspacing / 2
        location = Location(votersstartlocx + dx, votersstartlocy + dy, votersstartlocz + dz)
        vbgs[voter.uid] = VoteBaseG(voter.uid, vfwidth, stv.totalseats, location)

    # Build voters
    for voter in stv.voters.values():
        vbase = vbgs[voter.uid]
        for vf in voter.votelinks:
            candcode = vf.candidate.code
            vfgs[(voter.uid, candcode)] = VoteFractionG(voter.uid, buckgs[candcode], vbase, vfwidth, stv.totalseats,
                                                        vbase.location)

    # Build animations
    frame = 30
    finterval = 30
    extractdur = 6
    stagger = 0
    for t, pos in stvp.get_tansform_and_position():
        if pos.loopisreduction:
            frame += 15

        if t is not None and t.returnvfs:
            for vf in t.returnvfs:
                vfgs[(vf.voterid, vf.candidatecode)].transfer(False, frame, finterval, extractdur, vf.fraction)
                frame += stagger
            frame += finterval

        if t is not None and t.sendvfs:
            for vf in t.sendvfs:
                vfgs[(vf.voterid, vf.candidatecode)].transfer(True, frame, finterval, extractdur, vf.fraction)
                frame += stagger
            frame += finterval

        if pos.hasdecision:
            # Announce Result
            frame += 0

        for locy, locz, candlist in [(0, 2, pos.winners), (0, 0, pos.active), (2, 0, pos.deactivated), (4, 0, pos.excluded)]:
            startposx = -(len(candlist) - 1) / 2
            for i, cand in enumerate(candlist):
                buckgs[cand.code].move(frame, finterval, Location(startposx + i, locy, locz), cand.votes)
        if pos.hasdecision:
            frame += finterval * 2

    return list(buckgs.values()), list(vbgs.values()), list(vfgs.values()), frame  # Total frames


def build_from_shell(usegroups, reactivationmode):
    try:
        from shell_interface import setup
    except ImportError:
        print('Could not import Shell Interface\nExiting')
        return

    return build(setup(usegroups, reactivationmode))


if __name__ == '__main__':
    objs = build_from_shell(True, True)
    for obj in objs:
        print(obj)
