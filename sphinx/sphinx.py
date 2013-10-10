#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import environ
environ["FOOFIND_NOAPP"] = "1"

import signal, sys

# carga Foofind de la carpeta padre
import pymongo
from collections import Counter, defaultdict
from heapq import nlargest

from os.path import dirname, abspath, exists
sys.path.insert(0,dirname(dirname( abspath(__file__))))
sys.path.insert(0,dirname( abspath(__file__)))

import xmlpipe2
from foofind.utils.splitter import split_phrase, SEPPER
from foofind.utils import u, hex2mid, logging
from foofind.utils.seo import seoize_text
from foofind.utils.content_types import *
from foofind.utils.filepredictor import guess_doc_content_type
from foofind.datafixes import content_fixes
from hashlib import md5
from functools import partial
from itertools import imap, chain
from operator import mul
from math import log
from time import time, mktime
from struct import unpack, Struct, pack
import json
import argparse, os
from raven import Client
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging

import foofind.defaults
config = foofind.defaults.__dict__.copy()

all_langs = {l:i for i,l in enumerate(config["ALL_LANGS"])}
sources_groups = {"s":"%sstreaming"%FILTER_PREFIX_SOURCE_GROUP, "w":"%sdownload"%FILTER_PREFIX_SOURCE_GROUP,
                  "p":"%sp2p"%FILTER_PREFIX_SOURCE_GROUP, "t":"%storrent"%FILTER_PREFIX_SOURCE_GROUP}

PHRASE_SEPARATOR = u"\u2026"
separator_join = PHRASE_SEPARATOR.join
space_join = " ".join
langsrange = range(16)
now = time()
current_id = "None"

extra_rating_md = frozenset({"video:series", "book:title", "audio:title", "video:director", "video:year", "video:lang", "video:subs"})

numeric_filters = {"video:season":FILTER_PREFIX_SEASON, "video:episode":FILTER_PREFIX_EPISODE, "audio:year":FILTER_PREFIX_YEAR, "video:year":FILTER_PREFIX_YEAR}


dictget = dict.get
def innergroup_hash(field_path, afile):
    return hash(u(reduce(dictget, field_path, afile)) or "")

def get_definitions():
    fields = [
            {"name":"fn", "field": "_fns", "field_type": unicode },
            {"name":"md", "field": "_md", "field_type": unicode },
            {"name":"fil", "field": "_fil", "field_type": str },
            {"name":"ntt", "field": "_ntts", "field_type": str }
        ]
    attrs = [
            {"name":"fs", "type":"timestamp",                  # First Seen
                "field": "_fs",
                "field_type": int
            },
            {"name":"z", "type":"float",                       # Size log
                "field": "_z",
                "field_type": float
            },
            {"name":"uri1", "type":"int", "bits":32,           # MongoId 1
                "field": "_uri0",
                "field_type": int
            },
            {"name":"uri2", "type":"int", "bits":32,           # MongoId 2
                "field": "_uri1",
                "field_type": int
            },
            {"name":"uri3", "type":"int", "bits":32,           # MongoId 3
                "field": "_uri2",
                "field_type": int
            },
            {"name":"l", "type":"int", "bits":16,              # Length
                "field": "_l",
                "field_type": int
            },
            {"name":"va", "type":"int", "bits":16, "default":0,# Votes flags A
                "field": "_va",
                "field_type": int
            },
            {"name":"vb", "type":"int", "bits":16, "default":0,# Votes flags B
                "field": "_vb",
                "field_type": int
            },
            {"name":"vc", "type":"int", "bits":8, "default":42,# Votes C
                "field": "_vc",
                "field_type": int
            },
            {"name":"vd", "type":"int", "bits":8, "default":127,# Votes D
                "field": "_vd",
                "field_type": int
            },
            {"name":"bl", "type":"int", "bits":2, "default":0, # Blocked
                "field": False,
                "field_type": None
            },
            {"name":"ct", "type":"int", "bits":4, "default":0, # Content Type
                "field": "_ct",
                "field_type": int
            },
            {"name":"r2", "type":"int", "bits":8, "default":0, # Secondary rating
                "field": "_r2",
                "field_type": int
            },
            {"name":"r", "type":"float", "default":-1,          # Rating
                "field": "_r",
                "field_type": float
            },
            {"name":"s", "type":"multi",                       # Source type
                "field": "_s",
                "field_type": list
            },
            {"name":"g", "type":"bigint",                      # Group
                "field": "_g",
                "field_type": long
            }
        ]
    return (fields, attrs)

def get_url_part(url, t):
    if "url_lastparts_indexed" in sources[t]:
        url_lastparts_indexed = int(sources[t]["url_lastparts_indexed"])
        return "/".join(url[5:].split("?")[0].split("/")[-url_lastparts_indexed:]) if url_lastparts_indexed > 0 else ""
    else:
        return url[5:]

afile_struct = Struct('III')
# Calculate info for file
def init_file(afile):
    global current_id

    # gets file's id
    current_id = file_id = str(afile["_id"])

    # fixes a contenidos
    try:
        content_fixes(afile)
    except BaseException as e:
        logging.exception("Error fixing content file %s."%file_id)

    # entidades semanticas
    if "se" in afile and afile["se"] and "_id" in afile["se"]:
        try:
            entity = int(afile["se"]["_id"])
            if "rel" in afile["se"]:
                rels = afile["se"]["rel"]
                afile["_ntts"] = u"%04d%s%s"%(entity, PHRASE_SEPARATOR*10 + space_join(str(ntt_id).rjust(4,"0")+ntt_rel for ntt_id, ntt_rel in rels[0]) if rels[0] else "", PHRASE_SEPARATOR*(10-len(rels[0])/10) + space_join(str(ntt_id).rjust(4,"0")+ntt_rel for ntt_id, ntt_rel in rels[1]) if rels[1] else "")
        except ValueError:
            logging.exception("Error parsing entity id %s for file %s."%(str(afile["se"]["_id"]), file_id))
            entity = 0
        except:
            logging.exception("Error generating entity metadata for file %s."%file_id)
            entity = 0
    else:
        entity = 0

    md = afile["md"]

    # tipos del fichero
    src = afile["src"]
    types = {int(s["t"]) for uri, s in src.iteritems() if "t" in s and s["t"] in sources}
    if not types: return False
    isP2P = any(u"p" in sources[t]["g"] for t in types)

    # valores dependientes de tipos
    torrent_ct = None
    if not isP2P:
        return False

    trackers = md["torrent:trackers"] if "torrent:trackers" in md else 1 if "torrent:tracker" in md else 0
    if isinstance(trackers, basestring): trackers = trackers.count(" ")

    # mira si es fichero Torrent o Torrent Hash
    main_type = 7 if 7 in types and len(types)==1 else 3

    seeds = int(md["torrent:seeds"]) if "torrent:seeds" in md and 0<=md["torrent:seeds"]<500000 else False
    leechs = int(md["torrent:leechs"]) if "torrent:leechs" in md and 0<=md["torrent:leechs"]<500000 else False
    afile["_r"] = 2/(leechs+1.) if seeds==0 else (min(10,int(seeds/(leechs+1.)*5))+(seeds/500000.)) if seeds!=False else False
    inner_group = 0

    # rating secundario
    r2 = False

    # los errores votos no deben afectar a la indexación del fichero
    try:
        if "vs" in afile and afile["vs"]: # ficheros con votos
            votes = {all_langs[lang]:log(val["c"][0]+5, val["c"][1]*2+5) for lang, val in afile["vs"].iteritems()}
            m, M = min(0.9, min(votes.itervalues())), min(max(1.1,max(votes.itervalues())), 3.0)

            e = (m*2-M*0.5)/(M-m) # valores de 0-6
            f = M/(2+e)           # valores de 0-2

            vc = int(e*42)
            vd = int(f*127)

            vabs = {l:min((abs(v-(a-0.5*b+vc/42)*vd/127),str(a),str(b)) for a,b in [(0,0),(0,1),(1,0),(1,1)]) for l,v in votes.iteritems()}
            afile["_va"] = int("".join(str(vabs[i][1]) if i in vabs else "0" for i in langsrange),2)
            afile["_vb"] = int("".join(str(vabs[i][2]) if i in vabs else "0" for i in langsrange),2)
            afile["_vc"] = vc
            afile["_vd"] = vd

        elif "cs" in afile and afile["cs"]: # ficheros sin votos pero con comentarios aumenta el rating secundario
            r2 = 2
    except BaseException as e:
        logging.exception("Error processing votes from file %s."%file_id)

    # rating secundario
    if "i" in afile and isinstance(afile["i"],list): r2=(r2 or 1)*2  # ficheros con imagenes
    afile["_r2"] = r2

    # uri del fichero
    afile["_uri0"], afile["_uri1"], afile["_uri2"] = afile_struct.unpack(afile['_id'].binary)

    fs = afile["date"] if "date" in afile else afile["fs"]
    fs = long(mktime(fs.timetuple()))
    if fs<now: afile["_fs"] = fs

    fns = nlargest(5, ((sum(sfn["fn"][crc]["m"] if "fn" in sfn and crc in sfn["fn"] else 0 for sfn in src.itervalues()), fn) for crc,fn in afile["fn"].iteritems()))
    afile["_fns"] = separator_join(f[1]["n"]+("."+(f[1].get("x",None) or "")) for f in fns)

    res = [[seoize_text(f[1]["n"], separator=" ", is_url=False, max_length=100, min_length=20)] for f in fns]

    # informacion del contenido
    ct, file_tags, file_format = guess_doc_content_type(afile, sources)
    afile["_ct"] = ct

    '''# tags del fichero
    file_category = file_category_type = None
    for category in config["TORRENTS_CATEGORIES"]:
        if category.tag in file_tags and (not file_category or category.tag=="porn"): # always use adult when its present
            file_category = category.cat_id

        if category.content_main and category.content==ct:
            file_category_type = category.cat_id
    afile["_ct"] = file_category or file_category_type'''

    # tamaño
    try:
        z = float(afile["z"]) if "z" in afile and afile["z"] else False
    except:
        z = False

    if ct == CONTENT_VIDEO:
        try:
            l = int(float(md["video:duration"])) if "video:duration" in md else \
                int(float(md["video:length"])) if "video:length" in md else \
                sum(imap(mul, [int(float(part)) for part in ("0:0:0:" + str(md["length"])).split(":")[-4:]], [216000, 3600, 60, 1])) if "length" in md else \
                60*int(float(md["video:minutes"])) if "video:minutes" in md else \
                False
        except:
            l = False
        try:
            bitrate = int(str(md["bitrate"]).replace('~','')) if "bitrate" in md else 1280 # bitrate por defecto para video
        except:
            bitrate = False

    elif ct == CONTENT_AUDIO:
        try:
            l = int(float(md["audio:seconds"])) if "audio:seconds" in md else \
                sum(imap(mul, [int(float(part)) for part in ("0:0:0:" + str(md["length"])).split(":")[-4:]], [216000, 3600, 60, 1])) if "length" in md else \
                False
        except:
            l = False
        try:
            bitrate = int(str(md["bitrate"]).replace('~','')) if "bitrate" in md else 1280 # bitrate por defecto para video
        except:
            bitrate = False

    else:
        bitrate = l = False

    if z<1: z = False
    if l<1: l = False

    if bitrate:
        if l and not z: z = l*(bitrate<<7) # bitrate en kbps pasado a Kbps
        elif z and not l: l = z/(bitrate<<7)

    afile["_l"] = int(l) if 0<int(l)<0xFFFF else False
    afile["_z"] = log(z,2) if z else False

    # metadatos
    mds = chain(chain(*res), chain(value for key,value in md.iteritems() if key in GOOD_MDS and isinstance(value, basestring) and len(value)<=GOOD_MDS[key]))
    afile["_md"] = separator_join(amd for amd in mds if amd)

    # origenes
    afile["_s"] = [unicode(t) for t in types]

    # filtros de texto
    filters = {FILTER_PREFIX_CONTENT_TYPE+CONTENTS[ct]}
    filters.update(sources_domains[t] for t in types if sources[t]["d"])
    filters.update(sources_groups[g] for t in types for g in sources[t]["g"] if g in sources_groups)
    filters.update("%s%02d"%(prefix,int(md[key])) for key, prefix in numeric_filters.iteritems() if key in md and (isinstance(md[key], int) or isinstance(md[key], float) or (isinstance(md[key], basestring) and md[key].isdecimal())))
    filters.update("%s%s"%(FILTER_PREFIX_TAGS, tag) for tag in file_tags)
    if file_format: filters.add(FILTER_PREFIX_FORMAT+file_format[0])

    afile["_fil"] = " ".join(filters)

    # grupos
    afile["_g"] = ((entity << 32) |
                   (((afile["_ct"] or 0)&0xF) << 28) |
                   ((main_type & 0xFFFF) << 12) |
                   (inner_group & 0xFFF))

    return True


def file_stats(afile, stats):
    # estadisticas
    g = str(afile["_g"]&0xFFFFFFFF)
    gcount = stats["sg"][g]
    stats["sg"][g]=gcount+1

    # rating

    # solo tiene en cuenta los ratings válidos
    if afile["_r"] and afile["_r"]>=0:
        r = afile["_r"]
        grcount = stats["rc"][g]
        stats["rc"][g] = grcount+1
        if r>stats["rM"][g]: stats["rM"][g] = r

        delta = r-stats["ra"][g]
        stats["ra"][g]+=delta/(grcount+1.0)
        stats["rpa"][g]+=delta*(r-stats["ra"][g])

    # tamaño
    if afile["_z"]:
        z = afile["_z"]
        stats["z"][str(int(z))]+=1
        gzcount = stats["zc"][g]
        stats["zc"][g] = gzcount+1

        delta = z-stats["za"][g]
        stats["za"][g]+=delta/(gzcount+1.0)
        stats["zpa"][g]+=delta*(z-stats["za"][g])

    # duracion
    if afile["_l"]:
        l = afile["_l"]
        stats["l"][str(l/10)]+=1
        glcount = stats["lc"][g]
        stats["lc"][g] = glcount+1

        delta = l-stats["la"][g]
        stats["la"][g]+=delta/(glcount+1.0)
        stats["lpa"][g]+=delta*(l-stats["la"][g])

def fav_stats(afile, stats):
    pass

def main(processes, part, server, xml_file, fileid, favs, stats_update):
    global sources, sources_innergroups, sources_domains, counters

    batch_size = 1024*10

    setup_logging(SentryHandler(Client(config["SENTRY_SPHINX_DNS"])))
    fields, attrs = get_definitions()

    if favs:
        attrs.append(
            {"name":"list", "type":"str", "bits":64,              # Group
                "field": "_g"
            })

    sources = {int(float(s["_id"])):s for s in server_conn.foofind.source.find({"$or": [{"crbl": { "$exists" : False } }, {"crbl":0}]})}
    sources_domains = {source_id:"%s%s"%(FILTER_PREFIX_SOURCE, source["d"].lower().replace(".","")) for source_id, source in sources.iteritems()}

    g = globals()
    def get_function(i):
        if not (i in sources and "ig" in sources[i]): return None
        try:
            ig = sources[i]["ig"]
            return partial(g["innergroup_%s"%ig[0]], *ig[1:])
        except:
            return None
    sources_innergroups = [None]+[get_function(i+1) for i in xrange(0,max(sources.iterkeys()))]

    if not server:
        servers = server_conn.foofind.server.find_one({"_id":part})
        server = "mongodb://%s:%d"%(servers["ip"],servers["p"])
    ntts_server = config["DATA_SOURCE_ENTITIES"]

    xmlpipe2.set_globals(fields, attrs, init_file, fav_stats if favs else file_stats)

    incremental_index = False
    if favs:
        counters.append(0)
        user_conn = pymongo.Connection(config["DATA_SOURCE_USER"])
        xml = xmlpipe2.XmlPipe2(processes, fields, attrs, None, generate_fav_id)
        xml.generate_header()
        for doc in user_conn.foofind.favfile.find({"files.server":part}):
            if not doc.get("files", None): continue
            counters[0] = 0
            files_filter = {"_id":{"$in":[f["id"] for f in doc["files"]]}}
            xml.generate(server, ntts_server, (doc["name"], doc["user_id"] << 24, part << 16), files_filter, batch_size, headers=False)
        xml.generate_footer()
        user_conn.end_request()
    else:
        counters.extend((0,)*2**16) # 16 bits del hash hacen el contador
        files_filter = {'bl': 0}
        if fileid: files_filter["_id"] = hex2mid(fileid)

        stats = {"_id": part, "sg":defaultdict(int), "z":defaultdict(int), "l":defaultdict(int), "lc":defaultdict(int), "la":defaultdict(float), "lpa":defaultdict(float), "zc":defaultdict(int), "za":defaultdict(float), "zpa":defaultdict(float), "ra":defaultdict(float), "rpa":defaultdict(float), "rM":defaultdict(float), "rc":defaultdict(int)}

        if xml_file:
            if exists(xml_file):
                incremental_index = True
                line = last_line(xml_file)
                counters, stop_set, saved_stats, last_count = json.loads(line[4:-3])
                stop_set = set(stop_set)
                stop_set_len = len(stop_set)

                for key, value in saved_stats.iteritems():
                    if isinstance(value, defaultdict):
                        stats[key].update(value)
            else:
                # primer fichero
                stop_set = set()
                stop_set_len = 10
                last_count = 0

            xml = xmlpipe2.XmlPipe2(processes, fields, attrs, stats, generate_id)

            # genera cabeceras para el primer fichero
            if not incremental_index:
                xml.generate_header()
            new_stop_set = xml.generate(server, ntts_server, part<<16, files_filter, batch_size, stop_set=stop_set, stop_set_len=stop_set_len, last_count=last_count, headers=False)

            # solo imprime estado si ha añadido algun fichero
            if xml.count:
                print "\n<!--%s-->"%json.dumps((counters, list(new_stop_set), stats, xml.total_count)),

        else:
            xml = xmlpipe2.XmlPipe2(processes, fields, attrs, stats, generate_id)
            xml.generate(server, ntts_server, part<<16, files_filter, batch_size)

        if stats_update and not incremental_index:
            server_conn.foofind.search_stats.insert({"_id":part, "d0":time(), "d1":time()})
            server_conn.foofind.search_stats.update({"_id":part}, {"$set":stats})
            server_conn.foofind.server.update({"_id":part},{"$set":{"ss":0}})

counters = []

id_struct = Struct(">Q")
h_struct = Struct("H")
def generate_id(afile, part):
    binary_id = afile["_id"].binary[:5]
    counter, = h_struct.unpack(binary_id[:2])
    counters[counter]+=1
    if counters[counter]>0x10000:
        logging.warn("Counter overflow: %s" % hex(counter))
        counters[counter] = 1
    return id_struct.unpack(binary_id+"\0\0\0")[0]+part+counters[counter]-1, afile

def generate_fav_id(afile, (list_name, part1, part2)):
    counters[0] += 1
    afile["_listname"] = list_name
    return part1 + part2 + counters[0], afile


def last_line(path):
    '''
    Devuelve la última línea de un fichero.

    @type path: str
    @param path: ruta del fichero

    @rtype str
    @return línea pedida
    '''
    f = open(path, "r")
    linesep = f.newlines or os.linesep
    f.seek(0, os.SEEK_END)
    size = f.tell()

    data = []

    for pos in xrange(-1024, -size, -1024):
        # Voy recorriendo hacia atrás y leyendo a trozos hasta tener
        # suficientes líneas.
        f.seek(pos-1, os.SEEK_END) # evita el salto de linea final del fichero
        data.append(f.read(1024))
        if data[-1].count(linesep):
            break
    else:
        # Si he terminado el documento sin tener todas las líneas, añado
        # lo que resta (que no entra en los trozos).
        if 1024 * len(data) < size:
            f.seek(0, os.SEEK_SET)
            data.append( f.read(size % 1024) )

    f.close()
    data.reverse()

    return "".join(data).split(linesep)[-1]


def signal_handler(signal, frame):
    logging.warn("Process killed processing file %s." % current_id)
    sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Index data for a sphinx server.')
    parser.add_argument('processes', type=int, help='Number of processes')
    parser.add_argument('part', type=int, help='Server number.')
    parser.add_argument('--mode', type=str, default="admin", help='Configuration file to use.')
    parser.add_argument('--server', type=str, help='Server address. Default value is fetch from main database.', default=None)
    parser.add_argument('--xml', type=str, help='Last XML generated in incremental mode.', default=None)
    parser.add_argument('--fileid', type=str, help='Show output for a specific file.', default=None)
    parser.add_argument('--favs', action='store_true', help='Index favourites files.')
    parser.add_argument('--profile', action='store_true', help='Profiling mode.')
    parser.add_argument('--stats', action='store_true', help='Save stats when finish.')
    parser.add_argument('--refreshstats', action='store_true', help='Update stats date and exit.')

    params = parser.parse_args()

    settings_module = __import__(params.mode)
    config.update(settings_module.settings.__dict__)
    del config["__builtins__"]

    options = {"replicaSet": app.config["DATA_SOURCE_SERVER_RS"], "read_preference":pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED, "secondary_acceptable_latency_ms":app.config.get("SECONDARY_ACCEPTABLE_LATENCY_MS",15)} if "DATA_SOURCE_SERVER_RS" in app.config else {"slave_okay":True}
    server_conn = pymongo.MongoClient(config["DATA_SOURCE_SERVER"], max_pool_size=self.max_pool_size, **options)
    if params.refreshstats:
        server_conn.foofind.search_stats.update({"_id":part}, {"$set":{"d0":time(), "d1":time()}})
        exit()

    signal.signal(signal.SIGINT, signal_handler)
    if params.profile:
        import cProfile
        cProfile.run('main(%d, %d, %s, %s, %s, %s)' % (params.processes, params.part, repr(params.server), repr(params.xml), repr(params.fileid), repr(params.favs), repr(stats)))
    else:
        main(params.processes, params.part, params.server, params.xml, params.fileid, params.favs, params.stats)

