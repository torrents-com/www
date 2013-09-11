# -*- coding: utf-8 -*-
import os, re
from flask import flash, redirect, url_for, render_template, send_from_directory, current_app, make_response, request, g
from flask.ext.mail import Message

from foofind.utils import logging
from torrents.multidomain import MultidomainBlueprint
from foofind.services import *
from torrents.services import *

index = MultidomainBlueprint('index', __name__, domain="torrents.com")

@index.route('/robots.txt')
def robots():
    return send_from_directory(os.path.join(current_app.root_path, 'static'), 'robots.txt')

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
    g.extra_container_classes="text_page"
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrents", "torrents.com", "search engine", "download", "free", "movie", "software", "popular largest"])
    g.title+=" | About"
    return render_template('about.html')

@index.route('/legal')
def legal():
    g.extra_container_classes="text_page"
    g.category=False
    g.title+=" | Terms & privacy"
    g.keywords.clear()
    g.keywords.update(["torrents search engine privacy terms of use"])
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    return render_template('legal.html')

@index.route('/contact', methods=["GET","POST"])
def contact():
    '''
    Muestra el formulario para reportar enlaces
    '''
    g.extra_container_classes="text_page"
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrent search engine", "torrents", "free", "download", "popular", "torrents.com"])
    form = ContactForm(request.form)
    if request.method=='POST':
        if form.validate():
            to = current_app.config["CONTACT_EMAIL"]
            try:
                mail.send(Message("contact",sender=form.email.data, recipients=[to], html="<p>%s, %s</p><p>%s</p>"%(request.remote_addr, request.user_agent, form.message.data)))
                flash("The message has been sent successfully.")
                return redirect(url_for('index.home'))

            except BaseException as e:
                flash("The message has not been sent. Try again later or send mail to %s."%to)
                logging.warn("%d: %s"%e[0].values()[0]) # se extrae el código y el mensaje de error

    g.title+=" | Contact"
    return render_template('contact.html',form=form)

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
