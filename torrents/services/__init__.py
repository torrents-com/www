# -*- coding: utf-8 -*-
"""
    Servicios utilizados por la aplicación web de Torrents
"""
from .torrentsstore import TorrentsStore
from .ip_ranges import IPRanges
from .blacklists import Blacklists

__all__=['torrentsdb', 'spanish_ips', 'blacklists']

torrentsdb = TorrentsStore()
spanish_ips = IPRanges()
blacklists = Blacklists()
