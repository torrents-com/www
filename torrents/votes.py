#!/usr/bin/env python
# -*- coding: utf-8 -*-
import operator, math

VOTES = {"f1": "Verified", "f2": "Fake file", "f3": "Password protected", "f4": "Low quality", "f5": "Virus", "f6": "Bad"}
VOTE_CODES = {v:k for k,v in VOTES.iteritems()}
VERIFIED_VOTE = "f1"
GENERIC_BAD_VOTE = "f6"
REAL_VOTE_TYPES = 5

torrents_probs = {"f1": 0.50, "f2": 0.25, "f3": 0.05, "f4": 0.19, "f5": 0.01}
def prob_bad(bads, oks):
    return math.exp(-0.02*oks*oks-0.0002*bads*bads)

def prob_ok(bads, oks):
    return math.exp(-0.0002*oks*oks-0.02*bads*bads)

no_votes = None

def evaluate_file_votes(system, users):
    if not system and not users and no_votes:
        return no_votes

    # calculates system probs
    if system:
        system_vote = max(system.iteritems(), key=operator.itemgetter(1))

        # calculate system vote and "the rest" of system votes
        system_vote_norm = (system_vote[1]+100)/200.
        rest_vote_norm = (1.-system_vote_norm)/(REAL_VOTE_TYPES-1)

        system_probs = {vtype:(0.00001*p0 + 0.99999*(system_vote_norm if vtype==system_vote[0] else rest_vote_norm)) for vtype, p0 in torrents_probs.iteritems()}
    else:
        system_probs = torrents_probs

    # adds users votes to system probs
    extra_bad = users.get(GENERIC_BAD_VOTE,0)
    probs = {}
    for vtype in system_probs:
        if vtype==VERIFIED_VOTE: # ignore verified votes at this step
            continue

        votes_bad = users.get(vtype,0) + extra_bad
        votes_ok = users.get(VERIFIED_VOTE,0)
        pbad = prob_bad(votes_bad, votes_ok)
        pok = prob_ok(votes_bad, votes_ok)

        s = system_probs[vtype]
        probs[vtype] = pbad * s / (pbad * s + pok * (1 - s))

    val = reduce(operator.mul, [1-p for p in probs.itervalues()], 1)

    return val, sorted(probs.iteritems(), key=operator.itemgetter(1), reverse=True)

no_votes = evaluate_file_votes({},{})

if __name__ == '__main__':
    import timeit

    print "Performance"
    print "No votes", timeit.timeit(lambda: evaluate_file_votes({}, {}), number=100000)
    print "System votes", timeit.timeit(lambda: evaluate_file_votes({"f1":60}, {}), number=100000)
    print "User votes", timeit.timeit(lambda: evaluate_file_votes({}, {"f1":10, "f3":23, "f2":12}), number=100000)
    print "Both votes", timeit.timeit(lambda: evaluate_file_votes({"f2":60}, {"f1":10, "f3":23, "f2":12}), number=100000)

    # evaluate for different system votes
    for system in [{}, {"f1":30}, {"f1":100}, {"f2":20}, {"f2":100}, {"f3":100}]:
        print system
        print "-"*30

        # no user votes
        print "No user:", evaluate_file_votes(system, {})

        # single type user votes
        for vtype in ["f1", "f2", "f3"]:
            for i in [1,2,3,5,7,9,15,20]:
                print "%d %s: %s"%(i, vtype, evaluate_file_votes(system, {vtype:i}))
            print

        # specific user cases votes
        for users in [{"f1":8, "f2":4}, {"f6":4}, {"f1":4, "f2":1}, {"f6":10, "f2":1}, {u'f1': 8, u'f2': 4, u'f6': 1}]:
            print "%s: %s"%(users, evaluate_file_votes(system, users))
        print
        print
