#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path

from foofind.services.extensions import cache

from flask import Blueprint, render_template, g, current_app, request, send_file, send_from_directory, redirect, make_response, url_for, abort
from flask.ext.babelex import gettext as _
from torrents.multidomain import MultidomainBlueprint

from foofind.utils.downloader import get_file_metadata

web = MultidomainBlueprint('web', __name__, domain="torrents.ms")

def update_downloader_properties():
    cache.delete("downloader_properties")

@cache.cached(key_prefix="downloader_properties")
def get_downloader_properties():
    downloader_files = current_app.config["DOWNLOADER_FILES"]
    installer_metadata = get_file_metadata(downloader_files["installer.exe"])
    setup_metadata = get_file_metadata(downloader_files["setup.exe"])
    source_metadata = get_file_metadata(downloader_files["source.zip"])
    update_metadata = get_file_metadata(downloader_files["update.exe"])

    properties = {
        "available": installer_metadata and setup_metadata,
        "source_available": bool(source_metadata),
        "update_version": update_metadata.get("version", "")
        }

    try:
        if properties["available"]:
            properties["version_code"] = setup_metadata["version"]
            properties["length"] = installer_metadata["size"]
            properties["filename"] = "installer.exe"
    except KeyError:
        properties["available"] = False

    try:
        if properties["source_available"]:
            properties["source_length"] = source_metadata["size"]
            properties["source_filename"] = "source.zip"
    except KeyError:
        properties["source_available"] = False
    return properties

@web.route('/favicon.ico')
def favicon():
    g.cache_code += "S"
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@web.route('/robots.txt')
def robots():
    g.cache_code += "S"
    full_filename = os.path.join(os.path.join(current_app.root_path, 'static'), 'robots.txt')

    with open(full_filename) as input_file:
        response = make_response(input_file.read() + "\n\nUser-agent: Googlebot\nDisallow: /search/*\n"+"".join("Disallow: /%s/*\n"%cat.url for cat in g.categories) + "\nSitemap: " + url_for(".sitemap", _external=True))
        response.mimetype='text/plain'
    return response

@web.route('/smap')
def user_sitemap():
    g.cache_code += "S"
    structure = [[("Torrents Downloader", url_for("web.home"))]]

    if g.downloader_properties["available"]:
        structure[0].append(("Windows binaries", url_for('downloads.download', instfile=g.downloader_properties['filename'])))

        if g.downloader_properties["source_available"]:
            structure[0].append(("Source code", url_for('downloads.download', instfile=g.downloader_properties['source_filename'])))

    return render_template('sitemap.html', structure=structure, column_count=1, column_width=22)

@web.route('/sitemap.xml')
def sitemap():
    g.cache_code += "S"
    response = make_response(render_template('sitemap.xml', pages = [url_for(".home", _external=True)]))
    response.mimetype='text/xml'
    return response

@web.route('/')
def home():
    g.cache_code += "D"
    g.category=False
    g.title.append("Torrents Downloader")
    g.page_description = "Torrents Downloader is a fast client for the Torrent P2P network"
    g.keywords.clear()
    g.keywords.update(["files", "search", "document", "image", "video", "torrents", "audio", "software"])

    return render_template(
        "microsite/foodownloader.html",
        mode = "download",
        style_alternative = request.args.get("a", 2, int)
        )

@web.route("/success")
def foodownloader_success():
    g.cache_code += "D"
    return render_template(
        "microsite/foodownloader.html",
        mode = "success",
        style_alternative = 0
        )
