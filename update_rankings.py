# -*- coding: utf-8 -*-

import sys
from os.path import dirname, abspath
sys.path.append(dirname(dirname( abspath(__file__)))+"/foofind")

from os import environ
environ["FOOFIND_NOAPP"] = "1"

import rankings.generate
import production
import foofind.defaults

app = type("fake_app",(),{"config":foofind.defaults.__dict__.copy()})
app.config.update(production.settings.__dict__)
del app.config["__builtins__"]

# If Torrents has a shared connection, uses that connection settings
if not app.config["DATA_SOURCE_TORRENTS"]:
    app.config["DATA_SOURCE_TORRENTS"] = app.config["DATA_SOURCE_SHARING_SETTINGS"]["DATA_SOURCE_TORRENTS"]

rankings.generate.update_rankings(app)
