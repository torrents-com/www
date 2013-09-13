# -*- coding: utf-8 -*-
"""
    Módulo principal de la aplicación Web
"""
import foofind.globals
from torrents import multidomain

import foofind.services.search.search
foofind.services.search.search.WORD_SEARCH_MIN_LEN = 1

import os, os.path
from foofind import defaults
from collections import OrderedDict
from flask import Flask, g, request, render_template, redirect, abort, url_for, make_response, get_flashed_messages, current_app
from flask.ext.assets import Environment, Bundle
from flask.ext.babelex import gettext as _
from babel import support, localedata, Locale
from raven.contrib.flask import Sentry
from webassets.filter import register_filter
from hashlib import md5

from foofind.web import allerrors

from foofind.services import *
from foofind.utils.webassets_filters import JsSlimmer, CssSlimmer
from foofind.utils import u, logging
from foofind.utils.bots import is_search_bot, is_full_browser, check_rate_limit

from torrents.blueprints.index import index
from torrents.blueprints.files import files
from torrents.blueprints.downloader import all_blueprints as downloader_blueprints
from torrents.templates import register_filters
from torrents.services import *

def create_app(config=None, debug=False):
    '''
    Inicializa la aplicación Flask. Carga los siguientes módulos:
     - index: página de inicio
     - page: páginas estáticas
     - user: gestión del usuario
     - files: búsqueda y obtención de ficheros
     - status: servicio de monitorización de la aplicación

    Y además, inicializa los siguientes servicios:
     - Configuración: carga valores por defecto y modifica con el @param config
     - Web Assets: compilación y compresión de recursos estáticos
     - i18n: detección de idioma en la URL y catálogos de mensajes
     - Cache y auth: Declarados en el módulo services
     - Files: Clases para acceso a datos
    '''
    app = Flask(__name__)
    app.config.from_object(defaults)
    app.debug = debug

    # Configuración
    if config:
        app.config.from_object(config)

    # Runtime config
    app.config["DOWNLOADER_FILES"] = {
        k: os.path.join(os.path.abspath(os.path.join(app.root_path,"..")), "downloads", v)
        for k, v in app.config["DOWNLOADER_FILES"].iteritems()
        }

    # Gestión centralizada de errores
    if app.config["SENTRY_DSN"]:
        sentry.init_app(app)
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

    # Configuración dependiente de la versión del código
    revision_filename_path = os.path.join(os.path.dirname(app.root_path), "revision")
    if os.path.exists(revision_filename_path):
        f = open(revision_filename_path, "r")
        data = f.read()
        f.close()
        revisions = tuple(
            tuple(i.strip() for i in line.split("#")[0].split())
            for line in data.strip().split("\n")
            if line.strip() and not line.strip().startswith("#"))
        revision_hash = md5(data).hexdigest()
        app.config.update(
            CACHE_KEY_PREFIX = "%s%s/" % (
                app.config["CACHE_KEY_PREFIX"] if "CACHE_KEY_PREFIX" in app.config else "",
                revision_hash
                ),
            REVISION_HASH = revision_hash,
            REVISION = revisions
            )
    else:
        app.config.update(
            REVISION_HASH = None,
            REVISION = ()
            )


    # Registra valores/funciones para plantillas
    app.jinja_env.globals["u"] = u

    # Blueprints
    app.register_blueprint(index)
    app.register_blueprint(files)
    for blueprint in downloader_blueprints:
        app.register_blueprint(blueprint)

    # Registra filtros de plantillas
    register_filters(app)

    # Web Assets
    if not os.path.isdir(app.static_folder+"/gen"): os.mkdir(app.static_folder+"/gen")
    assets = Environment(app)
    app.assets = assets
    assets.debug = app.debug
    assets.versions = "timestamp"

    register_filter(JsSlimmer)
    register_filter(CssSlimmer)

    assets.register('css_torrents', Bundle('main.css', 'jquery.treeview.css', 'torrentsdownloader.css', filters='pyscss', output='gen/main.css', debug=False), '960_24_col.css', filters='css_slimmer', output='gen/torrent.css')
    assets.register('js_torrents', Bundle('jquery.js', 'jquery.treeview.js', 'torrents.js', "jquery.colorbox-min.js", "cookies.js", filters='rjsmin', output='gen/torrents.js'), )

    # CSRF protection
    csrf.init_app(app)

    # Traducciones
    babel.init_app(app)

    @babel.localeselector
    def get_locale():
        return "en"

    # Cache
    cache.init_app(app)

    # Mail
    mail.init_app(app)

    # Acceso a bases de datos
    pagesdb.init_app(app)
    filesdb.init_app(app)
    feedbackdb.init_app(app)
    configdb.init_app(app)
    entitiesdb.init_app(app)
    torrentsdb.init_app(app, feedbackdb)

    configdb.register_action("flush_cache", cache.clear, _unique=True)

    # Blacklists
    if app.debug:
        blacklists.debug=True
    blacklists.load_data(torrentsdb.get_blacklists())

    def refresh_blacklists():
        '''
        Refresh blacklists.
        '''
        blacklists.load_data(torrentsdb.get_blacklists())

    configdb.register_action("refresh_blacklists", refresh_blacklists)

    # IPs españolas
    spanish_ips.load(os.path.join(os.path.dirname(app.root_path),app.config["SPANISH_IPS_FILENAME"]))

    # Servicio de búsqueda
    @app.before_first_request
    def init_process():
        if not eventmanager.is_alive():
            # Fallback inicio del eventManager
            eventmanager.start()

    # Profiler
    profiler.init_app(app, feedbackdb)

    eventmanager.once(searchd.init_app, hargs=(app, filesdb, entitiesdb, profiler))

    # Refresco de conexiones
    eventmanager.once(filesdb.load_servers_conn)
    eventmanager.interval(app.config["FOOCONN_UPDATE_INTERVAL"], filesdb.load_servers_conn)
    eventmanager.interval(app.config["FOOCONN_UPDATE_INTERVAL"], entitiesdb.connect)

    # Refresco de configuración
    eventmanager.once(configdb.pull)
    eventmanager.interval(app.config["CONFIG_UPDATE_INTERVAL"], configdb.pull)

    @app.before_request
    def before_request():

        # No preprocesamos la peticiones a static
        if request.path.startswith("/static/"):
            g.must_cache = False
            return

        g.blacklisted_content = False
        init_g(current_app)

        # ignora peticiones sin blueprint
        if request.blueprint is None and request.path.endswith("/"):
            if "?" in request.url:
                root = request.url_root[:-1]
                path = request.path.rstrip("/")
                query = request.url.decode("utf-8")
                query = query[query.find(u"?"):]
                return redirect(root+path+query, 301)
            return redirect(request.url.rstrip("/"), 301)


    @app.after_request
    def after_request(response):
        if request.user_agent.browser == "msie": response.headers["X-UA-Compatible"] = "IE-edge"
        if g.must_cache:
            response.headers["X-Cache-Control"] = "max-age=%d"%g.must_cache

        return response

    # Páginas de error
    errors = {
        404: ("Page not found", "The requested address does not exists."),
        410: ("Page not available", "The requested address is no longer available."),
        500: ("An error happened", "We had some problems displaying this page. Maybe later we can show it to you."),
        503: ("Service unavailable", "This page is temporarily unavailable. Please try again later.")
    }

    @allerrors(app, 400, 401, 403, 404, 405, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 500, 501, 502, 503)
    def all_errors(e):
        error = e.code if hasattr(e,"code") else 500
        title, description = errors[error if error in errors else 500]

        init_g(current_app)
        g.title = "Torrents.com | The Torrent Search Engine | " + title

        return render_template('error.html', code=str(error), title=title, description=description), error

    return app

def init_g(app):

    # cache por defecto
    g.must_cache = 7200

    # caracteristicas del cliente
    g.full_browser=is_full_browser()
    g.search_bot=is_search_bot()

    # idioma ingles
    g.lang = "en"

    # peticiones en modo preproduccion
    g.beta_request = request.url_root[request.url_root.index("//")+2:].startswith("beta.")

    # prefijo para los contenidos estáticos
    if g.beta_request:
        app_static_prefix = app.static_url_path
    else:
        app_static_prefix = app.config["STATIC_PREFIX"] or app.static_url_path
    g.static_prefix = app.assets.url = app_static_prefix

    # permite sobreescribir practicamente todo el <head> si es necesario
    g.override_header = False

    # dominio de la web
    g.domain = "torrents.com"
    g.domains_family = ["torrents.com", "torrents.fm", "torrents.ag", "torrents.ms"]
    for domain in g.domains_family:
        if domain in request.url_root:
            g.domain = domain
            break

    g.section = "torrents" if g.domain=="torrents.fm" else "downloader" if g.domain=="torrents.ms" else "news"
    g.domain_capitalized = g.domain.capitalize()

    if "RUM_CODES" in app.config:
        rum_codes = app.config["RUM_CODES"]
        g.RUM_code = rum_codes[g.domain] if g.domain in rum_codes else rum_codes["torrents.com"]
    else:
        g.RUM_code = None

    # Patrón de URL de busqueda, para evitar demasiadas llamadas a url_for
    g.url_search_base = url_for("files.search", query="___")

    # título de la página por defecto
    g.title = "Torrents.com | The Torrent Search Engine"

    g.keywords = {'torrents', 'download', 'files', 'search', 'audio', 'video', 'image', 'document', 'software'}

    g.show_blacklisted_content = app.config["SHOW_BLACKLISTED_CONTENT"]

    # informacion de categorias
    g.categories = app_categories = app.config["TORRENTS_CATEGORIES"]
    g.categories_by_url = {category.url:category for category in app_categories}

    g.featured = []

    # busqueda actual
    g.track = False
    g.query = g.clean_query = None
    g.category = None

    g.extra_container_classes = None

    # cookie control
    g.must_accept_cookies = request.remote_addr in spanish_ips
