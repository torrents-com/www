#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, chardet, codecs, math, pymongo, Queue, os, argparse, glob
os.environ["FOOFIND_NOAPP"] = "1"

from os.path import dirname, abspath, exists
sys.path.insert(0,dirname(dirname( abspath(__file__))))
sys.path.insert(0,dirname(dirname(dirname( abspath(__file__))))+"/foofind")

import torrents
from foofind.utils import u, logging, mid2url
from foofind.utils.seo import seoize_text
from threading import Thread
from multiprocessing import Pool

class FilesFetcher(Thread):
    def __init__(self, server, files_filter, batch_size):
        super(FilesFetcher, self).__init__()
        self.daemon = True
        self.server = server
        self.batch_size = batch_size
        self.results = Queue.Queue(batch_size)
        self.files_filter = files_filter
        self.complete = False

    def run(self):
        self.complete = False
        gconn = pymongo.Connection(self.server, slave_okay=True)
        gdb = gconn.foofind
        gfoo = gdb.foo

        cursor = gfoo.find(self.files_filter, timeout=False).batch_size(self.batch_size)

        for f in cursor:
            self.results.put(f)

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

open_files = {}
def get_writer(fs, step, output, suffix):

    path = fs.strftime("%Y/%m-%d/")
    filename = path + "%02d-%02d"%(fs.hour, fs.minute/15*15)

    if filename in open_files:
        # accede al writer y actualiza el momento de uso
        writer = open_files[filename]
        writer.step = step
    else:
        # cierra el que lleva más sin usarse
        if len(open_files)>20:
            delete_filename = min((f.step, key) for key, f in open_files.iteritems())[1]
            open_files[delete_filename].close()
            del open_files[delete_filename]
        # crea la ruta del nuevo
        if not os.path.exists(output + path): os.makedirs(output + path)
        # abre archivo, crea el writer y establece momento de uso
        writer = open_files[filename] = codecs.getwriter("utf-8")(file(output + filename+suffix, "a"))
        setattr(writer,"step",step)

    return writer

def close_writers():
    for filename, f in open_files.iteritems():
        f.close()

def generate(server, part, afilter, batch_size, output):

    if not output:
        output = dirname(abspath(__file__)) + "/gen/" + str(part) + "/"

    ff = FilesFetcher(server, afilter, batch_size)
    ff.start()

    suffix = "."+str(part)
    count = error_count = 0
    logging.info("Comienza generación de sitemap en servidor %s."%server)

    for afile in ff:
        try:
            count += 1

            # comprueba si tiene nombres de ficheros
            if "fn" not in afile:
                continue

            # comprueba si no está bloqueado
            if int(float(afile.get("bl", 0)))!=0:
                continue

            # comprueba si tiene origenes validos
            for src in afile["src"].itervalues():
                if "t" in src and src["t"] in {3, 7, 79, 80, 81, 82, 83, 90} and int(float(src.get("bl",0)))==0:
                    break
            else:
                continue

            # elige algun nombre de fichero interesante
            for filename_info in afile["fn"].itervalues():
                if filename_info["n"]=="download" or IS_BTIH.match(filename_info["n"]) or filename_info["n"].startswith("[TorrentDownloads"):
                    continue
                break
            else:
                continue

            file_name = seoize_text(filename_info["n"]+("."+filename_info["x"] if "x" in filename_info and not filename_info["n"].endswith("."+filename_info["x"]) else ""), "-", True)

            file_id = mid2url(afile["_id"])
            fs = afile["fs"]
            get_writer(fs, count, output, suffix).write("<url><loc>http://torrents.fm/%s-%s</loc></url>\n"%(file_name, file_id))

        except BaseException as e:
            error_count += 1
            if error_count>100: raise e # ante mas de 100 errores, detiene la indexacion con error

        if count%10000==0:
            logging.info("Progreso de generación de sitemap del servidor %s."%(server), extra={"count":count, "error_count":error_count})

    close_writers()

    sort_files(output)

    logging.info("Finaliza la generación de sitemap en servidor %s."%server)

def last_part(line):
    return line.rsplit('-', 1)[-1]

def sort_files(output):
    for f in filter(os.path.isfile, glob.iglob(output+'*/*/*')):
        lines = sorted(open(f), key=last_part)
        open(f, 'w').write(''.join(lines))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Index data for a sphinx server.')
    parser.add_argument('server', type=str, help='Server address. Default value is fetch from main database.')
    parser.add_argument('part', type=int, help='Server number.')
    parser.add_argument('--output', type=str, help='Output folder.', default=None)
    parser.add_argument('--batch_size', type=str, help='Mongo batch fetch size.', default=10240)

    params = parser.parse_args()

    generate(params.server, params.part, {}, params.batch_size, params.output)

