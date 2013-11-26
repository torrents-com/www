# -*- coding: utf-8 -*-

import pymongo, bson, traceback
from heapq import nlargest
from operator import itemgetter
from collections import defaultdict
from time import time

from foofind.services.db.feedbackstore import FeedbackStore
from torrents.services.torrentsstore import TorrentsStore
from torrents.services.blacklists import Blacklists

def get_ranking_info(ranking, new_last_update):
    # ranking info
    size = int(ranking["size"])
    category = ranking.get("category", None)
    relevance_factor = ranking["relevance_factor"]
    interval = ranking["interval"]
    order = int(ranking["order"])

    # ranking used to compare and create trends
    ranking_trends = ranking.get("trends", None)

    # calculate parameters for weights update
    ellapsed_time = new_last_update - ranking["last_update"]
    alpha = relevance_factor**(ellapsed_time/interval)
    beta = (1 - alpha)/(ellapsed_time/60.)

    weight_threshold = beta * relevance_factor**(ranking["threshold_interval"]/float(interval))

    return {"_id":ranking["_id"], "size":size, "category":category, "relevance_factor":relevance_factor, "alpha":alpha, "beta":beta, "weight_threshold":weight_threshold, "interval":interval, "order":order, "ranking_trends":ranking_trends}

def update_rankings(app):
    try:
        # initialize data access services
        torrentsdb = TorrentsStore()
        torrentsdb.init_app(app, None)

        # initialize blacklists
        blacklists = Blacklists()
        blacklists.load_data(torrentsdb.get_blacklists())

        # load rankings information
        rankings = torrentsdb.get_rankings()

        # load last searches
        last_update = max(r["last_update"] for r in rankings) # start from last updated date
        searches = torrentsdb.get_searches(last_update)
        new_last_update = max(s["t"] for s in searches)
        print "\n %d new searches to process. "%len(searches)

        # prepare rankings to process
        rankings = {ranking["_id"]:get_ranking_info(ranking, new_last_update) for ranking in rankings}
        torrentsdb.verify_rankings_searches(rankings)

        print "\n Updating weights."
        # reduce weights (and add trends info if needed)
        torrentsdb.batch_rankings_searches(rankings)
        print " ***\n"

        # update weights
        for search in searches:
            # check blacklists
            if blacklists.prepare_phrase(search["s"]) in blacklists:
                continue

            # normalize search
            text = search["s"].lower().replace(".", " ")

            # increase weight for this search
            torrentsdb.update_rankings_searches(rankings, text, search["c"])

        # discard less popular searches and calculates normalization factor
        min_weight, weight_threshold = torrentsdb.clean_rankings_searches(rankings, 100000)
        if min_weight>weight_threshold:
            print " Safe truncated at weight %.6e (threshold is %.6e).\n"%(min_weight, weight_threshold)
        elif min_weight:
            print " WARNING: Truncated at weight %.6e when threshold is %.6e.\n"%(min_weight, weight_threshold)
        else:
            print " Not truncated.\n"

        # create a dictionary with rankings that will be used as trends for other rankings
        final_rankings = {ranking["ranking_trends"]:None for ranking in rankings.itervalues()}

        for ranking in sorted(rankings.itervalues(), key=itemgetter("order")):
            ranking_name = ranking["_id"]
            try:
                print " Ranking %s: i = %d, wt = %.6e, alpha = %.6e, beta=%.6e"%(ranking_name, ranking["interval"], ranking["weight_threshold"], ranking["alpha"], ranking["beta"])
                final_ranking = []

                size = ranking["size"]
                ranking_size = 0

                # gets trends ranking
                ranking_trend = ranking.get("ranking_trends", None)
                trend_final_ranking = final_rankings[ranking_trend] if ranking_trend else None

                # gets normalization factor
                norm_factor = torrentsdb.get_ranking_norm_factor(ranking_name, ranking["size"])
                if not norm_factor:
                    norm_factor = ranking.get("norm_factor",1)
                    print "WARNING: can't calculate normalization factor."

                # filter and regenerate new ranking
                for search_row in torrentsdb.get_ranking_searches(ranking_name):
                    search = search_row["_id"]
                    weight = search_row[ranking_name]

                    # double-check blacklists
                    if blacklists.prepare_phrase(search) in blacklists:
                        continue

                    # calculate trend for this search
                    trend_pos = trend_final_ranking.get(search,None) if trend_final_ranking else None

                    # adds word to set for checks in next iterations
                    final_ranking.append((search, weight/norm_factor, trend_pos, trend_pos))
                    ranking_size += 1

                    # stops when the list has the right size
                    if ranking_size>=size:
                        break

                # update ranking
                torrentsdb.update_ranking(ranking, final_ranking, norm_factor, new_last_update)

                # saves info for next rankings trends
                if ranking_name in final_rankings:
                    final_rankings[ranking_name] = {entry[0]:i for i, entry in enumerate(final_ranking)}
                print " ***\n"
            except BaseException:
                print " ERROR updating ranking %s:"%ranking_name
                print traceback.format_exc()
    except BaseException:
        print " ERROR on main process:"
        print traceback.format_exc()
