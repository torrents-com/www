# -*- coding: utf-8 -*-
import os, re, datetime
from flask import redirect, url_for, render_template, send_from_directory, current_app, make_response, request, g

from foofind.utils import logging
from torrents.multidomain import MultidomainBlueprint
from foofind.services import *
from torrents.services import *

index = MultidomainBlueprint('index', __name__)

@index.route('/res/caction.js')
def cookies():
    # obtiene la cookie actual y estable la cookie nueva como aceptada
    current_value = request.cookies.get("cookie_level","0")
    current_cid = request.cookies.get("_cid",None)
    new_cid = request.args.get("cid")
    new_value = "2"

    # si no está aceptando...
    if not "accept" in request.args:
        ip = (request.headers.getlist("X-Forwarded-For") or [request.remote_addr])[0]
        if ip in spanish_ips or any(lang_code in request.accept_languages.values() for lang_code in current_app.config["SPANISH_LANG_CODES"]):
            new_value = None if current_value == "2" else "1"
        else:
            current_value = "2"

    # respuesta
    response = make_response(request.args["callback"]+"("+current_value+")")
    response.headers['content-type']='application/javascript'
    if new_value:
        response.set_cookie('cookie_level', value=new_value, expires=(datetime.datetime.now() + datetime.timedelta(3650)), httponly=False)

    # guarda el id de cliente si puede
    if current_cid!=new_cid and current_value!="0":
        response.set_cookie('_cid', value=new_cid, expires=(datetime.datetime.now() + datetime.timedelta(365*2)), httponly=False)

    return response

@index.route('/favicon.ico')
def favicon():
    g.cache_code = "S"
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

