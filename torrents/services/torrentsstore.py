# -*- coding: utf-8 -*-
import pymongo, bson, msgpack, redis
from foofind.utils import mid2hex, check_capped_collections, u, check_collection_indexes, logging
from datetime import datetime
from time import time
from collections import defaultdict, OrderedDict

VISITED_LINKS_CHANNEL = "VL"

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

    def init_app(self, app, feedbackdb):
        '''
        Inicializa la clase con la configuración de la aplicación.
        '''
        self.max_pool_size = app.config["DATA_SOURCE_MAX_POOL_SIZE"]

        # soporte para ReplicaSet
        self.options = {"replicaSet": app.config["DATA_SOURCE_TORRENTS_RS"], "read_preference":pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED, "secondary_acceptable_latency_ms":app.config.get("SECONDARY_ACCEPTABLE_LATENCY_MS",15)} if "DATA_SOURCE_TORRENTS_RS" in app.config else {"slave_okay":True}

        # Inicia conexiones
        self.torrents_conn = pymongo.MongoClient(app.config["DATA_SOURCE_TORRENTS"], max_pool_size=self.max_pool_size, **self.options)
        self.searches_conn = feedbackdb.feedback_conn # uses feedback database for searches

        # Inicia conexion al redis para avisar de files visitados
        self.redis_server = app.config["SPHINX_REDIS_SERVER"][0]
        self.redis_conn = redis.StrictRedis(host=self.redis_server[0], port=self.redis_server[1])

        # Crea las colecciones capadas si no existen
        check_capped_collections(self.searches_conn.torrents, self._capped)

        # Comprueba índices
        check_collection_indexes(self.searches_conn.torrents, self._indexes)

        self.torrents_conn.end_request()

        self.trend_map = bson.Code("function(){emit(this._id,{'t':this.value.w})}")

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

    def get_rankings(self):
        ret = OrderedDict((r["_id"],r) for r in self.torrents_conn.torrents.rankings.find().sort("order",1))
        self.torrents_conn.end_request()
        return ret

    def save_ranking(self, ranking):
        self.torrents_conn.torrents.rankings.save(ranking)
        self.torrents_conn.end_request()

    def verify_ranking_searches(self, ranking):
        self.torrents_conn.torrents["rankings."+ranking].ensure_index([("value.w", 1)])
        self.torrents_conn.end_request()

    def batch_ranking_searches(self, ranking, ranking_trends, generate_trends, multiplier):
        # get searches to generate trends (and reduce weights in the same process)
        if generate_trends:
            trend_reduce = bson.Code("function(k,v){if('w' in v[0]){v[0].w*=%f;v[0].t=v[1].t}else{v[0].w=%f*v[1].w}return v[0]}"%(multiplier,multiplier))
            self.torrents_conn.torrents["rankings."+ranking_trends].map_reduce(self.trend_map, trend_reduce, {"reduce":"rankings."+ranking})
        else:
            # reduce weights
            self.torrents_conn.torrents.command("$eval",bson.Code("db.rankings.%s.find().forEach(function(d){d.value.w*=%f;db.rankings.%s.save(d)})"%(ranking, multiplier, ranking)), nolock=True)

    def update_ranking_searches(self, ranking, search, weight):
        self.torrents_conn.torrents["rankings."+ranking].update({"_id":search},{"$inc": {"value.w": weight}}, upsert=True)
        self.torrents_conn.end_request()

    def clean_ranking_searches(self, ranking, max_size, weight_threshold):
        ranking_searches = self.torrents_conn.torrents["rankings."+ranking]
        ranking_searches.remove({"value.w":float("nan")})
        ranking_searches.remove({"value.w":{"$exists":False}})
        ranking_searches.remove({"value.w":{"$lt":weight_threshold}})

        norm_sum = ranking_searches.aggregate([{"$sort":{"value.w":-1}}, {"$limit":max_size}, {"$group":{"_id":{}, "norm":{"$sum" : "$value.w"}}}, {"$project":{"_id":0, "norm": "$norm"}}])
        self.torrents_conn.end_request()

        if norm_sum["ok"] and norm_sum["result"]:
            return norm_sum["result"][0]["norm"]
        else:
            return None

    def get_ranking_searches(self, ranking):
        return self.torrents_conn.torrents["rankings."+ranking].find().sort("value.w", -1)

    def save_search(self, search, rowid, cat_id):
        self.searches_conn.torrents.searches.insert({"_id":bson.objectid.ObjectId(rowid[:12]), "t":time(), "s":search, "c":cat_id})
        self.searches_conn.end_request()

    def get_searches(self, start_date):
        ret = list(self.searches_conn.torrents.searches.find({"t":{"$gt": start_date}}))
        self.searches_conn.end_request()
        return ret

    def save_visited(self, files):
        try:
            self.redis_conn.publish(VISITED_LINKS_CHANNEL, msgpack.packb([mid2hex(f["file"]["_id"]) for f in files if f]))
        except BaseException as e:
            logging.exception("Can't log visited files.")

    def get_subcategories(self):
        results = {subcats["_id"]:set(subcats["sc"]) for subcats in self.torrents_conn.torrents.subcategory.find()}
        self.torrents_conn.end_request()
        return results
