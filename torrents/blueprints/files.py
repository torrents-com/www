# -*- coding: utf-8 -*-

import datetime, time, itertools, re, math, urllib2, hashlib
from flask import flash, request, render_template, redirect, url_for, g, current_app, abort, escape, jsonify
from struct import pack, unpack
from base64 import b64decode, urlsafe_b64encode, urlsafe_b64decode
from urlparse import urlparse, parse_qs

from heapq import heapify, heappop

from foofind.utils import url2mid, u, logging, mid2hex, bin2hex, nocache
from foofind.utils.fooprint import Fooprint
from foofind.utils.seo import seoize_text
from foofind.utils.splitter import SEPPER
from foofind.services import *
from foofind.services.search.search import WORD_SEARCH_MIN_LEN, NGRAM_CHARS
from foofind.templates import number_size_format_filter
from torrents.services import *
from foofind.blueprints.files import download_search
from foofind.blueprints.files.helpers import *
from foofind.blueprints.files.fill_data import secure_fill_data, get_file_metadata
from torrents.templates import clean_query, singular_filter
from torrents import Category
from unicodedata import normalize

files = Fooprint('files', __name__)

referrer_parser = re.compile("^(?:.*\://.+/.+/([^\?]+))|(?:.*\?(?:.*\&)?q=([^\&]+))", re.UNICODE)

def weight_processor(w, ct, r, nr):
    return w if w else -10

def tree_visitor(item):
    if item[0]=="_w" or item[0]=="_u":
        return None
    else:
        return item[1]["_w"]

CATEGORY_ORDER = ("IDIV(fs,17280000)*(r+10)", "ok DESC, r DESC, fs DESC", "IDIV(fs,17280000)*(r+10)")
RECENT_ORDER = ("fs", "ok DESC, r DESC, e DESC", "fs")
RANKING_ORDER = ("IDIV(fs,1728000)*(r+10)", "ok DESC, r DESC, fs DESC", "IDIV(fs,1728000)*(r+10)")
POPULAR_ORDER = RANKING_ORDER
SEARCH_ORDER = ("@weight*(r+10)", "e DESC, ok DESC, r DESC, fs DESC", "@weight*(r+10)")

CATEGORY_UNKNOWN = Category(cat_id=11, url="unknown", title='Unknown', tag=u'unknown', content='unknown', content_main=True, show_in_home=False)

COLUMN_ORDERS = {
    "fs": ("fs", "ok DESC, r DESC, e DESC", "fs"),
    "rfs": ("-fs", "ok DESC, r DESC, e DESC", "-fs"),
    "z": ("z", "ok DESC, r DESC, e DESC, e DESC, fs DESC", "z"),
    "rz": ("if(z>0,1/z,-1)", "ok DESC, r DESC, e DESC, e DESC, fs DESC", "if(z>0,1/z,-1)"),
    "s": ("r", "ok DESC, e DESC, fs DESC", "r"),
    "rs": ("if(r>0,1/r,-1)", "ok DESC, e DESC, fs DESC", "if(r>0,1/r,-1)"),
}


def get_order(default_order):
    try:
        order = request.args.get("o",None)
        if order and order in COLUMN_ORDERS:
            return COLUMN_ORDERS[order], order
    except:
        pass
    return default_order, None

def get_skip(x=None):
    try:
        return min(int(request.args.get("s","0")),10)
    except:
        return 0

PIXEL = b64decode("R0lGODlhAQABAPAAAAAAAAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==")
@files.route("/res/pixel.gif")
@nocache
def pixel():
    g.must_cache = 0
    try:
        if not g.search_bot:
            parts = urllib2.unquote(request.referrer).decode("utf-8").split("?")[0].split("/")
            get_query_info(parts[-1], parts[-2] if parts[-2]!="search" else None, check_qs=False)

            if g.query and g.safe_query:
                # no registra busquedas muy largas
                if len(g.safe_query)>=current_app.config["MAX_LENGTH_SAVE"]:
                    return PIXEL

                # no registra busquedas con palabras no permitidas
                if g.blacklists.prepare_phrase(g.safe_query) in g.blacklists:
                    return PIXEL

                # si toca registrar y hay resultados, registra busqueda para nubes de tags
                ip = request.headers.getlist("X-Forwarded-For")[0] if request.headers.getlist("X-Forwarded-For") else request.remote_addr
                torrentsdb.save_search(g.query, hashlib.md5((g.safe_query+"_"+ip).encode("utf-8")).digest(), g.category.cat_id if g.category else 0)
    except BaseException as e:
        logging.warn("Error registering search.")

    return PIXEL

def get_featured(results_shown=100, headers=1):
    feat = g.featured[:]
    del g.featured
    heapify(feat)
    results_shown += 1 if headers==1 else headers*4
    count = min(len(feat), int(math.ceil((results_shown)/7.)))
    return render_template('featured.html', files=[heappop(feat) for i in xrange(count)])

def get_query_info(query=None, category=None, check_qs=True):
    redirect = False
    if not query and check_qs:
        query = request.args.get("q",None)
        if query:
            redirect = True

    if not category and check_qs:
        category = request.args.get("c",None)
        if category:
            redirect = True

    if query:
        g.clean_query = clean_query(query)
        g.query = g.clean_query.replace("_"," ")
        g.safe_query = seoize_text(query, " ").lower()

    if category:
        if category in g.categories_by_url:
            g.category = g.categories_by_url[category]

    return redirect

@files.route('/search_info')
def search_info():

    must_redirect = get_query_info()
    not_category = request.args.get("nc",None)

    final_query = (g.query+u" " if g.query else u"")+(u"("+g.category.tag+")" if g.category and g.category.tag else u"")+(u" -("+not_category+")" if not_category else u"")

    order, show_order = get_order(SEARCH_ORDER)
    return jsonify(searchd.get_search_info(final_query, filters=None, order=order))

@files.route('/search/')
@files.route('/search/<query>')
def search(query=None):

    search_bot = g.search_bot

    must_redirect = get_query_info(query)

    if not g.query:
        flash("Write something!")
        return redirect(url_for("index.home"))

    if must_redirect:
        if g.category:
            return redirect(url_for("files.category", category=g.category.url, query=g.clean_query))
        else:
            return redirect(url_for("files.search", query=g.clean_query))

    order, show_order = get_order(SEARCH_ORDER)

    skip = get_skip()

    results, search_info = single_search(g.query, None, zone="Search", order=order, title=("%s torrents"%escape(g.query), 2, None), last_items=get_last_items(), skip=skip, show_order=show_order or True)

    if search_info['count'] == 0:
        _query = normalize('NFC', g.query)
        if g.query != _query:
            results, search_info = single_search(_query, None, zone="Search", order=order, title=("%s torrents"%escape(g.query), 2, None), last_items=get_last_items(), skip=skip, show_order=show_order or True)

    #g.title+=" | " + g.query
    g.title = "Torrents.com | " + g.query

    g.title += " | Page %d" % (int(skip) + 1) if skip > 0 else ""

    g.page_description = "Download %s torrent from %s search engine with free, fast downloads." % (g.query, g.domain_capitalized)

    if search_bot:
        searchd.log_bot_event(search_bot, (search_info["total_found"]>0 or search_info["sure"]))
    else:
        g.track = bool(results)

    return render_template('search.html', results=results, search_info=search_info, show_order=show_order, featured=get_featured(search_info["count"]))

@files.route('/<category>')
@files.route('/<category>/<query>')
def category(category, query=None):

    get_query_info(query, category)

    # categoria invalida
    if not g.category:
        return abort(404)

    g.title = "Torrents.com"

    page_title = singular_filter(g.category.title)+" torrents"
    pop_searches = None
    if g.query:
        page_title += " | " + g.query
        g.page_description = "%s %s torrents at %s, the free and fast torrent search engine."%(g.query.capitalize(), singular_filter(g.category.title).lower(), g.domain_capitalized)
        order, show_order = get_order(SEARCH_ORDER)
    else:
        pop_searches = tag_clouds[g.category.url]
        g.page_description = "%s torrents at %s, the free and fast torrent search engine."%(singular_filter(g.category.title).capitalize(), g.domain_capitalized)
        order, show_order = get_order(CATEGORY_ORDER)
    g.title+=" | " + page_title

    results, search_info = single_search(g.query, g.category.tag, order=order, zone=g.category.url, title=(page_title, 2, g.category.tag), last_items=get_last_items(), skip=get_skip(), show_order=show_order or True)

    if g.query:
        if g.search_bot:
            searchd.log_bot_event(g.search_bot, (search_info["total_found"]>0 or search_info["sure"]))
        else:
            g.track = bool(results)

    return render_template('category.html', results=results, search_info=search_info, show_order=show_order, featured=get_featured(search_info["count"]), pop_searches=pop_searches)

@files.route('/recent')
def recent():
    g.category = False
    g.title+=" | Recent torrents"
    results, search_info = single_search(None, "torrent", "porn", order=RECENT_ORDER, zone="Recent", title=("Recent torrents", 2, None), last_items=get_last_items(), skip=get_skip(), show_order=None)
    g.keywords.clear()
    g.keywords.update(["recent", "torrents", "search", "search engine", "free", "full movie", "2013"])
    g.page_description = "%s is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."%g.domain_capitalized
    g.h1 = "Find recently created torrents on this page. For specific category torrents, click the tab above and sort by creation date."
    return render_template('ranking.html', title="Recent torrents", results=results, search_info=search_info, featured=get_featured(search_info["count"]))

@files.route('/popular')
def popular():
    g.category = False
    g.title+=" | Popular torrents"
    results, search_info = single_search(None, "torrent", "porn", order=POPULAR_ORDER, zone="Popular", title=("Popular torrents", 2, None), last_items=get_last_items(), skip=get_skip(), show_order=None)
    g.keywords.clear()
    g.keywords.update(["torrent", "torrents", "search engine", "popular downloads", "online movies"])
    g.page_description = "%s is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place." % g.domain_capitalized
    g.h1 = " These are the most popular torrents."
    return render_template('ranking.html', title="Popular torrents", results=results, search_info=search_info, featured=get_featured(search_info["count"]))

@files.route('/-<file_id>')
@files.route('/<file_name>-<file_id>')
def download(file_id, file_name=""):
    if request.referrer:
        try:
            posibles_queries = referrer_parser.match(request.referrer)
            if posibles_queries:
                query = posibles_queries.group(1) or posibles_queries.group(2) or ""
                if query:
                    get_query_info(u(urllib2.unquote_plus(query).decode("utf-8")))
        except:
            pass

    error = None
    file_data=None
    if file_id is not None: #si viene un id se comprueba que sea correcto
        try: #intentar convertir el id que viene de la url a uno interno
            file_id=url2mid(file_id)
        except TypeError as e:
            try: #comprueba si se trate de un ID antiguo
                possible_file_id = filesdb.get_newid(file_id)
                if possible_file_id is None:
                    logging.warn("Identificadores numericos antiguos sin resolver: %s."%e, extra={"fileid":file_id})
                    error=404
                else:
                    logging.warn("Identificadores numericos antiguos encontrados: %s."%e, extra={"fileid":file_id})
                    return {"html": redirect(url_for(".download", file_id=mid2url(possible_file_id), file_name=file_name), 301),"error":301}

            except BaseException as e:
                logging.exception(e)
                error=503

            file_id=None

        if file_id:
            try:
                file_data=get_file_metadata(file_id, file_name.replace("-"," "))
            except DatabaseError:
                error=503
            except FileNotExist:
                error=404
            except (FileRemoved, FileFoofindRemoved, FileNoSources):
                error=410
            except FileUnknownBlock:
                error=404

            if error is None and not file_data: #si no ha habido errores ni hay datos, es porque existe y no se ha podido recuperar
                error=503

    if error:
        abort(error)

    # completa datos de torrent
    file_data = torrents_data(file_data, True)
    if not file_data:
        abort(404)

    # no permite acceder ficheros que deberian ser bloqueados
    blacklists = g.blacklists
    prepared_phrase = blacklists.prepare_phrase(file_data['view']['nfn'])
    if prepared_phrase in blacklists["forbidden"] or (prepared_phrase in blacklists["misconduct"] and prepared_phrase in blacklists["underage"]):
        g.blacklisted_content = "File"
        if not g.show_blacklisted_content:
            abort(404)

    query = download_search(file_data, file_name, "torrent")
    related = single_search(query, category=None, title=("Related torrents",3,None), zone="File / Related", last_items=[], limit=30, max_limit=15, ignore_ids=[mid2hex(file_id)], show_order=None)

    # elige el titulo de la página
    title = file_data['view']['fn']

    # recorta el titulo hasta el proximo separador
    if len(title)>101:
        for pos in xrange(101, 30, -1):
            if title[pos] in SEPPER:
                title = title[:pos].strip()
                break
        else:
            title = title[:101]

    g.title = title

    page_description = ""
    if "description" in file_data["view"]["md"]:
        page_description = file_data["view"]["md"]["description"].replace("\n", " ")

    if not page_description:
        page_description = "Download %s torrents from %s" % (file_data["view"]['file_type'].capitalize() if file_data["view"]['file_type'] != "unknown" else "All", g.domain_capitalized)

    if len(page_description)<50:
        if page_description:
           page_description += ". "
        page_description += " ".join(text.capitalize()+"." for text in related[1]["files_text"])

    if len(page_description)>180:
        last_stop = page_description[:180].rindex(".") if "." in page_description[:180] else 0
        if last_stop<100:
            last_stop = page_description[:180].rindex(" ") if " " in page_description[:180] else 0
        if last_stop<100:
            last_stop = 180
        page_description = page_description[:last_stop]+"."

    g.page_description = page_description

    is_canonical_filename = file_data["view"]["seo-fn"]==file_name

    # registra visita al fichero
    if g.search_bot:
        searchd.log_bot_event(g.search_bot, True)
    else:
        save_visited([file_data])

    if related[0]:
        g.must_cache = 3600

    return render_template('file.html', related_query = query, file_data=file_data, related_files=related, is_canonical_filename=is_canonical_filename, featured=get_featured(related[1]["count"]+len(file_data["view"]["md"]), 1))

@files.route('/copyright', methods=["GET","POST"])
def copyright():
    '''
    Muestra el formulario para reportar enlaces
    '''
    g.category = False
    g.page_description = "%s is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place." % g.domain_capitalized
    g.keywords.clear()
    g.keywords.update(["torrents search engine popular largest copyright"])
    g.title+=" | Copyright"
    form = ComplaintForm(request.form)
    if request.method=='POST':
        if "file_id" in request.form:
            try:
                file_id = request.form["file_id"]
                file_name = request.form.get("file_name",None)
                data = torrents_data(get_file_metadata(url2mid(file_id), file_name))
                if data:
                    form.urlreported.data=url_for("files.download",file_id=file_id,file_name=file_name,_external=True)
                    form.linkreported.data=data['view']["sources"]["tmagnet"]["urls"][0] if "tmagnet" in data['view']["sources"] else data['view']["sources"]["download"]["urls"][0] if "download" in data['view']["sources"] else data['view']["sources"]["download_ind"]["urls"][0]
            except BaseException as e:
                logging.exception(e)
        elif form.validate():
            pagesdb.create_complaint(dict([("ip",request.remote_addr)]+[(field.name,field.data) for field in form]))
            flash("Message sent successfully!")
            return redirect(url_for('index.home'))
    return render_template('copyright.html',form=form)

def get_last_items():
    last_items = []
    try:
        last_items = urlsafe_b64decode(str(request.args.get("p","")))
        if last_items:
            last_items = unpack("%dh"%(len(last_items)/2), last_items)
    except BaseException as e:
        last_items = []
        logging.error("Error parsing last_items information from request.")

    return last_items

def single_search(query, category=None, not_category=None, order=None, title=None, zone="", query_time=800, skip=None, last_items=[], limit=70, max_limit=50, ignore_ids=[], show_order=None):
    if (query and (len(query)>=WORD_SEARCH_MIN_LEN or query in NGRAM_CHARS)) or category:
        s = searchd.search((query+u" " if query else u"")+(u"("+category+")" if category else u"")+(u" -("+not_category+")" if not_category else u""), None, order=order, start=not skip, group=not skip, no_group=True)

        return process_search_results(s, query, category, not_category, zone=zone, title=title, last_items=last_items, skip=skip, limit=limit, max_limit=max_limit, ignore_ids=ignore_ids, show_order=show_order)
    else:
        return process_search_results(None, query, category, zone=zone, title=title, last_items=last_items, skip=skip, limit=limit, max_limit=max_limit, ignore_ids=ignore_ids, show_order=show_order)

def multi_search(params, query_time=500, extra_wait_time=500):
    searches = [(searchd.search((query+u" " if query else u"")+(u"("+category+")" if category else u"")+(u" -("+not_category+")" if not_category else u""), None, order=order, start=True, group=True, no_group=True), query, category, not_category, zone, title, limit, max_limit, show_order) for query, category, not_category, order, zone, title, limit, max_limit, show_order in params]

    for s, query, category, not_category, zone, title, limit, max_limit, show_order in searches:
        yield process_search_results(s, query, category, not_category, zone=zone, title=title, limit=limit, max_limit=max_limit, show_order=show_order)


def process_search_results(s=None, query=None, category=None, not_category=None, title=None, zone="", last_items=[], skip=None, limit=70, max_limit=50, ignore_ids=[], show_order=True):
    files = []
    files_text = []
    files_dict = None
    results = None
    must_cache = True
    if not title:
        title = (None, 2, False)

    if s:
        ids = [result for result in ((bin2hex(fileid), server, sphinxid, weight, sg) for (fileid, server, sphinxid, weight, sg) in s.get_results((3.0, 0.1), last_items=last_items, skip=skip*100 if skip else None, min_results=limit, max_results=limit, extra_browse=limit, weight_processor=weight_processor, tree_visitor=tree_visitor)) if result[0] not in ignore_ids]

        results_entities = list(set(int(aid[4])>>32 for aid in ids if int(aid[4])>>32))
        ntts = {int(ntt["_id"]):ntt for ntt in entitiesdb.get_entities(results_entities)} if results_entities else {}
        stats = s.get_stats()
        canonical_query = stats["ct"]

        if canonical_query:
            # elimina categoria y no categoria de la busqueda canonica
            canonical_query_parts = [part for part in canonical_query.split("_") if not ((not_category and part==u"-("+not_category+")")
                                                                                        or (category and part==u"("+category+")"))]

            canonical_query = "_".join(canonical_query_parts) if any(len(part)>=WORD_SEARCH_MIN_LEN or part in NGRAM_CHARS for part in canonical_query_parts) else ""

        sure = stats["s"]
        if (not sure) or ("total_sure" in stats and not stats["total_sure"]):
            g.must_cache = 0
            cache.cacheme = False
    else:
        sure = True
        canonical_query = ""

    # no realiza busquedas bloqueadas
    if canonical_query:
        blacklists = g.blacklists
        #si la query exacta está en underage no se muestra nada
        safe_phrase = canonical_query.replace("_"," ").strip()
        #Si solo la incluye ya tiene que completar con misconduct
        prepared_phrase = blacklists.prepare_phrase(safe_phrase)

        if blacklists["underage"].exact(safe_phrase) or prepared_phrase in blacklists["forbidden"] or prepared_phrase in blacklists["searchblocked"] or (prepared_phrase in blacklists["misconduct"] and prepared_phrase in blacklists["underage"]):
            g.blacklisted_content = "Search"

    # si la canonical query es vacia, solo interesan resultados para busquedas con query nulo (rankings)
    if (g.show_blacklisted_content or not g.blacklisted_content) and (canonical_query or not query):
        if ids:
            files_dict={str(f["_id"]):prepare_data(f,text=query,ntts=ntts) for f in get_files(ids,s)}
            # ordena resultados y añade informacion de la busqueda
            position = 0
            for search_result in ids:
                fid = search_result[0]
                if fid in files_dict and files_dict[fid]:
                    afile = files_dict[fid]
                    afile["search"] = search_result
                    files.append(afile)
                    files_text.append(afile["view"]["nfn"])


                    featured_weight = (afile['view']["rating"]
                                        + (3 if 'images_server' in afile['view'] or 'thumbnail' in afile['view'] else 0)
                                        + (4 if all(cat.show_in_home for cat in afile["view"]["categories"]) else 0))

                    g.featured.append((-featured_weight, position, afile))

                    position-=1

            results = render_template('results.html', files=files[:max_limit or limit], list_title=title[0] or query or category, title_level=title[1], title_class=title[2], zone=zone, show_order=show_order)

        count = min(len(files), max_limit or limit)
        search_info = {"time": max(stats["t"].itervalues()) if stats["t"] else 0, "total_found": stats["cs"],
                   "count": count, "next": False if "end" in stats and stats["end"] or skip>=10 else (skip or 0)+1, "files_text":files_text, "canonical_query":canonical_query, "sure":sure}
    else:
        search_info = {"time": 0, "total_found": 0, "count": 0, "next": False, "files_text":[], "canonical_query":"-", "sure":sure}

    # intenta evitar problemas de memoria
    del files

    return results, search_info

def prepare_data(f, text=None, ntts=[], details=False):
    try:
        return torrents_data(secure_fill_data(f,text,ntts), details)
    except BaseException as e:
        logging.error("Error retrieving torrent data.")
        return None

NULL_DATE = datetime.datetime.fromtimestamp(0)
URL_DETECTOR = re.compile(r"(http://[^ \n,\[\(]+)")
TRAILER_DETECTOR = re.compile(r"(http://(?:www.)?youtube.com[^ \n,\[]+)")
IMDB_DETECTOR = re.compile(r"(http://(?:www.)?imdb.com[^ \n,\[]+)")

def get_video_id(value):
    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    try:
        query = urlparse(value.replace("&amp;","&"))
        if query.hostname == 'youtu.be':
            return query.path[1:]
        if query.hostname in ('www.youtube.com', 'youtube.com'):
            if query.path == '/watch':
                p = parse_qs(query.query)
                return p['v'][0]
            if query.path[:7] == '/embed/':
                return query.path.split('/')[2]
            if query.path[:3] == '/v/':
                return query.path.split('/')[2]
    except BaseException as e:
        logging.exception(e)

    return None

def torrents_data(data, details=False):
    valid_torrent = False
    providers = []

    if not data or not "sources" in data["view"]:
        return None

    for source in data["view"]["sources"].keys():
        if source == "tmagnet":
            valid_torrent = True
        elif data["view"]["sources"][source]["icon"]=="torrent":
            valid_torrent = True
            providers.append(source)
            if u"i" in data["view"]["sources"][source]["g"]:
                data["view"]["sources"]["download_ind"] = data["view"]["sources"][source]
            else:
                data["view"]["sources"]["download"] = data["view"]["sources"][source]

    # no tiene origenes validos
    if not valid_torrent:
        return None

    desc = None

    #downloader
    if data['view']['sources'][data['view']['source']]['downloader'] == 1 and request.user_agent.platform != "windows":
        #lo desactiva para los no windows
        data['view']['sources'][data['view']['source']]['downloader'] = 0

    # organiza mejor la descripcion del fichero
    if details and "description" in data["view"]["md"]:

        # recupera la descripcion original
        desc = data["view"]["md"]["description"]
        del data["view"]["md"]["description"]

        # inicializa variables
        long_desc = False
        short_desc = None
        acum = []

        # recorre las lineas de la descripcion
        for line in desc.split("\n"):
            # elimina enlaces
            line = URL_DETECTOR.sub("", line)

            # si llega a pasar despues acumular algo, hay que mostrar la desc larga
            if acum:
                long_desc = True

            # ignora lineas con muchos caracteres repetidos
            prev_char = repeat_count = 0
            for char in line:
                if prev_char==char:
                    repeat_count+=1
                else:
                    repeat_count = 0
                if repeat_count>5:
                    line=""
                    break
                prev_char = char

            # si la linea es "corta", la toma como fin de parrafo
            if len(line)<50:
                if acum:
                    if line: acum.append(line)

                    # si el parrafo es mas largo que 110, lo usa
                    paraph = " ".join(acum)
                    acum = [] # antes de seguir reinicia el acum
                    paraph_len = len(paraph)
                    if paraph_len>90:
                        short_desc = paraph
                        if paraph_len>140: # si no es suficientemente larga sigue buscando
                            break
                    continue
            else: # si no, acumula
                acum.append(line)

        # procesa el parrafo final
        if acum:
            paraph = " ".join(acum)
            paraph_len = len(paraph)
            if paraph_len>90:
                short_desc = paraph

        # si hay descripcion corta se muestra y se decide si se debe mostrar la larga tambien
        if short_desc:
            data["view"]["md"]["short_desc"] = short_desc
            long_desc = long_desc or len(short_desc)>400
        else:
            long_desc = True

        if not long_desc and "nfo" in data["file"]["md"]:
            desc = data["file"]["md"]["nfo"]
            long_desc = True

        if long_desc and short_desc!=desc:
            if len(desc)>400:
                data["view"]["md"]["long_desc"] = desc
            else:
                data["view"]["md"]["description"] = desc

    # preview
    if "torrent:thumbnail" in data["file"]["md"]:
        data["view"]["thumbnail"] = data["file"]["md"]["torrent:thumbnail"]

    # tags del fichero
    file_tags = data["view"]["tags"] if "tags" in data["view"] else []
    file_category = file_category_type = None
    file_categories = []
    for category in g.categories:
        if category.tag in file_tags:
            if not file_category:
                file_category = category
            file_categories.append(category)
        if not file_category_type and category.content_main and category.content==data["view"]["file_type"]:
            file_category_type = category

    data["view"]["category"] = file_category
    data["view"]["categories"] = file_categories
    data["view"]["category_type"] = file_category_type

    has_trailer = data["view"]["has_trailer"] = file_category and (file_category.url in ["movies", "games"])

    if desc:
        if has_trailer:
            trailer = TRAILER_DETECTOR.findall(desc)
            youtube_id = get_video_id(trailer[0]) if trailer else None
            if youtube_id:
                data["view"]["trailer_link"] = "http://www.youtube.com/embed/%s?autoplay=1"%youtube_id

        imdb = IMDB_DETECTOR.findall(desc)
        if imdb:
            data["view"]["imdb_link"] = imdb[0]

    # salud del torrent
    try:
        seeds = int(float(data['view']['md']['seeds'])) if 'seeds' in data['view']['md'] else 0
    except:
        seeds = 0
    try:
        leechs = int(float(data['view']['md']['leechs'])) if 'leechs' in data['view']['md'] else 0
    except:
        leechs = 0
    data['view']['health'] = int(2/(leechs+1.)) if seeds==0 else min(10,int(seeds/(leechs+1.)*5))
    data['view']['rating'] = int((data['view']['health']+1)/2)

    data["view"]["icon"] = file_category or file_category_type or CATEGORY_UNKNOWN
    data["view"]["providers"] = providers
    data["view"]["seo-fn"] = seoize_text(data["view"]["fn"], "-", True)

    return data

@cache.memoize(timeout=60*60)
def get_rankings():
    rs = current_app.config["RANKING_SIZE"]
    categories_len = len(g.categories)
    return zip(
        multi_search(
            (None, category.tag, "porn", RANKING_ORDER, "Home / " + category.title, ("<a href='%s'>%s torrents</a>"%
                (url_for("files.category",category=category.url),singular_filter(category.title)), 3, category.url),
            rs*2, rs, None) for category in g.categories if category.show_in_home),
        (category for category in g.categories if category[-1])), get_featured(rs*categories_len,categories_len)

def save_visited(files):
    if not g.search_bot:
        result=[{"_id": afile['view']['sources']["download"]['urls'][0] if "download" in afile['view']['sources'] else
                        afile['view']['sources']["download_ind"]['urls'][0]}
                    for afile in files
                        if "download" in afile['view']['sources'] or "download_ind" in afile['view']['sources']]
        if result:
            try:
                feedbackdb.visited_links(result)
            except:
                pass

from flask.ext.wtf import Form, BooleanField, PasswordField, TextField, TextAreaField, SelectField, FileField, FieldList, SubmitField, ValidationError, Regexp, Required, URL, Email, RecaptchaField
class ComplaintForm(Form):
    '''
    Formulario para reportar enlaces
    '''
    name = TextField("Name", [Required("Required field.")])
    surname = TextField("Surname", [Required("Required field.")])
    company = TextField("Company")
    email = TextField("Email", [Required("Required field."),Email("Invalid email.")])
    phonenumber = TextField("Phone")
    linkreported = TextField("Link reported", [Required("Required field."),Regexp("^(?!http://[^/]*torrents.(com|is|ms|fm|ag)/?.*).*$",re.IGNORECASE,"Link URL can't be from Torrents.")])
    urlreported = TextField("Torrents URL", [Required("Required field."),URL("Torrents URL must be a valid URL."),Regexp("^http://torrents.(com|is|ms|fm|ag)/",re.IGNORECASE,"The link must be a Torrents page.")])
    reason = TextField("Complaint reason", [Required("Required field.")])
    message = TextAreaField("Message", [Required("Required field.")])
    captcha = RecaptchaField()
    accept_tos = BooleanField(validators=[Required("Required field.")])
    submit = SubmitField("Submit")
