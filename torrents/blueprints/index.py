# -*- coding: utf-8 -*-
import os, re
from flask import redirect, url_for, render_template, send_from_directory, current_app, make_response, request, g
from flask.ext.mail import Message

from foofind.utils import logging
from torrents.multidomain import MultidomainBlueprint
from foofind.services import *
from torrents.services import *

index = MultidomainBlueprint('index', __name__, domain="torrents.com")

@index.route('/res/cookies.js')
def cookies():
    response = make_response("$(function(){cookies("+request.cookies.get("cookies_accept","0")+")})")
    response.headers['content-type']='application/javascript'
    response.set_cookie('cookies_accept',value='1')
    return response

@index.route('/robots.txt')
def robots():
    full_filename = os.path.join(os.path.join(current_app.root_path, 'static'), 'robots.txt')

    with open(full_filename) as input_file:
        response = make_response(input_file.read() +  "\nSitemap: "+ url_for("news.main_sitemap", _external=True))
        response.mimetype='text/plain'
    return response

@index.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@index.route('/opensearch.xml')
def opensearch():
    response = make_response(render_template('opensearch.xml',shortname = "Torrents",description = "opensearch_description"))
    response.headers['content-type']='application/opensearchdescription+xml'
    return response

@index.route('/about')
def about():
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrents", "torrents.com", "search engine", "download", "free", "movie", "software", "popular largest"])
    g.title.append("About")
    return render_template('about.html')

@index.route('/legal')
def legal():
    g.category=False
    g.title.append("Terms & privacy")
    g.keywords.clear()
    g.keywords.update(["torrents search engine privacy terms of use"])
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    return render_template('legal.html')

@index.route('/contact', methods=["GET","POST"])
def contact():
    '''
    Muestra el formulario para reportar enlaces
    '''
    sent_error = g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrent search engine", "torrents", "free", "download", "popular", "torrents.com"])
    form = ContactForm(request.form)
    if request.method=='POST':
        if form.validate():
            to = current_app.config["CONTACT_EMAIL"]
            try:
                mail.send(Message("contact", sender=form.email.data, recipients=[to], html="<p>%s, %s</p><p>%s</p>"%(request.remote_addr, request.user_agent, form.message.data)))
                return redirect(url_for('.home', _anchor="sent"))

            except BaseException as e:
                g.alert = ("error", "The message has not been sent. Try again later or send mail to %s."%to)
                logging.exception(e)

    g.title.append("Contact form")
    return render_template('contact.html',form=form, sent_error=sent_error)

from flask.ext.wtf import Form, BooleanField, TextField, TextAreaField, SubmitField, Required, Email, RecaptchaField
class ContactForm(Form):
    '''
    Formulario para reportar enlaces
    '''
    email = TextField("Email", [Required("Required field."),Email("Invalid email.")])
    message = TextAreaField("Message", [Required("Required field.")])
    captcha = RecaptchaField("")
    accept_tos = BooleanField(validators=[Required("Required field.")])
    submit = SubmitField("Submit")
