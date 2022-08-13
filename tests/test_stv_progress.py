from stv_lebanon.stv_progress import STVProgress
from stv_lebanon.cli_interface import setup

print("Options:\n"
      "'g' to use group quotas\n"
      "'n' for no reactivation")
viewmode = input("Type any number of options: ")

stv = setup('g' in viewmode, 'n' not in viewmode, True)
stvp = STVProgress(stv)
candidates = stv.candidates

for t, pos in stvp.get_tansform_and_position():
    print(f"\n\nRound: {pos.round}.{pos.subround}.{pos.loopcount}")
    print(pos.message)
    print()

    if t is not None:
        vlformat = "{0:<12}{3} {1:.2f} {3} {2}"
        if t.returnvfs:
            print("Return Fractions")
            for vf in t.returnvfs:
                print(vlformat.format(vf.voterid, vf.fraction, candidates[vf.candidatecode].name, '<'))
        if t.sendvfs:
            print("Send Fractions")
            for vf in t.sendvfs:
                print(vlformat.format(vf.voterid, vf.fraction, candidates[vf.candidatecode].name, '>'))

    print("\nCandidates:")
    for candlist, status in [(pos.winners, 'W'), (pos.active, 'A'), (pos.deactivated, 'D'), (pos.excluded, 'E')]:
        for cand in candlist:
            print(f"{candidates[cand.code].name:<20}{status}  {cand.votes:,.2f}")