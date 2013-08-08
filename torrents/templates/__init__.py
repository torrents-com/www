# -*- coding: utf-8 -*-
import re
from flask import current_app, url_for, g, Markup
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
    app.jinja_env.filters['blacklist_query'] = blacklist_query
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

def blacklist_query(query, text=None, title=None):
    # conjunto de palabras
    words = frozenset(word[:-1] if word[-1]=="s" else word for word in query.lower().split("_"))

    # comprueba lista de palabras o conjuntos de palabras no permitidas
    if any(word in g.word_blacklist for word in words) or any(word_set <= words for word_set in g.word_blacklist_set):
        return Markup("<a>"+(text or query)+"</a>")

    return Markup("<a href='" + g.url_search_base.replace('___', query)+"' title='"+(title or text or query)+"'>"+(text or query)+"</a>")
