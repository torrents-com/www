# -*- coding: utf-8 -*-
import pymongo, bson
from foofind.utils import check_capped_collections, u, check_collection_indexes
from datetime import datetime
from time import time
from collections import defaultdict
from foofind.services.extensions import cache

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
        self.torrents_conn = self.word_blacklist = self.word_blacklist_set = None


    def init_app(self, app):
        '''
        Inicializa la clase con la configuración de la aplicación.
        '''
        self.max_pool_size = app.config["DATA_SOURCE_MAX_POOL_SIZE"]

        # Inicia conexiones
        self.torrents_conn = pymongo.Connection(app.config["DATA_SOURCE_TORRENTS"], slave_okay=True, max_pool_size=self.max_pool_size)

        # Crea las colecciones capadas si no existen
        check_capped_collections(self.torrents_conn.torrents, self._capped)

        # Comprueba índices
        check_collection_indexes(self.torrents_conn.torrents, self._indexes)

        self.torrents_conn.end_request()

    def save_search(self, search, rowid, cat_id):
        self.torrents_conn.torrents.searches.insert({"_id":bson.objectid.ObjectId(rowid[:12]), "t":time(), "s":search, "c":cat_id})
        self.torrents_conn.end_request()

    def process_searches(self, data, limit, use_weights):
        ret = {}
        ret_words_sets = []
        for result in data:
            search = u(result["s"])
            words = frozenset(word[:-1] if word[-1]=="s" else word for word in search.lower().split(" ") if word)

            # comprueba lista de palabras no permitidas
            if any(word in self.word_blacklist for word in words):
                continue

            # comprueba lista de conjuntos de palabras no permitidas
            if any(word_set <= words for word_set in self.word_blacklist_set):
                continue

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
        searches = self.torrents_conn.torrents.searches.find().sort([("$natural",-1)]).limit(int(limit*1.3))
        ret = self.process_searches(searches, limit, False)
        self.torrents_conn.end_request()
        return ret

    def get_popular_searches(self, limit, cat_id=None):
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

        searches = self.torrents_conn.torrents.searches.aggregate(aggregation_cmd)
        self.torrents_conn.end_request()
        ret = self.process_searches(searches["result"], limit, True) if searches and searches["ok"] else {}
        return ret

    def add_blacklist(self, block):
        # ignora elementos vacios
        if not block:
            return

        if isinstance(block, (str,unicode)):
            self.torrents_conn.torrents.blacklist.save({"_id":block})
            self.word_blacklist.add(block)
        else:
            multi = sorted(filter(bool,set(block)))
            self.torrents_conn.torrents.blacklist.save({"_id":"_".join(multi), "m":multi})
            self.word_blacklist_set.add(frozenset(multi))

        # actualiza fecha de ultima actualizacion
        cache.set(BLACKLIST_CACHE_NAME, time())

    def del_blacklist(self, block):
        if isinstance(block, (str,unicode)):
            self.torrents_conn.torrents.blacklist.remove({"_id":block})
            self.word_blacklist.remove(block)
        else:
            multi = sorted(filter(bool,set(block)))
            self.torrents_conn.torrents.blacklist.remove({"_id":"_".join(multi)})
            self.word_blacklist_set.remove(frozenset(multi))

        # actualiza fecha de ultima actualizacion
        cache.set(BLACKLIST_CACHE_NAME, time())

    def get_blacklists(self):
        # obtiene fecha de ultima actualizacion
        last_blacklist_update = cache.get(BLACKLIST_CACHE_NAME)

        # si no tiene cache o este ha caducado, actualiza
        if not self.word_blacklist or not self.word_blacklist_set or self.last_blacklist_update != last_blacklist_update:
            words, sets = set(), set()
            for block in self.torrents_conn.torrents.blacklist.find():
                if "m" in block:
                    sets.add(frozenset(block["m"]))
                else:
                    words.add(block["_id"])

            # almacena nueva lista
            self.word_blacklist, self.word_blacklist_set = words, sets
            self.last_blacklist_update = last_blacklist_update

        return self.word_blacklist, self.word_blacklist_set
