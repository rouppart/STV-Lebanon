from stv import STV
from stv_progress import STVProgress

CANDIDATE_LIMIT = 50


def pos_to_json(pos):
    j = {
        'round': pos.round,
        'subround': pos.subround,
        'loopcount': pos.loopcount,
        'looptype': pos.looptype,
        'message': pos.message,
        'winners': {},
        'active': {},
        'deactivated': {},
        'excluded': {}
    }
    for key, candlist in [('winners', pos.winners), ('active', pos.active), ('deactivated', pos.deactivated),
                          ('excluded', pos.excluded)]:
        for cand in candlist:
            j[key][cand.code] = round(cand.votes, 2)

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
    result = []
    for t, pos in stvp.get_tansform_and_position():
        result.append(pos_to_json(pos))

    return result


def get_error(msg):
    return {'error': msg}


def test():
    import json
    with open('sample.json') as f:
        res = lambda_handler(json.load(f), None)
    print(res)


if __name__ == '__main__':
    test()
