from typing import Any, List, Dict, Union, Optional
from collections import namedtuple
from math import sqrt, ceil
from stv_lebanon.stv import STV
from stv_lebanon.stv_progress import STVProgress


Location = namedtuple('Location', ['x', 'y', 'z'])
TextStrip = namedtuple('TextStrip', ['overlay', 'text', 'startframe', 'endframe', 'color'])


def add_location(loc, x=0.0, y=0.0, z=0.0):
    return Location(loc.x + x, loc.y + y, loc.z + z)


def get_last_frame(adata: Dict[float, Any], maxf) -> float:
    if maxf is None:
        return max(adata.keys())
    else:
        return max(k for k in adata.keys() if k <= maxf)


class BucketG:
    def __init__(
            self,
            candidatecode: str,
            candidatename: str,
            width: float,
            heightratio: float,
            votefillheightratio: float,
            border: float
    ):
        self.candidatecode = candidatecode
        self.candidatename = candidatename
        self.width = width
        self.heightratio = heightratio
        self.votefillheightratio = votefillheightratio
        self.border = border
        self.animation_location: Dict[float, Location] = {}
        self.animation_fill: Dict[float, float] = {0: 0}

    def get_last_location(self, maxf=None) -> Location:
        return self.animation_location[get_last_frame(self.animation_location, maxf)]

    def get_last_votes(self, maxf=None) -> float:
        return self.animation_fill[get_last_frame(self.animation_fill, maxf)]

    def get_last_fill_location(self, maxf=None) -> Location:
        zoffset = self.border + self.fraction_to_height(self.get_last_votes(maxf))
        return add_location(self.get_last_location(maxf), z=zoffset)

    def move(self, frame: float, duration: float, tolocation: Location, votes: float) -> None:
        if self.animation_location:
            self.animation_location[frame] = self.get_last_location()
        self.animation_location[frame + duration] = tolocation
        # Make sure votes a stable during move and readjust to real value
        self.animation_fill[frame] = votes

    def fraction_to_height(self, fraction: float):
        return self.width * self.votefillheightratio * fraction


class VoteBaseG:
    def __init__(self, uid: str, width: float, heightratio: float, location: Location):
        self.uid = uid
        self.width = width
        self.heightratio = heightratio
        self.location = location

        self.animation_fill: Dict[float, float] = {0: 1}

    def get_last_location(self, _=None) -> Location:
        return self.location

    def fraction_to_height(self, fraction: float) -> float:
        return self.width * self.heightratio * fraction

    def get_last_votes(self, maxf=None) -> float:
        return self.animation_fill[get_last_frame(self.animation_fill, maxf)]

    def get_last_fill_location(self, maxf=None) -> Location:
        return add_location(self.get_last_location(), z=self.fraction_to_height(self.get_last_votes(maxf)))


class VoteFractionG:
    def __init__(
            self,
            voterid: str,
            bucket: BucketG,
            vbase: VoteBaseG,
            width: float,
            heightratio: float,
            initlocation: Location
    ):
        self.voterid = voterid
        self.bucket = bucket
        self.candidatecode = bucket.candidatecode if bucket is not None else None
        self.vbase = vbase
        self.width = width
        self.heightratio = heightratio

        self.animation_location: Dict[float, Location] = {0: initlocation}
        self.animation_fill: Dict[float, float] = {0: 0}

    def extract(self, startframe: float, endframe: float, extractdur: float, fraction: float) -> None:
        self.animation_fill[startframe] = 0
        self.animation_fill[startframe + extractdur] = fraction
        self.animation_fill[endframe - extractdur] = fraction
        self.animation_fill[endframe] = 0

    def transfer(self, issend: bool, frame: float, movedur: float, extractdur: float, fraction: float) -> None:
        """ Animate the move of VF in either direction """
        startf = frame
        endf = frame + movedur

        startobj: Union[BucketG, VoteBaseG] = self.vbase if issend else self.bucket
        start_loc = startobj.get_last_fill_location()
        start_loc2 = add_location(start_loc, z=-startobj.fraction_to_height(fraction))

        endobj: Union[BucketG, VoteBaseG] = self.bucket if issend else self.vbase
        end_loc = endobj.get_last_fill_location()
        end_loc2 = add_location(end_loc, z=endobj.fraction_to_height(fraction))

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


class TextOverLay:
    def __init__(self, name: str, channel: int, xpos: float, ypos: float, xalign: str, yalign: str, size: float):
        self.name = name
        self.channel = channel
        self.xpos = xpos
        self.ypos = ypos
        self.xalign = xalign
        self.yalign = yalign
        self.size = size


def adjust_fill(objg: Union[BucketG, VoteBaseG], frame: float, extractdur: float, fraction: float) -> None:
    fdata = objg.animation_fill
    startf = frame
    endf = frame + extractdur

    prev_endf = get_last_frame(fdata, endf)

    fdata[endf] = fdata[prev_endf] + fraction

    if startf > prev_endf:  # Skip adding start keyframe
        fdata[startf] = fdata[prev_endf]


class STVBlender:
    def __init__(self, stv: STV, viewid: Optional[str] = None):
        stvp = STVProgress(stv)

        vfwidth = 0.05  # Cm
        votercount = len(stv.voters)

        bucketheightratio: float = 2
        bucketwidth = (votercount / bucketheightratio) ** (1/3) * vfwidth
        votefillheightratio = stv.totalseats * bucketheightratio / votercount

        self.viewvoter = stv.voters.get(viewid) if viewid is not None else None
        self.textstrips: List[TextStrip] = []
        overlay_round = TextOverLay('Rounds', 2, 0, 1, 'LEFT', 'TOP', 50)
        overlay_looptype = TextOverLay('Message', 3, 0.5, 1, 'CENTER', 'TOP', 50)
        overlay_comment = TextOverLay('Comment', 4, 1, 1, 'RIGHT', 'TOP', 30)
        overlay_tracking = TextOverLay('Tracking', 5, 1, 0, 'RIGHT', 'BOTTOM', 30)

        # Build buckets and fill
        buckgs = {}
        for cand in stv.candidates.values():
            buckgs[cand.code] = BucketG(cand.code, cand.name, bucketwidth, bucketheightratio,
                                        votefillheightratio, bucketwidth / 15)

        # Build Vote Base
        def viewvotertest(v):
            return 1 if v is self.viewvoter else 0

        vbgs = {}
        voterlist = sorted(stv.voters.values(), key=viewvotertest)
        voterspacing = 0.5
        gridwidth_units = ceil(sqrt(votercount * 2))
        votersstartlocx = -(gridwidth_units - 1) * voterspacing / 2
        votersstartlocy = -2
        votersstartlocz = 0
        for i, voter in enumerate(voterlist):
            dx = i % gridwidth_units * voterspacing
            dy = i // gridwidth_units * -voterspacing
            dz = i // gridwidth_units * voterspacing / 2
            location = Location(votersstartlocx + dx, votersstartlocy + dy, votersstartlocz + dz)
            vbgs[voter.uid] = VoteBaseG(voter.uid, vfwidth, stv.totalseats, location)

        # Build votefractions
        vfgs = {}
        for voter in voterlist:
            vbase = vbgs[voter.uid]
            for vl in voter.votelinks:
                candcode = vl.candidate.code
                vfgs[(voter.uid, candcode)] = VoteFractionG(voter.uid, buckgs[candcode], vbase, vfwidth, stv.totalseats,
                                                            vbase.location)

        # Build animations
        frame: float = 30
        finterval: float = 30
        extractdur: float = 6
        stagger: float = 0
        for t, pos in stvp.get_tansform_and_position():
            looproundstartf = frame
            if pos.looptype == pos.REDUCTION:
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
                frame += finterval

            for locy, locz, candlist in [
                (0, 2, pos.winners), (0, 0, pos.active), (2, 0, pos.deactivated), (4, 0, pos.excluded)
            ]:
                xunits = len(candlist) if candlist is not pos.winners else stv.totalseats
                startposx = -(xunits - 1) / 2
                for i, cand in enumerate(candlist):
                    buckgs[cand.code].move(frame, finterval, Location(startposx + i, locy, locz), cand.votes)
            if pos.hasdecision:
                frame += finterval * 2

            # Create Overlays
            if frame > looproundstartf:
                grey = (0.3, 0.3, 0.3, 1)
                # Round
                text = 'Round: {}.{}'.format(pos.round, pos.subround)
                self.textstrips.append(TextStrip(overlay_round, text, looproundstartf, frame, grey))

                # Loop Type
                looptype_trans = {
                    pos.WIN: ('Win', (0.1, 1, 0.1, 1)),  # Green
                    pos.LOSS: ('Loss', (1, 0, 0, 1)),  # Red
                    pos.REDUCTION: ('Reduction', (1, 1, 0, 1)),  # Yello
                    pos.ALLOCATION: ('Allocation', (0.2, 0.2, 1, 1)),  # Blue
                    pos.UNKNOWN: ('Beginning', grey)  # White
                }[pos.looptype]
                self.textstrips.append(
                    TextStrip(overlay_looptype, looptype_trans[0], looproundstartf, frame, looptype_trans[1])
                )

                # Comments
                if pos.excluded_group is not None:
                    comment = 'Exclusion of group: ' + pos.excluded_group
                    self.textstrips.append(TextStrip(overlay_comment, comment, looproundstartf, frame, grey))

                if self.viewvoter is not None:
                    text = "{}'s ballot".format(viewid)
                    lineformat = '\n{:16} {:>4.0%}'
                    for vl in self.viewvoter.votelinks:
                        candcode = vl.candidate.code
                        vf = pos.votefractions[(viewid, candcode)]
                        text += lineformat.format(vl.candidate.name[:16], vf.fraction)
                    text += lineformat.format('Waste', pos.waste[viewid])
                    self.textstrips.append(TextStrip(overlay_tracking, text, looproundstartf, frame, grey))
        self.lastframe = frame

        # set Variables
        self.buckets = list(buckgs.values())
        self.votebases = list(vbgs.values())
        self.votefractions = list(vfgs.values())


def build_from_cli(usegroups: bool, reactivationmode: bool, viewvoter=None, load_samples=False) -> STVBlender:
    from stv_lebanon.cli_interface import setup

    return STVBlender(setup(usegroups, reactivationmode, load_samples), viewvoter)


if __name__ == '__main__':
    stvb = build_from_cli(True, True, None, True)
    obj: Any
    for obj in stvb.buckets:
        print(obj)
    for obj in stvb.votebases:
        print(obj)
    for obj in stvb.votefractions:
        print(obj)
    for obj in stvb.textstrips:
        print(obj)
