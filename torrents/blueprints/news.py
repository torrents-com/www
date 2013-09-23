# -*- coding: utf-8 -*-

import os.path, re, urllib2
from flask import render_template, current_app, g, send_from_directory, abort, make_response, request, url_for
from torrents.multidomain import MultidomainBlueprint
from foofind.utils.fooprint import Fooprint
from foofind.services import *
from .downloader.web import get_downloader_properties

news = MultidomainBlueprint('news', __name__, domain="torrents.com")

def fix_urls(content, external=False):

    # remove xsl references from xml sitemaps first line
    if content.startswith('<?xml version="1.0" encoding="UTF-8"?>'):
        content = '<?xml version="1.0" encoding="UTF-8"?>\n'+content.split("\n",1)[1]

    home_url = url_for("news.home", _external=external).rstrip("/")
    inner_url = url_for("news.home", path="_", _external=external)[:-1] + r"\1"
    inner_url_on_url = urllib2.quote(url_for("news.home", path="_", _external=True)[:-1], "") + r"\1"

    original_url = current_app.config["NEWS_ORIGINAL_URLS"].rstrip("/")
    original_url_on_url = urllib2.quote(original_url, "")
    original_template_url = original_url+"/template"

    inner_re=re.compile(re.escape(original_url)+r"/([a-zA-Z0-9\-]+)")
    inner_on_url_re=re.compile(re.escape(original_url_on_url)+r"%2F([a-zA-Z0-9\-]+)")

    return inner_re.sub(inner_url, inner_on_url_re.sub(inner_url_on_url, content.replace(original_template_url, home_url))).replace(original_url, home_url)

def fix_response(filename, mimetype=None):
    full_filename = os.path.join(current_app.root_path, "news", filename)

    with open(full_filename) as input_file:
        response = make_response(fix_urls(input_file.read(), True))
        if mimetype:
            response.mimetype = mimetype

    return response

def load_html_parts(filename):
    parts = {}
    open_block = None
    block_content = []

    full_filename = os.path.join(current_app.root_path, "news", filename, "index.html")

    # chequea que exista el fichero pedido
    if not os.path.exists(full_filename):
        return None

    with open(full_filename) as input_file:
        for line in input_file:
            line = line.strip()
            if line.startswith("<!--= "):
                var_name, var_content = line[6:-3].split(" ",1)
                parts[var_name] = fix_urls(var_content)
            elif open_block:
                if line.startswith("<!--}-->"):
                    parts[open_block] = fix_urls("\n".join(block_content).decode("UTF-8"))
                    block_content = []
                    open_block = None
                else:
                    block_content.append(line)
            else:
                if line.startswith("<!--{ "):
                    open_block = line[6:-3]

    return parts

@news.route('/')
@news.route('/news/<path:path>')
def home(path=""):
    g.cache_code += "N"
    g.override_header = True
    path_parts = load_html_parts(path)

    if not path_parts:
        return abort(404)

    return render_template('news.html', **path_parts)

@news.route('/news/wp-content/<path:path>')
def wp_content(path):
    g.cache_code += "N"
    return send_from_directory(os.path.join(current_app.root_path, 'news', 'wp-content'), path)

@news.route('/news/sitemap.xml')
def main_sitemap():
    g.cache_code += "N"
    return fix_response('sitemap_index.xml', "text/xml")

@news.route('/news/<name>-sitemap.xml')
def inner_sitemap(name):
    g.cache_code += "N"
    return fix_response(name+'-sitemap.xml', "text/xml")

@news.route('/news/rss')
def rss():
    g.cache_code += "N"
    return fix_response('feed/rss', "application/rss+xml")
