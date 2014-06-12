#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse, os, stat, collections, gzip, time
from itertools import islice, chain
from datetime import datetime

def file_lines(fname):
    try:
        count = 0
        with open(fname) as thefile:
            while True:
                buffer = thefile.read(65536)
                if not buffer: break
                count += buffer.count('\n')
        return count
    except IOError as e:
        return -1

class InputNode:
    def __init__(self, input_folder):
        self.input_folder = input_folder
        self.folders = collections.OrderedDict()
        self.files = collections.OrderedDict()
        self.size = 0
        self.lastmod = 0

        # recorre entradas dentro del directorio
        for entry in sorted(os.listdir(self.input_folder)):
            path_entry = self.input_folder+entry
            entry_info = os.stat(path_entry)

            if stat.S_ISDIR(entry_info[stat.ST_MODE]):
                self.folders[entry] = folder = InputNode(path_entry+"/")
                size = folder.size
                lastmod = folder.lastmod
            else:
                size = file_lines(path_entry)
                lastmod = entry_info[stat.ST_MTIME]
                group_entry, part = entry.split(".")
                if group_entry in self.files:
                    self.files[group_entry].append((part, size, lastmod))
                else:
                    self.files[group_entry] = [(part, size, lastmod)]

            self.size += size
            if lastmod > self.lastmod:
                self.lastmod = lastmod

    def get_first_filename(self):
        if self.folders:
            name, folder = self.folders.iteritems().next()
            return name+"/"+folder.get_first_filename()
        elif self.files:
            return self.files.iterkeys().next()

    def copydata(self, start, end, output):
        if start and end and len(start)>1 and start[0]==end[0]:
            self.folders[start[0]].copydata(start[1:], end[1:], output)
        else:
            active = not start or not start[0]
            for name, folder in self.folders.iteritems():
                if not active and name==start[0]:
                    active = True
                    folder.copydata(start[1:], None, output)
                elif active:
                    if end and end[0] and name==end[0]:
                        folder.copydata(None, end[1:], output)
                        active = False
                        break
                    else:
                        folder.copydata(None,None, output)

            for name, parts in self.files.iteritems():
                if not active and name==start[0]:
                    active = True

                if active:
                    if end and end[0] and name==end[0]:
                        break

                    output.extend(self.get_unique_data(name, parts))

    def get_unique_data(self, name, parts):
        files = [open(self.input_folder+name+"."+part) for (part, size, lastmod) in parts]
        unique_lines = sorted({line for afile in files for line in afile})
        for afile in files:
            afile.close()
        return unique_lines

    def __iter__(self):
        return chain(self.folders.iteritems(),self.files.iteritems())


FILESIZE_LIMIT = 45000
FILESIZE_HARDLIMIT = 50000
FILESIZE_HALF_HARDLIMIT = FILESIZE_HARDLIMIT/2
FIRST_FILENAME = "_first"

class XmlFile:
    def __init__(self, xml_line=None, path=None):
        if xml_line:
            # parsea <sitemap><loc>%s</loc><lastmod>%s</lastmod></sitemap>
            url, lastmod = xml_line[14:-21].split("</loc><lastmod>")

            # obtiene el nombre del fichero de la url
            filename = url[url.rfind("/")+1:]

            # separa extensiones
            filename, exts = filename.split(".",1)

            # separa parte
            if "__" in filename:
                filename, part = filename.split("__",1)
                part = int(part)
            else:
                part = None


            if part: # no considera partes que no sean la primera (None o 0)
                self.start = False
            else:
                self.start = None if filename.startswith(FIRST_FILENAME) else tuple(filename.split("_"))

                # si esta en partes calcula el tamaño como la suma de todas las partes
                if part==0:
                    size = self.size = 0
                    while True: # recorre partes hasta que no haya más
                        size = file_lines(path+filename+"__"+str(part)+"."+exts)
                        if size<0:
                            break
                        part += 1
                        self.size += size
                else:
                    self.size = file_lines(path+filename+"."+exts)
                self.lastmod = int(time.mktime(datetime.strptime(lastmod,'%Y-%m-%dT%H:%M:%SZ').timetuple()))
        else:
            self.start = None
            self.size = 0
            self.lastmod = 0
        self.force_write = False
        self.end = None

    def get_filename(self, part=None):
        return ("_".join(self.start) if self.start else FIRST_FILENAME) + (".xml" if part==None else "__"+str(part)+".xml")

class OutputTree:
    def __init__(self, input_folder):
        self.files = []
        self.old_files = {}
        self.half_outfile = xml = None
        # si tiene carpeta de entrada, regenera la estructura de los XML existentes
        if input_folder:
            i=0
            main_filename = input_folder+"sitemap%d.xml.gz"
            while os.path.exists(main_filename%i):
                with self._open_file(main_filename%i) as main:
                    for entry in main:
                        if entry.startswith("<sitemap>"):
                            xml = XmlFile(entry, input_folder)
                            if xml.start!=False: self.old_files[xml.start] = xml.lastmod
                i+=1

        self.last_old_file = xml.start if xml else None

    def _create_tree(self, tree, path=[]):
        outfile = self.files[-1][-1]

        # esta en modo actualización?
        update_mode = bool(self.old_files)

        # recorre subcarpetas
        for name, folder in tree.folders.iteritems():
            if update_mode or folder.size+outfile.size>FILESIZE_LIMIT:
                self._create_tree(folder, path+[name])
            else: # evita recorrer la carpeta por dentro
                outfile.size += folder.size
                if folder.lastmod > outfile.lastmod:
                    outfile.lastmod = folder.lastmod

        # inicializa variables
        next_file = False

        # recorre ficheros
        for name, parts in tree.files.iteritems():
            full_path = tuple(path+[name])

            size = sum(part[1] for part in parts)
            lastmod = max(part[2] for part in parts)

            new_size = size+outfile.size

            # modo actualizacion solo hasta el último fichero generado anteriormente
            if update_mode and full_path > self.last_old_file:
                self.half_outfile = None
                update_mode = False

            if update_mode: # modo actualización
                # si en la generación anterior se habia cortado aqui, se respeta
                if full_path in self.old_files:
                    # no hace falta crear un fichero a la mitad, unifica info con fichero actual
                    if self.half_outfile:
                        if self.half_outfile.lastmod>outfile.lastmod:
                            outfile.lastmod = self.half_outfile.lastmod
                        self.half_outfile = None
                    next_file = True

                else:
                    # si se pasa del limite duro, parte por la mitad
                    if new_size>=FILESIZE_HARDLIMIT:
                        self.files[-1].insert(-1, self.half_outfile)
                        outfile.start = self.half_outfile.end
                        outfile.size -= self.half_outfile.size
                        new_size = size+outfile.size
                        self.half_outfile = None

                    # guarda la mitad por si se pasara del tamaño máximo
                    if not self.half_outfile and new_size>=FILESIZE_HALF_HARDLIMIT:
                        self.half_outfile = XmlFile()
                        self.half_outfile.start = outfile.start
                        self.half_outfile.size = outfile.size
                        self.half_outfile.lastmod = outfile.lastmod
                        self.half_outfile.end = full_path
                        self.half_outfile.force_write = True

                        # reinicia contadores del fichero actual
                        outfile.lastmod = 0

            elif new_size>=FILESIZE_LIMIT: # modo nuevo
                next_file = True

            # cambio de fichero cuando este está lleno o si ya existe uno con este comienzo
            if next_file:
                next_file = False
                outfile.end = full_path # cierra fichero actual

                # crea fichero nuevo
                outfile = XmlFile()
                outfile.start = full_path
                if len(self.files[-1])>=FILESIZE_LIMIT:
                    self.files.append([])
                self.files[-1].append(outfile)

            # actualiza tamaño y fecha del fichero actual
            if lastmod > outfile.lastmod:
                outfile.lastmod = lastmod
            outfile.size += size

    def update(self, input_tree):
        self.input_tree = input_tree
        self.files.append([XmlFile()])
        self._create_tree(input_tree)

    def _create_file(self, filename):
        return gzip.GzipFile(filename, "w", 9)

    def _open_file(self, filename):
        return gzip.GzipFile(filename, "r", 9)

    def save(self, output_folder, files_baseurl, sitemaps_baseurl):
        reverse_files_list = []
        main_filename = output_folder+"sitemap%d.xml.gz"

        for i, chunk in enumerate(self.files):
            with self._create_file(main_filename%i) as main:
                main.write('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
                for afile in chunk:
                    lastmod = datetime.fromtimestamp(afile.lastmod).strftime("%Y-%m-%dT%H:%M:%SZ")

                    # si el fichero respeta los limites (lo + habitual)
                    if afile.size<=FILESIZE_HARDLIMIT:
                        sitemap_filename = afile.get_filename()+".gz"
                        reverse_files_list.append('<sitemap><loc>%s%s</loc><lastmod>%s</lastmod></sitemap>\n'%(sitemaps_baseurl, sitemap_filename, lastmod))

                        # comprueba si se debe reescribir
                        if afile.force_write or afile.lastmod > self.old_files.get(afile.start, 0):
                            with self._create_file(output_folder+sitemap_filename) as sitemap:
                                sitemap.write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
                                temp_buffer = []
                                self.input_tree.copydata(afile.start, afile.end, temp_buffer)
                                while temp_buffer:
                                    sitemap.write(temp_buffer.pop() % files_baseurl)
                                sitemap.write('</urlset>')

                    # para excepciones con ficheros muy grandes
                    else:
                        # busca el nodo en el arbol de entrada
                        path = afile.start
                        folder = self.input_tree
                        while len(path)>1:
                            folder = folder.folders[path[0]]
                            path = path[1:]

                        # trocea el fichero en partes
                        data_iter = iter(folder.get_unique_data(path[0], folder.files[path[0]]))
                        part = list(islice(data_iter, FILESIZE_HARDLIMIT))
                        part_index=0
                        while part:
                            sitemap_filename = afile.get_filename(part_index)+".gz"
                            reverse_files_list.append('<sitemap><loc>%s%s</loc><lastmod>%s</lastmod></sitemap>\n'%(sitemaps_baseurl, sitemap_filename, lastmod))
                            with self._create_file(output_folder+sitemap_filename) as sitemap:
                                sitemap.write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
                                while part:
                                    sitemap.write(part.pop() % files_baseurl)
                                sitemap.write('</urlset>')
                                part = list(islice(data_iter, FILESIZE_HARDLIMIT))
                            part_index+=1

                while reverse_files_list:
                    main.write(reverse_files_list.pop())
                main.write('</sitemapindex>')

def build(input_folder, output_folder, files_baseurl, sitemaps_baseurl, previous_folder=None):

    # añade barra final a las rutas
    if input_folder[-1]!="/":
        input_folder += "/"
    if output_folder[-1]!="/":
        output_folder += "/"
    if files_baseurl[-1]!="/":
        files_baseurl += "/"
    if sitemaps_baseurl[-1]!="/":
        sitemaps_baseurl += "/"

    print "Parseando estructura de entrada: "
    # parsea estructura de entrada
    input_tree = InputNode(input_folder)
    print input_tree.size

    # busca XML existentes
    print "Creando estructura de salida: "
    output_tree = OutputTree(previous_folder)
    print len(output_tree.old_files)

    # genera estructura de salida
    print "Actualizando estructura de salida: "
    output_tree.update(input_tree)
    print len(output_tree.files)

    # guarda ficheros
    print "Guardando estructura de salida."
    output_tree.save(output_folder, files_baseurl, sitemaps_baseurl)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('input', type=str, help='Input folder.')
    parser.add_argument('output', type=str, help='Output folder.')
    parser.add_argument('files_baseurl', type=str, help='Start for torrent files URLs.')
    parser.add_argument('sitemaps_baseurl', type=str, help='Start for sitemaps URLs.')
    parser.add_argument('--previous', type=str, help='Output folder in the last execution.', default=None)

    params = parser.parse_args()

    build(params.input, params.output, params.files_baseurl, params.sitemaps_baseurl, params.previous)
