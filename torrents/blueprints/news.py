# -*- coding: utf-8 -*-

import os.path
from flask import render_template, current_app, g, send_from_directory, abort
from torrents.multidomain import MultidomainBlueprint
from foofind.utils.fooprint import Fooprint
from foofind.services import *

news = MultidomainBlueprint('news', __name__, domain="torrents.com")

@cache.memoize(timeout=60*60)
def load_html_parts(filename):
    parts = {}
    open_block = None
    block_content = []
    full_filename = os.path.join(current_app.root_path, 'news', filename, "index.html")

    # chequea que exista el fichero pedido
    if not os.path.exists(full_filename):
        return None

    with open(full_filename) as input_file:
        for line in input_file:
            if open_block:
                if line.startswith("<!--}-->"):
                    parts[open_block] = "".join(block_content).decode("UTF-8")
                    block_content = []
                    open_block = None
                else:
                    block_content.append(line)
            else:
                if line.startswith("<!--{ "):
                    open_block = line[6:-4]

    return parts

@news.route('/')
@news.route('/news/<path:path>')
def home(path=""):
    g.override_header = True
    path_parts = load_html_parts(path)

    if not path_parts:
        return abort(404)

    return render_template('news.html', **path_parts)

@news.route('/news/sitemap.xml')
def main_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news'), 'sitemap_index.xml')

@news.route('/news/post-sitemap.xml')
def post_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news'), 'post-sitemap.xml')

@news.route('/news/category-sitemap.xml')
def category_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news'), 'category-sitemap.xml')

@news.route('/news/author-sitemap.xml')
def author_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news'), 'author-sitemap.xml')

