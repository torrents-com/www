# -*- coding: utf-8 -*-

import os.path
from flask import render_template, current_app, g
from foofind.utils.fooprint import Fooprint
from foofind.services import *

news = Fooprint('news', __name__)

@cache.memoize(timeout=60*60)
def load_html_parts(filename):
    parts = {}
    open_block = None
    block_content = []
    full_filename = os.path.join(current_app.root_path, 'news', filename, "index.html")
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

@news.route('/news')
@news.route('/news/<path:path>')
def main(path=""):
    g.override_header = True
    path_parts = load_html_parts(path)
    return render_template('news.html', **path_parts)

@index.route('/news/sitemap.xml')
def main_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news', 'sitemap_index.xml'))

@index.route('/news/post-sitemap.xml')
def post_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news', 'post-sitemap.xml'))

@index.route('/news/category-sitemap.xml')
def category_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news', 'category-sitemap.xml'))

@index.route('/news/author-sitemap.xml')
def author_sitemap():
    return send_from_directory(os.path.join(current_app.root_path, 'news', 'author-sitemap.xml'))

