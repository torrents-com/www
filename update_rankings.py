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

rankings.generate.update_rankings(app)
