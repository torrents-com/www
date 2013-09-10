# -*- coding: utf-8 -*-

import os.path
from flask import render_template, current_app, g, send_from_directory, abort, make_response, request
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
            line = line.strip()
            if line.startswith("<!--= "):
                var_name, var_content = line[6:-3].split(" ",1)
                parts[var_name] = var_content
            elif open_block:
                if line.startswith("<!--}-->"):
                    parts[open_block] = "".join(block_content).decode("UTF-8")
                    block_content = []
                    open_block = None
                else:
                    block_content.append(line)
            else:
                if line.startswith("<!--{ "):
                    print line
                    open_block = line[6:-3]

    return parts


@news.route('/res/cookies.js')
def cookies():
    response = make_response("$(function(){cookies("+request.cookies.get("cookies_accept","0")+")})")
    response.headers['content-type']='application/javascript'
    response.set_cookie('cookies_accept',value='1')
    return response

@news.route('/')
@news.route('/news/<path:path>')
def home(path=""):
    g.override_header = True
    path_parts = load_html_parts(path)

    if not path_parts:
        return abort(404)

    if "top-stories" in path_parts:
        path_parts["top_stories"] = path_parts["top-stories"]
        del path_parts["top-stories"]
    print path_parts.keys()
    return render_template('news.html', **path_parts)

@news.route('/news/wp-content/<path:path>')
def wp_content(path):
    return send_from_directory(os.path.join(current_app.root_path, 'news/wp-content'), path)

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

