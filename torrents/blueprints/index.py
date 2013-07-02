# -*- coding: utf-8 -*-
import os, re
from flask import flash, redirect, url_for, render_template, send_from_directory, current_app, make_response, request, g
from flask.ext.mail import Message

from foofind.utils import logging
from foofind.utils.fooprint import Fooprint
from foofind.services import *
from torrents.services import *
from .files import get_rankings, get_popular_searches, get_last_searches

index = Fooprint('index', __name__)


@index.route('/')
def home():
    '''
    Renderiza la portada.
    '''
    g.page_description = "A free torrent search engine providing download results for movies, software and other torrent files."
    g.keywords.clear()
    g.keywords.update(["torrents", "search engine", "free download", "music", "online", "movie", "games", "TV", "music", "Anime", "Books", "Adult", "Porn", "Spoken word", "Software", "Mobile", "Pictures"])
    
    pop_searches = get_popular_searches(50, 10)
    rankings, featured = get_rankings()

    return render_template('index.html', rankings = rankings, pop_searches = dict(pop_searches), featured=featured)

@index.route('/popular_searches')
def popular_searches():
    '''
    Renderiza la página de búsquedas populares.
    '''
    g.category=False
    g.keywords.clear()
    g.keywords.update(["populartorrent", "free movie", "full download", "search engine", "largest"])
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.title+=" | Popular searches"
    g.h1 = "See up to the minute results for most popular torrent searches ranging from movies to music."
    pop_searches = get_popular_searches(500, 50)
    return render_template('popular.html', pop_searches = dict(pop_searches))

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
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrents", "torrents.com", "search engine", "download", "free", "movie", "software", "popular largest"])
    g.title+=" | About"
    return render_template('about.html')

@index.route('/legal')
def legal():
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
