# -*- coding: utf-8 -*-
"""
    Servicios utilizados por la aplicación web de Torrents
"""
from .torrentsstore import TorrentsStore

__all__=['torrentsdb']

torrentsdb = TorrentsStore()
