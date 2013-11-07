# -*- coding: utf-8 -*-
"""
    Servicios utilizados por la aplicación web de Torrents
"""
from .torrentsstore import TorrentsStore
from .ip_ranges import IPRanges
from .blacklists import Blacklists
from .categories import CategoriesCache

__all__=['torrentsdb', 'spanish_ips', 'blacklists', 'categories_cache']

torrentsdb = TorrentsStore()
spanish_ips = IPRanges()
blacklists = Blacklists()
categories_cache = CategoriesCache()
