# -*- coding: utf-8 -*-
import pymongo, bson, msgpack, redis
from foofind.utils import mid2hex, check_capped_collections, u, check_collection_indexes, logging
from datetime import datetime
from time import time
from collections import defaultdict, OrderedDict
from operator import itemgetter

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
        self.torrents_conn = self.redis_conn = self.searches_conn = None

    def init_app(self, app, searchd):
        '''
        Inicializa la clase con la configuración de la aplicación.
        '''
        self.max_pool_size = app.config["DATA_SOURCE_MAX_POOL_SIZE"]

        if app.config["DATA_SOURCE_TORRENTS"]:
            # soporte para ReplicaSet
            options = {"replicaSet": app.config["DATA_SOURCE_TORRENTS_RS"], "read_preference":pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED, "secondary_acceptable_latency_ms":app.config.get("SECONDARY_ACCEPTABLE_LATENCY_MS",15), "tag_sets":app.config.get("DATA_SOURCE_TORRENTS_RS_TAG_SETS",[{}])} if "DATA_SOURCE_TORRENTS_RS" in app.config else {"slave_okay":True}

            # Inicia conexiones
            self.torrents_conn = pymongo.MongoReplicaSetClient(app.config["DATA_SOURCE_TORRENTS"], max_pool_size=self.max_pool_size, **options)

        # Referencia al servicio de busquedas
        self.searchd = searchd

        # Conexion a bases de datos de feedback
        self.feedback_dbs = app.config["DATA_SOURCES_TORRENTS_FEEDBACK"]
        self.feedback_dbs_index = app.config.get("DATA_SOURCES_TORRENTS_FEEDBACK_INDEX", None)

        if not self.feedback_dbs_index is None:
            self.searches_conn = pymongo.MongoClient(self.feedback_dbs[self.feedback_dbs_index], max_pool_size=self.max_pool_size)
            self.init_searches_conn()

    def share_connections(self, torrents_conn=None, searches_conn=None):
        ''' Allows to share data source connections with other modules.'''
        if torrents_conn:
            self.torrents_conn = torrents_conn
        if searches_conn:
            self.searches_conn = searches_conn
            self.init_searches_conn()

    def init_searches_conn(self):
        ''' Inits searches database before its first use. '''
        # Crea las colecciones capadas si no existen
        check_capped_collections(self.searches_conn.torrents, self._capped)

        # Comprueba índices
        check_collection_indexes(self.searches_conn.torrents, self._indexes)
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

    def get_rankings(self):
        ret = list(self.torrents_conn.torrents.rankings.find())
        self.torrents_conn.end_request()
        return ret

    def update_ranking(self, ranking, final_ranking, norm_factor, update_date):
        self.torrents_conn.torrents.rankings.update({"_id":ranking["_id"]}, {"$set":{"final_ranking":final_ranking, "norm_factor":norm_factor, "last_update":update_date}})
        self.torrents_conn.end_request()

    def verify_rankings_searches(self, rankings):
        for ranking in rankings.iterkeys():
            self.torrents_conn.torrents.rankings_data.ensure_index([(ranking, 1)])
        self.torrents_conn.end_request()

    def batch_rankings_searches(self, rankings):
        self.torrents_conn.torrents.command("$eval",bson.Code("var alpha = ["+",".join("['%s',%f]"%(ranking, info["alpha"]) for ranking, info in rankings.iteritems())+"];db.rankings_data.find().forEach(function(d){for(var r in alpha)if(alpha[r][0] in d)d[alpha[r][0]]*=alpha[r][1];db.rankings_data.save(d)})"), nolock=True)

    def update_rankings_searches(self, rankings, search, category):
        self.torrents_conn.torrents.rankings_data.update({"_id":search},{"$inc": {ranking: info["beta"] for ranking, info in rankings.iteritems() if not info["category"] or category==info["category"]}}, upsert=True)
        self.torrents_conn.end_request()

    def clean_rankings_searches(self, rankings, max_size):
        # chooses max interval ranking to truncate less important searches
        max_ranking = max(rankings.itervalues(), key=itemgetter("interval"))
        ranking = max_ranking["_id"]

        # gets nth search, if exists
        nth_search = None
        try:
            nth_search = next(self.torrents_conn.torrents.rankings_data.find().sort(ranking,-1).skip(max_size).limit(1))
        except:
            pass

        if nth_search:
            # get nth element weight
            min_weight = nth_search[ranking]

            # delete all elements less important than minimum weight
            self.torrents_conn.torrents.rankings_data.remove({ranking:{"$lt":min_weight}})
            self.torrents_conn.torrents.rankings_data.remove({ranking:{"$exists":False}})

            return min_weight, max_ranking["weight_threshold"]

        return None, max_ranking["weight_threshold"]

    def get_ranking_norm_factor(self, ranking, max_size):
        norm_sum = self.torrents_conn.torrents.rankings_data.aggregate([{"$sort":{ranking:-1}}, {"$limit":max_size}, {"$group":{"_id":{}, "norm":{"$sum" : "$"+ranking}}}, {"$project":{"_id":0, "norm": "$norm"}}])
        self.torrents_conn.end_request()

        if norm_sum["ok"] and norm_sum["result"]:
            return norm_sum["result"][0]["norm"]
        else:
            return None

    def get_ranking_searches(self, ranking):
        return self.torrents_conn.torrents.rankings_data.find({ranking:{"$exists":True}}).sort(ranking, -1)

    def get_subcategories(self):
        results = {subcats["_id"]:subcats["sc"] for subcats in self.torrents_conn.torrents.subcategory.find()}
        self.torrents_conn.end_request()
        return results

    def save_visited(self, files):
        try:
            self.searchd.get_redis_connection().publish(VISITED_LINKS_CHANNEL, msgpack.packb([mid2hex(f["file"]["_id"]) for f in files if f]))
        except BaseException as e:
            logging.exception("Can't log visited files.")

    def save_search(self, search, rowid, cat_id):
        if self.searches_conn:
            try:
                self.searches_conn.torrents.searches.insert({"_id":bson.objectid.ObjectId(rowid[:12]), "t":time(), "s":search, "c":cat_id})
                self.searches_conn.end_request()
            except DuplicateKeyError as e:
                pass # don't log when a search is duplicated
            except BaseException as e:
                logging.exception("Can't register search stats.")

    def get_searches(self, start_date):
        ret = []
        for db in self.feedback_dbs:
            conn = pymongo.MongoClient(db, max_pool_size=self.max_pool_size)
            ret.extend(conn.torrents.searches.find({"t":{"$gt": start_date}}))
            conn.end_request()
        return ret

