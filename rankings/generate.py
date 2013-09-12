# -*- coding: utf-8 -*-

import pymongo, bson
from heapq import nlargest
from operator import itemgetter
from collections import defaultdict
from time import time
from torrents.services.blacklists import Blacklists

def levenshtein(a,b,threshold):
    "Calculates the Levenshtein distance between a and b."
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a,b = b,a
        n,m = m,n

    if m-n>threshold:
        return threshold+1

    current = range(n+1)
    for i in xrange(1,m+1):
        previous, current = current, [i]+[0]*n
        for j in xrange(1,n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)
        if threshold and min(current)>threshold:
            return threshold+1
    return current[n]

RELEVANCE_FACTOR = 0.32

def update_rankings(app):

    torrentsdb = TorrentsStore()
    torrentsdb.init_app(app)

    blacklists = Blacklists()
    blacklists.load_data(torrentsdb.get_blacklists())


    rankings = torrentsdb.get_rankings()

    last_update = next(rankings.itervalues())["last_update"]

    searches = torrentsdb.get_searches(last_update)
    print "\n %d new searches: "%len(searches)

    if searches:
        new_last_update = max(s["t"] for s in searches)

        for ranking_name, ranking in rankings.iteritems():
            try:
                torrentsdb.verify_ranking_searches(ranking_name)

                # ranking info
                size = int(ranking["size"])
                max_size = int(ranking["max_size"])
                category = ranking.get("category", None)

                # ranking used to compare and create trends
                ranking_trends = ranking.get("trends", None)
                if ranking_trends:
                    ranking_trends_norm_factor = rankings[ranking_trends].get("norm_factor", None)

                generate_trends = ranking_trends and ranking_trends_norm_factor

                # calculate parameters for weights update
                ellapsed_time = new_last_update - ranking["last_update"]
                alpha = RELEVANCE_FACTOR ** (ellapsed_time/ranking["interval"])
                beta = (1 - alpha)/(ellapsed_time/60.)
                weight_threshold = beta * RELEVANCE_FACTOR

                print "RANKING %s: i = %d, lu = %.2f, wt = %.6f, te = %.2f alpha = %.6f, beta=%.6f"%(ranking_name, ranking["interval"], new_last_update, weight_threshold, ellapsed_time, alpha, beta)

                # reduce weights (and add trends info if needed)
                torrentsdb.batch_ranking_searches(ranking_name, ranking_trends, generate_trends, alpha):

                # update weights
                for search in searches:

                    # category filter for ranking
                    if category and search["c"]!=category:
                        continue

                    # check blacklists
                    if blacklists.prepare_phrase(search["s"]) in blacklists:
                        continue

                    # normalize search
                    text = search["s"].lower().replace(".", " ")

                    # increase weight for this search
                    torrentsdb.update_ranking_searches(self, ranking_name, text, beta)

                # discard less popular searches and calculates normalization factor
                norm_factor = torrentsdb.clean_ranking_searches(ranking_name, weight_threshold)

                if norm_factor:
                    ranking["norm_factor"] = norm_factor
                else:
                    norm_factor = ranking.get("norm_factor",1)
                    print "WARNING: can't calculate normalization factor."

                # filter and regenerate new ranking
                final_ranking = {}

                for search_row in torrentsdb.get_ranking_searches(ranking_name):

                    search = search_row["_id"]
                    weight = search_row["value"]["w"]

                    # split search in words
                    words = frozenset(word[:-1] if word[-1]=="s" else word for word in search.lower().split(" ") if word)

                    # calculate trend for this search
                    if generate_trends:
                        weight_trend = search_row["value"].get("t", None)
                        trend = (weight*ranking_trends_norm_factor/norm_factor/weight_trend) if weight_trend else None
                    else:
                        trend = None

                    # ignore searches similar, included or that includes another searches
                    '''for prev_search, info in final_ranking.iteritems():
                        if info[2] <= words or words <= info[2] or levenshtein(prev_search, search, 1)<2:
                            ignore = True
                            final_ranking[prev_search][0] += weight/norm_factor*alpha #  *alpha = similar searches is worst than exact same search
                            if final_ranking[prev_search][1] or trend:
                                final_ranking[prev_search][1] = (final_ranking[prev_search][1] or 0) + (trend or 0)
                            break

                    # no break, add the new search
                    else:'''

                    # adds word to set for checks in next iterations
                    final_ranking[search] = [weight/norm_factor, trend, words]

                    # stops when the list has the right size
                    if len(final_ranking)>=max_size:
                        break

                ranking["final_ranking"] = [(search, info[0], info[1]) for search, info in sorted(final_ranking.iteritems(), key=itemgetter(1,1), reverse=True)[:size]]

                # update ranking
                ranking["last_update"] = new_last_update

                torrentsdb.save_ranking(ranking)
            except BaseException as e:
                print "Error updating ranking '%s':"%ranking_name
                print type(e), e
