#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os.path
import mimetypes
import requests
from flask import g, render_template, current_app, request, send_file, send_from_directory, jsonify, url_for, abort, redirect, make_response
from flask.ext.babelex import gettext as _
from foofind.utils.downloader import downloader_url
from torrents.multidomain import MultidomainBlueprint
from foofind.utils import logging

downloader = MultidomainBlueprint('downloader', __name__, domain="torrents.ms")

def get_downloader_properties(base_path, downloader_files_builds):
    # source code information
    properties = {"common":{"base_path": base_path}}

    # builds information
    for build, info in downloader_files_builds.iteritems():
        try:
            with open(os.path.join(base_path, info["metadata"]), "r") as f:
                metadata = json.load(f)

            properties[build] = info.copy()
            properties[build].update(metadata)
            properties[build]["length"] = os.path.getsize(os.path.join(base_path, properties[build]["main"]))
        except:
            logging.error("Error checking downloader files.")

    return properties

def parse_version(info):
    if info:
        try:
            info_parts = info.split("-",3)
            info_parts.reverse()
            version = info_parts.pop().split(".")
            version2 = info_parts.pop() if info_parts else ""
            build = info_parts.pop() if info_parts else "W32"
            return [[int(v) for v in version], version2], build
        except:
            pass

    # Default return value: no version, W32 build
    return 0, "W32"

@downloader.route('/favicon.ico')
def favicon():
    g.cache_code += "S"
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@downloader.route('/robots.txt')
def robots():
    g.cache_code += "S"
    full_filename = os.path.join(os.path.join(current_app.root_path, 'static'), 'robots.txt')

    with open(full_filename) as input_file:
        response = make_response(input_file.read() + "\nSitemap: " + url_for(".sitemap", _external=True))
        response.mimetype='text/plain'
    return response

@downloader.route('/smap')
def user_sitemap():
    g.cache_code += "S"
    structure = [[("Torrents Downloader", url_for("downloader.home")),(_("Browse all downloads"), url_for("downloader.downloads"))]]

    return render_template('sitemap.html', canonical=url_for("downloader.user_sitemap", _external=True), structure=structure, column_count=1, column_width=22)

@downloader.route('/sitemap.xml')
def sitemap():
    g.cache_code += "S"
    response = make_response(render_template('sitemap.xml', pages = [url_for(".home", _external=True), url_for(".downloads", _external=True)]))
    response.mimetype='text/xml'
    return response

@downloader.route("/")
def home():
    g.cache_code += "D"
    g.category = False
    g.title.append("Torrents Downloader")
    g.page_description = "Torrents Downloader is a fast client for the Torrent P2P network"
    g.keywords.clear()
    g.keywords.update(["files", "search", "document", "image", "video", "torrents", "audio", "software"])

    return render_template(
        "microsite/index.html",
        mode = "download"
        )


@downloader.route("/downloads")
def downloads():
    g.cache_code += "D"
    return render_template(
        "microsite/downloads.html",
        mode = "success"
        )

@downloader.route("/success")
def success():
    g.cache_code += "D"
    return render_template(
        "microsite/success.html",
        mode = "success"
        )

@downloader.route("/logger", methods=("GET", "POST"))
@downloader_url
def logger():
    return ""

@downloader.route("/update")
@downloader_url
def update():
    '''

    JSON SPEC
        {
        ?"update": {
            ?"title": "Update available...",
            ?"text": "New version...",
            "files":[
                {"url": "http://...", "version": "xyz", "argv": ["/arg1", ... ]},
                ...
                ]
            },
        ?"messages": [{
            ?"title": "title",
            ?"icon": "wxART_INFORMATION" // Icon name to display, defaults to wxART_INFORMATION

            ?"priority": 0, // Higher priority means first shown on multiple messages, otherwhise alphabetical order by title is used
            ?"id": "unique_identifier", // For non repeateable messages, if not specified, message will be shown on every session

            ?"text": "Text...",
            ?"url": "http://...",
            ?"size": [-1,-1], // Size for embeded objects like url

            ?"go_url": "http//:", // Implies Go, Cancel buttons
            ?"go_text": ""

            ?"start_url": "http://...", // Implies Download, Cancel buttons
            ?"start_filename": "...", // Filename wich file should have on disk, if not given, last part of url will be used
            ?"start_argv": ["/arg1", ...]
            ?"start_text"
            ?"start_close": true // True if app needs to be closed when run. Defaults to false,
            }, ...]
        }

    ICONS:
        wxART_ERROR                 wxART_FOLDER_OPEN
        wxART_QUESTION              wxART_GO_DIR_UP
        wxART_WARNING               wxART_EXECUTABLE_FILE
        wxART_INFORMATION           wxART_NORMAL_FILE
        wxART_ADD_BOOKMARK          wxART_TICK_MARK
        wxART_DEL_BOOKMARK          wxART_CROSS_MARK
        wxART_HELP_SIDE_PANEL       wxART_MISSING_IMAGE
        wxART_HELP_SETTINGS         wxART_NEW
        wxART_HELP_BOOK             wxART_FILE_OPEN
        wxART_HELP_FOLDER           wxART_FILE_SAVE
        wxART_HELP_PAGE             wxART_FILE_SAVE_AS
        wxART_GO_BACK               wxART_DELETE
        wxART_GO_FORWARD            wxART_COPY
        wxART_GO_UP                 wxART_CUT
        wxART_GO_DOWN               wxART_PASTE
        wxART_GO_TO_PARENT          wxART_UNDO
        wxART_GO_HOME               wxART_REDO
        wxART_PRINT                 wxART_CLOSE
        wxART_HELP                  wxART_QUIT
        wxART_TIP                   wxART_FIND
        wxART_REPORT_VIEW           wxART_FIND_AND_REPLACE
        wxART_LIST_VIEW             wxART_HARDDISK
        wxART_NEW_DIR               wxART_FLOPPY
        wxART_FOLDER                wxART_CDROM
        wxART_REMOVABLE

    '''
    platform = request.args.get("platform", None)
    version_raw = request.args.get("version", None)
    if not version_raw and "/" in request.user_agent.string: # tries to get version from user agent
        version_raw = request.user_agent.string.split("/")[-1]

    version, build = parse_version(version_raw)

    # Updates
    update = g.downloader_properties[build].get("update",None)
    response = {}
    if update and version<update["min"]:
        # Custom update message
        new_version = g.downloader_properties[build]["version"]
        response["update"] = {
            "text": _("downloader_update_message",
                      appname = current_app.config["DOWNLOADER_APPNAME"],
                      version = new_version
                      ),
            "title": "Torrents Downloader",
            "files": [{
                        "url": url_for('.download', build=build, instfile=update["file"], _external=True),
                        "version": new_version,
                        "argv": [],
                    },]
            }

    # Messages
    response["messages"] = []

    return jsonify(response)

@downloader.route("/download/torrents_downloader_proxy.exe")
@downloader.route("/download/<build>/torrents_downloader_proxy.exe")
def download_proxy(build="W32"):
    if build[0]=="W" and g.downloader_properties[build]["proxy"]=="torrents_downloader_proxy.exe":
        data = {'geturl':'1', 'name':"Torrents Downloader", 'version':g.downloader_properties[build]["version"],
                'url':url_for('downloader.download', build=build, instfile=g.downloader_properties[build]["main"], _external=True), 'id':"torrents", 'img':'http://torrents.ms/static/app.png'}
        headers = {'Content-Type':'application/x-www-form-urlencoded', 'Connection':'close', 'Referer':request.referrer}

        resp = requests.post("http://download.oneinstaller.com/installer/", headers=headers, data=data)

        return redirect(resp.text, 302)
    else:
        return redirect(url_for('downloader.download', build=build, instfile=g.downloader_properties[build]["main"], _external=True), 302)


@downloader.route("/download/static/<path:instfile>") # Should be served statically
@downloader.route("/download/static/<build>/<path:instfile>") # Should be served statically
@downloader.route("/download/<instfile>")
@downloader.route("/download/<build>/<instfile>")
def download(instfile, build="W32"):
    return send_instfile(instfile, build)

def send_instfile(instfile, build):
    g.cache_code += "D"
    downloader_files = g.downloader_properties.get(build, None)
    if not downloader_files:
        abort(404)

    downloader_files_aliases = downloader_files.get("aliases",{})
    if instfile in downloader_files_aliases:
        path = downloader_files[downloader_files_aliases[instfile]]
    else:
        # check that can be downloaded
        for downloadable in downloader_files["downloadables"]:
            if downloader_files.get(downloadable, None)==instfile:
                path = instfile
                break
        else:
            abort(404)

    return send_file(os.path.join(g.downloader_properties["common"]["base_path"], path), mimetypes.guess_type(path)[0])



    downloader_files = current_app.config["DOWNLOADER_FILES"]
    downloader_files_aliases = current_app.config["DOWNLOADER_FILES_ALIASES"]

    if instfile in downloader_files_aliases:
        instfile = downloader_files_aliases[instfile]
    if not instfile in downloader_files:
        abort(404)

    version = request.args.get("version", "")
    lang = request.args.get("lang", "en")
    platform = request.args.get("platform", None)

    path = downloader_files[instfile]

    # Redirect downloads on static directories to static_download endpoint
    # hoping server will handle request and serve it directly
    prefix = os.path.abspath(os.path.join(current_app.root_path,"../downloads")) + os.sep
    if path.startswith(prefix):
        relative_path = path[len(prefix):]
        return redirect(url_for('.static_download', instfile=relative_path))

    # All downloads should be inside downloads static dir
    logging.warn("Download %r served dinamically because not in static directory %r" % (path, prefix))
    return send_file(path, mimetypes.guess_type(path)[0])
