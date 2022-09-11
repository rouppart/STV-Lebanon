from typing import Optional
from os import getenv

from .stv import STV
from .stv_progress import STVProgress, Position

VOTES_LIMIT = int(getenv('VOTES_LIMIT', 50))


def pos_to_json(pos: Position, initquota: float, winners_quota: dict, viewvoter: Optional[str]):
    j = {
        'round': pos.round,
        'subround': pos.subround,
        'loopcount': pos.loopcount,
        'looptype': pos.looptype,
        'message': pos.message,
        'candidates': {},
        'viewballot': None,
        'waste': round(sum(pos.waste.values()), 2)
    }
    for status, candlist in [('winner', pos.winners), ('active', pos.active), ('deactivated', pos.deactivated),
                             ('excluded', pos.excluded)]:
        for cand in candlist:
            quota = round(winners_quota[cand.code] if status == 'winner' else initquota, 2)
            j['candidates'][cand.code] = {'votes': round(cand.votes, 2), 'status': status, 'quota': quota}

    if viewvoter is not None:
        j['viewballot'] = []
        for vf in pos.votefractions.values():
            if vf.voterid == viewvoter:
                ballotline = {'ccode': vf.candidatecode, 'fraction': round(vf.fraction, 2), 'status': vf.status[0]}
                j['viewballot'].append(ballotline)

    return j


def lambda_handler(event, context):
    # Preliminary checks
    usegroups = event['usegroups']
    reactivation = event['reactivation']
    groups = event['groups']
    candidates = event['candidates']
    votes = event['votes']
    viewvoter = event.get('viewvoter')

    if len(votes) > VOTES_LIMIT:
        return get_error('Function', 'limit is {} votes'.format(VOTES_LIMIT))

    stv = STV(usegroups, reactivation)

    for group in groups:
        stv.add_group(group['name'], group['seats'])

    for candidate in candidates:
        stv.add_candidate(candidate['code'], candidate['name'], candidate['group'])

    for vote in votes:
        stv.add_voter(vote['voterid'], vote['ballot'])

    if viewvoter not in stv.voters:
        viewvoter = None
    stvp = STVProgress(stv)
    # Get Quotas
    initquota = stv.quota
    winners_quota = {cand.code: cand.wonatquota for cand in stv.winners}

    loops = []
    for t, pos in stvp.get_tansform_and_position():
        loops.append(pos_to_json(pos, initquota, winners_quota, viewvoter))

    # Create links
    lastroundli = len(loops) - 1
    lastsubroundli = len(loops) - 1
    lastround = loops[lastroundli]['round']
    lastsubround = loops[lastsubroundli]['subround']

    for i, loop in list(enumerate(loops))[::-1]:
        loop['nextRound'] = lastroundli
        loop['nextSubround'] = lastsubroundli

        if loop['round'] != lastround:
            lastround = loop['round']
            lastroundli = i

        if loop['round'] != lastround or loop['subround'] != lastsubround:
            lastsubround = loop['subround']
            lastsubroundli = i

    lastroundli = 0
    lastsubroundli = 0
    lastround = loops[lastroundli]['nextRound']
    lastsubround = loops[lastsubroundli]['nextSubround']

    for i, loop in enumerate(loops):
        loop['previousRound'] = lastroundli
        loop['previousSubround'] = lastsubroundli

        if loop['nextRound'] != lastround:
            lastround = loop['nextRound']
            lastroundli = i

        if loop['nextRound'] != lastround or loop['nextSubround'] != lastsubround:
            lastsubround = loop['nextSubround']
            lastsubroundli = i

    return {'quota': stv.quota, 'loops': loops, 'viewvoter': viewvoter}


def get_error(errortype, msg):
    return {'errorType': errortype, 'errorMessage': msg}
