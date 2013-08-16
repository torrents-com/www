# -*- coding: utf-8 -*-
from msgpack import dumps, loads
from operator import itemgetter
from time import time
from foofind.utils import logging

TAG_CLOUDS = "TAG_CLOUDS"
TAG_CLOUDS_LAST_UPDATE = "TAG_CLOUDS_LAST_UPDATE"
class TagClouds:
    def __init__(self):
        self.clouds_caches = {}
        self.last_update = 0

    def init_app(self, clouds_params, torrentsdb, cache, config):
        self.clouds_params = clouds_params
        self.torrentsdb = torrentsdb
        self.cache = cache
        self.refresh_interval = config["TAGS_REFRESH_INTERVAL"]

    def refresh(self):
        try:
            # mira si ha habido actualizaciones de las nubes
            last_update = self.cache.get(TAG_CLOUDS_LAST_UPDATE) or 0

            if self.last_update < last_update: # obtiene de cache las nubes nuevas
                self.last_update = last_update
                self.clouds_caches = loads(self.cache.get(TAG_CLOUDS) or '\x80', encoding='utf-8')

            if not self.clouds_caches or (time() - self.last_update) >= self.refresh_interval: # debe regenerar las nubes
                self.cache.set(TAG_CLOUDS_LAST_UPDATE, time()) # evita que otros empiecen a regenerar tambien

                # fuerza refresco de palabras bloqueadas
                self.torrentsdb.get_blacklists(True)
        
                # regenera las nubes
                for cloud_params in self.clouds_params:
                    self.clouds_caches[cloud_params[0]] = self._get_searches(*cloud_params[1:])

                # guarda las nubes y avisa para que el resto actualice
                self.cache.set(TAG_CLOUDS, dumps(self.clouds_caches, encoding='utf-8'))
                self.cache.set(TAG_CLOUDS_LAST_UPDATE, time())
        except BaseException as e:
            logging.error("Error refreshing tag clouds")

    def __getitem__(self, name):
        return self.clouds_caches[name]

    def _get_searches(self, cloud_type, size, bins, cat_id=None):
        if cloud_type=="popular":
            searches = self.torrentsdb.get_popular_searches(size, cat_id)
        elif cloud_type=="recent":
            searches = self.torrentsdb.get_last_searches(size)
        bin_size = 1.0*len(searches)/bins
        return {search:int(order/bin_size)/float(bins) for order, (search, weight) in enumerate(sorted(searches.iteritems(), key=itemgetter(1)))}
