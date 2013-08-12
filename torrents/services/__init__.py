# -*- coding: utf-8 -*-
"""
    Servicios utilizados por la aplicación web de Torrents
"""
from .torrentsstore import TorrentsStore
from .tagclouds import TagClouds

__all__=['torrentsdb', 'tag_clouds']

torrentsdb = TorrentsStore()
tag_clouds = TagClouds()
