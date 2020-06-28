from stv import STV
from stv_progress import STVProgress

CANDIDATE_LIMIT = 50


def pos_to_json(pos, initquota, winners_quota):
    j = {
        'round': pos.round,
        'subround': pos.subround,
        'loopcount': pos.loopcount,
        'looptype': pos.looptype,
        'message': pos.message,
        'candidates': {}
    }
    for status, candlist in [('winner', pos.winners), ('active', pos.active), ('deactivated', pos.deactivated),
                             ('excluded', pos.excluded)]:
        for cand in candlist:
            quota = round(winners_quota[cand.code] if status == 'winner' else initquota, 2)
            j['candidates'][cand.code] = {'votes': round(cand.votes, 2), 'status': status, 'quota': quota}

    return j


def lambda_handler(event, context):
    try:
        usegroups = event['usegroups']
        reactivation = event['reactivation']
        groups = event['groups']
        candidates = event['candidates']
        votes = event['votes']
    except KeyError:
        return get_error('JSON not properly defined')

    if len(candidates) > CANDIDATE_LIMIT:
        return get_error('Function limited to {} candidates'.format(CANDIDATE_LIMIT))

    stv = STV(usegroups, reactivation)
    for group in groups:
        stv.add_group(group['name'], group['seats'])

    for candidate in candidates:
        stv.add_candidate(candidate['code'], candidate['name'], candidate['group'])

    for vote in votes:
        stv.add_voter(vote['voterid'], vote['ballot'])

    stvp = STVProgress(stv)
    # Get Quotas
    initquota = stv.quota
    winners_quota = {cand.code: cand.wonatquota for cand in stv.winners}

    loops = []
    for t, pos in stvp.get_tansform_and_position():
        loops.append(pos_to_json(pos, initquota, winners_quota))

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

    return {'quota': stv.quota, 'loops': loops}


def get_error(msg):
    return {'error': msg}


def test():
    import json
    with open('sample.json') as f:
        res = lambda_handler(json.load(f), None)
    print(json.dumps(res, indent=2))


if __name__ == '__main__':
    test()
