#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, chardet, codecs, math, pymongo, Queue, os, re
from foofind.utils import u, logging
from threading import Thread
from multiprocessing import Pool

class EntitiesFetcher(Thread):
    def __init__(self, server, results):
        super(EntitiesFetcher, self).__init__()
        self.daemon = True
        self.server = server
        self.results = results
        self.requests = Queue.Queue()

    def run(self):
        gconn = None
        not_found_count = 0
        with open("nf_ntts.csv", "w") as not_found_ntts:
            while True:
                # obtiene peticiones de buscar entidades
                afile = self.requests.get(True)
                if afile is None:
                    self.requests.task_done()
                    break

                if not gconn:
                    gconn = pymongo.Connection(self.server, slave_okay=True)

                try:
                    # busca la entidad principal
                    main_ntt_id = int(afile["se"]["_id"])
                    ntt = gconn.ontology.ontology.find_one({"_id":main_ntt_id})
                    ntts1_info = set()
                    ntts2_info = set()
                    if ntt:
                        afile["se"]["info"] = ntt
                        # busca entidades de primer y segundo nivel
                        if "r" in ntt and ntt["r"]:
                            # genera la lista de entidades y tipos de relacion de primer nivel
                            ntts1_info = {(ntt_id, relation[:3])
                                            for relation, relation_ids in ntt["r"].iteritems()
                                                for ntt_id in relation_ids if ntt_id!=main_ntt_id}

                            # si hay entidades de primer nivel...
                            if ntts1_info:
                                # obtiene entidades de primer nivel
                                ntts1_ids = [ntt_id for ntt_id, relation in ntts1_info]
                                ntts1 = list(gconn.ontology.ontology.find({"_id":{"$in":ntts1_ids}}))

                                # genera la lista de entidades y tipos de relacion de segundo nivel
                                ntts1_ids.append(main_ntt_id) # añade el id de la relacion para usar la lista como filtro
                                ntts2_info = {(ntt_id, relation[:3])
                                                for ntt2 in ntts1 if "r" in ntt2
                                                    for relation, relation_ids in ntt2["r"].iteritems()
                                                        for ntt_id in relation_ids if ntt_id not in ntts1_ids}

                        afile["se"]["rel"] = (ntts1_info, ntts2_info)
                    else:
                        not_found_ntts.write(str(afile["_id"])+"\n")
                        not_found_count += 1
                        del afile["se"]["_id"]
                except BaseException:
                    ntt_id = str(afile["se"]["_id"]) if "_id" in afile["se"] else "???"
                    del afile["se"]["_id"]
                    gconn.close()
                    gconn = None
                    logging.exception("Error obtaining entities for file %s: %s."%(str(afile["_id"]), ntt_id))

                self.results.put(afile)
                self.requests.task_done()

        if not_found_count:
            logging.warn("Entities not found for some files. Check file nf_ntts.csv.")

class FilesFetcher(Thread):
    def __init__(self, server, entities_server, filter, batch_size, stop_set, stop_set_len, last_count, processes):
        super(FilesFetcher, self).__init__()
        self.daemon = True
        self.server = server
        self.batch_size = batch_size
        self.results = Queue.Queue(batch_size*processes)
        self.filter = filter
        self.complete = False
        self.entities = EntitiesFetcher(entities_server, self.results)
        self.stop_set = stop_set
        self.stop_set_len = stop_set_len
        self.total_count = self.last_count = last_count

    def run(self):
        self.complete = False
        gconn = pymongo.Connection(self.server, slave_okay=True)
        gdb = gconn.foofind
        gfoo = gdb.foo

        self.entities.start()
        cursor = gfoo.find(self.filter, timeout=False).batch_size(self.batch_size)

        if self.stop_set_len:
            cursor = cursor.sort([("$natural",pymongo.DESCENDING)])
            new_stop_set = set()
            must_stop = add_to_stop_set = self.stop_set_len
            self.total_count = gfoo.count()
            count_limit = max(0,self.total_count-self.last_count)
            hard_limit = -100 - int(count_limit/1000.) # limite duro: 1 borrado cada mil ficheros más 100 fijos

        for f in cursor:
            if not 's' in f:
                f['s'] = 9
            if self.stop_set_len:
                # construye el nuevo stop set
                if add_to_stop_set:
                    new_stop_set.add(str(f["_id"]))
                    add_to_stop_set -= 1

                # comprueba el stop set actual
                if str(f["_id"]) in self.stop_set:
                    must_stop-=1
                    if must_stop==0:
                        break
                    else:
                        continue

                # limite por cantidad de ficheros
                count_limit += 1
                # para si ya ha recorrido el numero probable de ficheros y ha visto alguno del conjunto de parada
                # o si ha visto más del número limite de ficheros
                if count_limit<0 and must_stop<self.stop_set_len or count_limit<hard_limit:
                    if add_to_stop_set and self.stop_set:
                        new_stop_set.update(self.stop_set)
                    break

            if "se" in f and f["se"]:
                self.entities.requests.put(f)
            else:
                self.results.put(f)

        self.entities.requests.put(None)
        self.entities.requests.join()

        # actualiza el nuevo stop set
        if self.stop_set_len:
            self.stop_set = new_stop_set

        self.complete = True

    def __iter__(self):
        return self

    def next(self):
        while True:
            if self.results.empty() and self.complete:
                raise StopIteration
            try:
                return self.results.get(True, 3)
            except:
                pass

space_join = " ".join

XML_ILLEGAL_CHARS_RE = re.compile(u'[\x00-\x08<>\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')

def tag(_name, _children=None, separator="", children_type=None, **kwargs):
    if _children is False:
        return u""
    else:
        attr = (" " + space_join('%s="%s"' % (key, u(val)) for key, val in kwargs.iteritems() if val)) if kwargs else ""
        if _children:
            if children_type is list:
                return u"<%s%s>%s</%s>" % (_name, attr, separator.join(_children), _name)
            elif children_type is unicode:
                escaped_children = space_join(XML_ILLEGAL_CHARS_RE.split(u(_children)))
                if "&" in escaped_children:
                    return u"<%s%s><![CDATA[%s]]></%s>" % (_name, attr, escaped_children, _name)
                else:
                    return u"<%s%s>%s</%s>" % (_name, attr, escaped_children, _name)
            elif children_type is str:
                 return u"<%s%s>%s</%s>" % (_name, attr, _children, _name)
            elif children_type is float:
                 return u"<%s%s>%.8f</%s>" % (_name, attr, _children, _name)
            else:
                return u"<%s%s>%s</%s>" % (_name, attr, unicode(_children), _name)
        else:
            return u"<%s%s/>" % (_name, attr)

def set_globals(fields, attrs, init_file, stats_file):
    setattr(sys.modules[__name__], "init_file", init_file)
    setattr(sys.modules[__name__], "stats_file", stats_file)
    setattr(sys.modules[__name__], "items", [(item["name"], item["field"], item["field_type"]) for item in fields+attrs])

def generate_file(args):
    file_id, afile = args
    try:
        if not init_file(afile): return None, None
        doc = [tag(n, afile[f] if f and f in afile and afile[f] else False, children_type=t, separator=",") for n,f,t in items]
        return tag("sphinx:document", doc, id=file_id, children_type=list), afile
    except BaseException as e:
        logging.exception("Error processing file %s.\n"%str(afile["_id"]))
        return None, e

outwrite = None
generate_id = None

class XmlPipe2:
    def __init__(self, processes, fields, attrs, stats, gen_id):
        global outwrite, generate_id
        outwrite = codecs.getwriter("utf-8")(sys.stdout).write
        self.processes = processes
        self.fields = fields
        self.attrs = attrs
        self.stats = stats
        self.pool = Pool(processes=processes) if processes>1 else None
        self.count = 0
        generate_id = gen_id

    def generate_header(self):
        outwrite(u"<?xml version=\"1.0\" encoding=\"utf-8\"?><sphinx:docset><sphinx:schema>")
        outwrite(u"".join(tag("sphinx:field", name=f["name"]) for f in self.fields))
        outwrite(u"".join(tag("sphinx:attr", name=a["name"], type=a["type"], bits=a.get("bits"), default=a.get("default")) for a in self.attrs))
        outwrite(u"</sphinx:schema>")

    def generate_footer(self):
        outwrite(u"</sphinx:docset>")

    def generate(self, server, entities_server, part, afilter, batch_size, stop_set=None, stop_set_len=0, last_count=None, headers=True):
        ff = FilesFetcher(server, entities_server, afilter, batch_size, stop_set, stop_set_len, last_count, self.processes)
        ff.start()
        if headers: self.generate_header()
        count = error_count = 0
        logging.warn("Comienza indexado en servidor %s."%server)
        if self.pool:
            for doc, extra in self.pool.imap(generate_file, (generate_id(afile, part) for afile in ff)):
                count+=1
                if doc:
                    outwrite(doc)
                    stats_file(extra, self.stats)
                elif extra:
                    error_count += 1
                    if error_count>100: raise extra # ante mas de 100 errores, detiene la indexacion con error
                if count%1000000==0:
                    outwrite("\n")
                    logging.warn("Progreso de indexado del servidor %s."%(server), extra={"count":count, "error_count":error_count})
        else:
            for afile in ff:
                doc, extra = generate_file(generate_id(afile, part))
                count+=1
                if doc:
                    outwrite(doc+"\n")
                    stats_file(extra, self.stats)
                elif extra:
                    error_count += 1
                    if error_count>100: raise extra # ante mas de 100 errores, detiene la indexacion con error
                if count%1000000==0:
                    logging.warn("Progreso de indexado del servidor %s."%(server), extra={"count":count, "error_count":error_count})

        if headers: self.generate_footer()
        logging.warn("Finaliza indexado en servidor %s."%server)

        self.total_count = ff.total_count
        self.count = count

        return ff.stop_set
