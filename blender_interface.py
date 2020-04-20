from collections import namedtuple
from math import sqrt, ceil
from stv_progress import STVProgress


Location = namedtuple('Location', ['x', 'y', 'z'])
LocationKF = namedtuple('LocationKF', ['frame', 'location'])
FillKF = namedtuple('FillKF', ['frame', 'fill'])
HideKF = namedtuple('HideKF', ['frame', 'hide'])


def add_z_location(loc, z):
    return Location(loc.x, loc.y, loc.z + z)


class BucketG:
    def __init__(self, candidatecode, width, heightratio, votefillheightratio, border):
        self.candidatecode = candidatecode
        self.width = width
        self.heightratio = heightratio
        self.votefillheightratio = votefillheightratio
        self.border = border
        self.animation_location = []
        self.animation_fill = []
        self.animation_hide = []

    def get_last_location(self):
        return self.animation_location[-1].location

    def get_last_votes(self):
        return self.animation_fill[-1].fill

    def get_last_fill_location(self):
        return add_z_location(self.get_last_location(), self.border + self.fraction_to_height(self.get_last_votes()))

    def move(self, frame, duration, tolocation, votes):
        if self.animation_location:
            self.animation_location.append(LocationKF(frame, self.get_last_location()))
        self.animation_location.append(LocationKF(frame + duration, tolocation))
        # Make sure votes a stable during move and readjust to real value
        self.animation_fill.append(FillKF(frame, votes))
        self.animation_fill.append(FillKF(frame + duration, votes))

        hide = votes < 0.001
        self.animation_hide.append(HideKF(frame, hide))
        self.animation_hide.append(HideKF(frame, hide))

    def fraction_to_height(self, fraction):
        return self.width * self.votefillheightratio * fraction


class VoteBaseG:
    def __init__(self, voterid, width, heightratio, location):
        self.voterid = voterid
        self.width = width
        self.heightratio = heightratio
        self.location = location

        self.animation_fill = [FillKF(0, 1)]
        self.animation_hide = [HideKF(0, False)]

    def get_last_location(self):
        return self.location

    def fraction_to_height(self, fraction):
        return self.width * self.heightratio * fraction

    def get_last_fill_location(self):
        return add_z_location(self.get_last_location(), self.fraction_to_height(self.animation_fill[-1].fill))


class VoteFractionG:
    def __init__(self, voterid, bucket: BucketG, vbase: VoteBaseG, width, heightratio, initlocation):
        self.voterid = voterid
        self.bucket = bucket
        self.candidatecode = bucket.candidatecode if bucket is not None else None
        self.vbase = vbase
        self.width = width
        self.heightratio = heightratio

        self.animation_location = [LocationKF(0, initlocation)]
        self.animation_fill = [FillKF(0, 0)]
        self.animation_hide = [HideKF(0, True)]

    def extract(self, startframe, endframe, extractdur, fraction):
        self.animation_hide.append(HideKF(startframe + 0.5, False))
        self.animation_fill.append(FillKF(startframe, 0))
        self.animation_fill.append(FillKF(startframe + extractdur, fraction))
        self.animation_fill.append(FillKF(endframe - extractdur, fraction))
        self.animation_fill.append(FillKF(endframe, 0))
        self.animation_hide.append(HideKF(endframe - 0.5, True))

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

        self.animation_location.append(LocationKF(startf - 0.5, start_loc))
        self.animation_location.append(LocationKF(startf, start_loc))
        adjust_fill(startobj, startf, extractdur, -fraction)
        self.animation_location.append(LocationKF(startf + extractdur, start_loc2))
        self.animation_location.append(LocationKF(startf + extractdur + 0.5, start_loc2))

        self.animation_location.append(LocationKF(endf - extractdur - 0.5, end_loc))
        self.animation_location.append(LocationKF(endf - extractdur, end_loc))
        adjust_fill(endobj, endf - extractdur, extractdur, fraction)
        self.animation_location.append(LocationKF(endf, end_loc2))
        self.animation_location.append(LocationKF(endf + 0.5, end_loc2))


def adjust_fill(objg, frame, extractdur, fraction):
    startf = frame
    endf = frame + extractdur

    # Fill
    lastfkf = objg.animation_fill[-1]
    newfill = lastfkf.fill + fraction

    if lastfkf.frame == endf:
        objg.animation_fill[-1] = FillKF(endf, newfill)  # Probably don't need to check startf
    elif lastfkf.frame == startf:
        objg.animation_fill.append(FillKF(endf, newfill))
    else:
        objg.animation_fill.append(FillKF(startf, lastfkf.fill))
        objg.animation_fill.append(FillKF(endf, newfill))

    # Hide
    if newfill > 0:
        objg.animation_hide.append(HideKF(startf + 0.5, False))
    else:
        objg.animation_hide.append(HideKF(endf - 0.5, True))


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
    finterval = 30
    frame = 30
    for t, pos in stvp.get_tansform_and_position():
        if t is not None and t.returnvfs:
            for vf in t.returnvfs:
                vfgs[(vf.voterid, vf.candidatecode)].transfer(False, frame, finterval, 6, vf.fraction)
            frame += finterval

        if t is not None and t.sendvfs:
            for vf in t.sendvfs:
                vfgs[(vf.voterid, vf.candidatecode)].transfer(True, frame, finterval, 6, vf.fraction)
            frame += finterval

        for locy, locz, candlist in [(0, 2, pos.winners), (0, 0, pos.active), (2, 0, pos.deactivated), (4, 0, pos.excluded)]:
            startposx = -(len(candlist) - 1) / 2
            for i, cand in enumerate(candlist):
                buckgs[cand.code].move(frame, finterval, Location(startposx + i, locy, locz), cand.votes)

        # for vid, waste in pos.waste.items():
        #     vbgs[vid].animation_fill.append(FillKF(frame, waste))
        #     vbgs[vid].animation_fill.append(FillKF(frame + finterval, waste))

        frame += finterval

    return list(buckgs.values()), list(vbgs.values()), list(vfgs.values()), frame  # Total frames


def build_from_shell(usegroups, reactivationmode):
    try:
        from shell_interface import setup
    except ImportError:
        print('Could not import Shell Interface\nExiting')
        return

    return build(setup(usegroups, reactivationmode))


if __name__ == '__main__':
    objs = build_from_shell()
    for obj in objs:
        print(obj)
