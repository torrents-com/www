# -*- coding: utf-8 -*-
import pymongo, bson
from foofind.utils import check_capped_collections, u, check_collection_indexes
from datetime import datetime
from time import time
from collections import defaultdict
from foofind.services import feedbackdb
from torrents.blacklists import Blacklists, prepare_phrase


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

class TorrentsStore(object):
    '''
    Clase para acceder a los datos propios de torrents
    '''
    _capped = {
        "searches":50000,
        }
    _indexes = {
        "searches": (
            {"key": [("_id", 1)], "unique":1},
            {"key": [("c", 1)]},
            {"key": [("t", 1)]},
            )
        }

    def __init__(self):
        '''
        Inicialización de la clase.
        '''
        self.max_pool_size = 0
        self.torrents_conn = None

    def init_app(self, app):
        '''
        Inicializa la clase con la configuración de la aplicación.
        '''
        self.max_pool_size = app.config["DATA_SOURCE_MAX_POOL_SIZE"]

        # Inicia conexiones
        self.torrents_conn = pymongo.Connection(app.config["DATA_SOURCE_TORRENTS"], slave_okay=True, max_pool_size=self.max_pool_size)
        self.searches_conn = feedbackdb.feedback_conn # uses feedback database for searches

        # Crea las colecciones capadas si no existen
        check_capped_collections(self.searches_conn.torrents, self._capped)

        # Comprueba índices
        check_collection_indexes(self.searches_conn.torrents, self._indexes)

        self.torrents_conn.end_request()

    def save_search(self, search, rowid, cat_id):
        self.searches_conn.torrents.searches.insert({"_id":bson.objectid.ObjectId(rowid[:12]), "t":time(), "s":search, "c":cat_id})
        self.searches_conn.end_request()

    def get_blacklists(self):
        ret = {row["_id"]:row["entries"] for row in self.torrents_conn.torrents.blacklists.find()}
        self.torrents_conn.end_request()
        return ret

    def add_blacklist_entry(self, category, entry):
        self.torrents_conn.torrents.blacklists.update({"_id":category},{"$addToSet":{"entries":entry}}, upsert=True)
        self.torrents_conn.end_request()

    def remove_blacklist_entry(self, category, entry):
        self.torrents_conn.torrents.blacklists.update({"_id":category},{"$pull":{"entries":entry}})
        self.torrents_conn.end_request()

    def get_ranking(self, name):
        ret = self.torrents_conn.torrents.rankings.find_one({"_id":name})
        self.torrents_conn.end_request()
        return ret
