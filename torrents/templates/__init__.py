# -*- coding: utf-8 -*-
import re
from flask import current_app
from foofind.templates import number_format_filter, number_size_format_filter, format_timedelta_filter, urlencode_filter, number_friendly_filter, pformat, numeric_filter, markdown_filter, seoize_filter
from foofind.utils.htmlcompress import HTMLCompress

import foofind.templates
def _(x): return x
foofind.templates._ = _

def register_filters(app):
    '''
    Registra filtros de plantillas
    '''
    app.jinja_env.filters['numberformat'] = number_format_filter
    app.jinja_env.filters['numbersizeformat'] = number_size_format_filter
    app.jinja_env.filters['format_timedelta'] = format_timedelta_filter
    app.jinja_env.filters['urlencode'] = urlencode_filter
    app.jinja_env.filters['numberfriendly'] = number_friendly_filter
    app.jinja_env.filters['pprint'] = pformat
    app.jinja_env.filters['numeric'] = numeric_filter
    app.jinja_env.filters['markdown'] = markdown_filter
    app.jinja_env.filters['seoize'] = seoize_filter
    app.jinja_env.filters['clean_query'] = clean_query
    app.jinja_env.filters['singular'] = singular_filter
    app.jinja_env.filters['cycle'] = cycle_filter
    app.jinja_env.add_extension(HTMLCompress)

whitespaces = re.compile(r'[\s\/]+')
def clean_query(query):
    query = re.sub(whitespaces, '_', query.strip())
    maxlen = current_app.config["MAX_LENGTH"]
    if len(query)>maxlen:
        final = query[:maxlen].rfind("_")
        if final>0:
            maxlen = final
        query = query[:maxlen-1]
    return query

def singular_filter(text):
    return text[:-1] if text[-1]=="s" else text

def cycle_filter(alist):
    alist.insert(0, alist.pop())
    return alist[0]
