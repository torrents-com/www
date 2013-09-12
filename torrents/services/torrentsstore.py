# -*- coding: utf-8 -*-
import pymongo, bson
from foofind.utils import check_capped_collections, u, check_collection_indexes
from datetime import datetime
from time import time
from collections import defaultdict
from foofind.services.extensions import cache
from torrents.blacklists import Blacklists, prepare_phrase
from foofind.services import feedbackdb

BLACKLIST_CACHE_NAME = "BLACKLIST_DATE"

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
            )
        }

    def __init__(self):
        '''
        Inicialización de la clase.
        '''
        self.max_pool_size = self.last_blacklist_update = 0
        self.torrents_conn = None
        self.blacklists = Blacklists({})

    def init_app(self, app):
        '''
        Inicializa la clase con la configuración de la aplicación.
        '''
        self.debug = app.debug
        self.max_pool_size = app.config["DATA_SOURCE_MAX_POOL_SIZE"]

        # soporte para ReplicaSet
        self.options = {"replicaSet": app.config["DATA_SOURCE_TORRENTS_RS"], "read_preference":pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED, "secondary_acceptable_latency_ms":app.config.get("SECONDARY_ACCEPTABLE_LATENCY_MS",15)} if "DATA_SOURCE_TORRENTS_RS" in app.config else {"slave_okay":True}

        # Inicia conexiones
        self.torrents_conn = pymongo.MongoClient(app.config["DATA_SOURCE_TORRENTS"], max_pool_size=self.max_pool_size, **self.options)
        self.searches_conn = feedbackdb.feedback_conn # uses feedback database for searches

        # Crea las colecciones capadas si no existen
        check_capped_collections(self.searches_conn.torrents, self._capped)

        # Comprueba índices
        check_collection_indexes(self.searches_conn.torrents, self._indexes)

        self.torrents_conn.end_request()

    def save_search(self, search, rowid, cat_id):
        self.searches_conn.torrents.searches.insert({"_id":bson.objectid.ObjectId(rowid[:12]), "t":time(), "s":search, "c":cat_id})
        self.searches_conn.end_request()

    def process_searches(self, data, limit, use_weights):
        ret = {}
        ret_words_sets = []
        for result in data:
            search = u(result["s"])

            # comprueba algun conjunto de terminos no permitidos
            if prepare_phrase(search) in self.blacklists:
                continue

            words = frozenset(word[:-1] if word[-1]=="s" else word for word in search.lower().split(" ") if word)

            # comprueba que no esté incluida en otra busqueda
            if any(aset <= words or words <= aset for aset in ret_words_sets):
                continue

            # comprueba que sea muy parecida a otra busqueda
            if any(levenshtein(prev_search, search,1)<2 for prev_search in ret):
                continue

            # añade la busqueda a los resultados
            ret[search] = result["w"] if use_weights else limit
            ret_words_sets.append(words)

            # contador de cantidad
            limit -= 1
            if limit<=0:
                break
        return ret

    def get_last_searches(self, limit):
        searches = self.searches_conn.torrents.searches.find().sort([("$natural",-1)]).limit(int(limit*1.3))
        ret = self.searches_conn(searches, limit, False)
        self.torrents_conn.end_request()
        return ret

    @cache.memoize(60*60)
    def find_popular_searches(self, limit, cat_id):
        aggregation_cmd = [
          { "$group" : {"_id" : "$s", "w" : {"$sum":1}}},
          { "$project" : {"key" : {"$toLower":"$_id"}, "w":"$w"}},
          { "$sort": { "w": -1} },
          { "$group" : {"_id" : "$key", "w" : {"$sum":"$w"}, "s": { "$first": "$_id" } }},
          { "$sort": { "w": -1} },
          { "$limit": int(limit*1.3) }
        ]
        if cat_id!=None:
            aggregation_cmd.insert(0,{ "$match": { "c": cat_id} })

        searches = self.searches_conn.torrents.searches.aggregate(aggregation_cmd)
        self.searches_conn.end_request()
        return searches

    def get_popular_searches(self, limit, cat_id=None):
        searches = self.find_popular_searches(limit, cat_id)
        ret = self.process_searches(searches["result"], limit, True) if searches and searches["ok"] else {}
        return ret

    def get_blacklists(self, force_refresh=False):
        # obtiene fecha de ultima actualizacion
        last_blacklist_update = cache.get(BLACKLIST_CACHE_NAME)

        if not self.blacklists or self.last_blacklist_update != last_blacklist_update or force_refresh:
            self.blacklists = Blacklists({row["_id"]:row["entries"] for row in self.torrents_conn.torrents.blacklists.find()}, self.debug)
            self.torrents_conn.end_request()
            self.last_blacklist_update = last_blacklist_update

        return self.blacklists

    def add_blacklist_entry(self, category, entry):
        self.torrents_conn.torrents.blacklists.update({"_id":category},{"$addToSet":{"entries":entry}}, upsert=True)
        self.torrents_conn.end_request()

        # actualiza fecha de ultima actualizacion
        cache.set(BLACKLIST_CACHE_NAME, time())

    def remove_blacklist_entry(self, category, entry):
        self.torrents_conn.torrents.blacklists.update({"_id":category},{"$pull":{"entries":entry}})
        self.torrents_conn.end_request()

        # actualiza fecha de ultima actualizacion
        cache.set(BLACKLIST_CACHE_NAME, time())
