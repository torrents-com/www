#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path

from foofind.services.extensions import cache

from flask import Blueprint, render_template, g, current_app, request, send_file, send_from_directory
from flask.ext.babelex import gettext as _
from torrents.multidomain import MultidomainBlueprint

from foofind.utils.downloader import get_file_metadata

web = MultidomainBlueprint('web', __name__, domain="torrents.ms")

def get_downloader_properties():
    g.cache_code += "D"
    downloader_files = current_app.config["DOWNLOADER_FILES"]
    installer_metadata = get_file_metadata(downloader_files["installer.exe"])
    setup_metadata = get_file_metadata(downloader_files["setup.exe"])
    source_metadata = get_file_metadata(downloader_files["source.zip"])

    properties = {
        "available": installer_metadata and setup_metadata,
        "source_available": bool(source_metadata)
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

@web.route('/robots.txt')
def favicon():
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'robots.txt', mimetype='text/plain')

@web.route('/')
def home():
    g.category=False
    g.title = "Torrents.com | Torrents Downloader"
    g.page_description = "Torrents Downloader is a fast client for the Torrent P2P network"

    return render_template(
        "microsite/foodownloader.html",
        properties = get_downloader_properties(),
        mode = "download",
        style_alternative = request.args.get("a", 2, int)
        )

@web.route("/success")
@cache.cached()
def foodownloader_success():
    return render_template(
        "microsite/foodownloader.html",
        mode = "success",
        style_alternative = 0
        )
