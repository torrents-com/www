# -*- coding: utf-8 -*-

import os.path, re, urllib2, json, math
from flask import render_template, current_app, g, send_from_directory, abort, make_response, request, url_for
from flask.ext.mail import Message
from torrents.multidomain import MultidomainBlueprint, empty_redirect
from foofind.utils import logging
from foofind.utils.fooprint import Fooprint
from foofind.services import *

news = MultidomainBlueprint('news', __name__, domain="torrents.com")

def fix_urls(content, external=False):
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

    # el fichero no existe
    if not os.path.exists(full_filename):
        return abort(404)

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
    g.must_cache = 86400
    g.override_header = True
    path_parts = load_html_parts(path)

    if not path_parts:
        return abort(404)

    if not path:
        g.keywords.clear()
        g.keywords.update(["movies", "tv", "video", "music", "torrents", "software"])

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

@news.route('/news/feed/')
def rss():
    g.cache_code += "N"
    return fix_response('feed/index.html', "application/rss+xml")

@news.route('/news/rss')
def old_rss():
    g.cache_code = "S"
    return empty_redirect(url_for("news.rss"), 301)


@news.route('/downloader')
def old_downloader():
    g.cache_code = "S"
    return empty_redirect(url_for("web.home"), 301)

@news.route('/popular')
def old_popular_torrents():
    g.cache_code = "S"
    return empty_redirect(url_for("files.popular_torrents", interval="month"), 301)

@news.route('/recent')
def old_recent_torrents():
    g.cache_code = "S"
    return empty_redirect(url_for("files.popular_torrents", interval="today"), 301)

@news.route('/popular_searches')
def old_popular_searches():
    g.cache_code = "S"
    return empty_redirect(url_for("files.popular_searches", interval="today"), 301)

@news.route('/robots.txt')
def robots():
    g.cache_code = "S"
    full_filename = os.path.join(os.path.join(current_app.root_path, 'static'), 'robots.txt')

    with open(full_filename) as input_file:
        response = make_response(input_file.read() + "\n\nUser-agent: Googlebot\nDisallow: /search/*\n"+"".join("Disallow: /%s/*\n"%cat.url for cat in g.categories) + "\nSitemap: "+ url_for("news.main_sitemap", _external=True) + "\nSitemap: "+ url_for(".static_sitemap", _external=True))
        response.mimetype='text/plain'
    return response

@news.route('/st_sitemap.xml')
def static_sitemap():
    g.cache_code += "SN"
    pages = [url_for(page, _external=True) for page in ("news.home", ".about", ".legal", ".contact")]
    response = make_response(render_template('sitemap.xml', pages = pages))
    response.mimetype='text/xml'
    return response

LIST_FINDER = re.compile("(?:<h4.*?</h4>\s*)?<ul...+?</ul>", re.M+re.U+re.I+re.S)
@news.route('/smap')
def user_sitemap():
    g.cache_code += "N"

    with open(os.path.join(current_app.root_path, 'news', 'wp-json.php', 'posts', 'types', 'post', 'taxonomies', 'category', 'terms')) as json_file:
        posts_categories = json.load(json_file)
    with open(os.path.join(current_app.root_path, 'news', 'wp-json.php', 'posts', 'types', 'post', 'taxonomies', 'post_tag', 'terms')) as json_file:
        posts_tags = json.load(json_file)

    structure = [[("Home page", url_for("news.home"), [("About us", url_for(".about")), ("Terms & privacy", url_for(".legal")), ("Contact us", url_for(".contact"))]), ("News categories", None, [(cat["name"], url_for("news.home", path="category/"+cat["slug"])) for cat in posts_categories.itervalues() if cat["count"]>0])]]

    sorted_tags = sorted([(tag["name"], url_for("news.home", path="tag/"+tag["slug"])) for tag in posts_tags.itervalues() if tag["count"]>0], key=lambda x:x[0].lower())

    column_size = int(math.ceil(len(sorted_tags)/3.))

    for i in xrange(3):
        column_tags = sorted_tags[i*column_size:(i+1)*column_size]
        structure.append([("Tags "+column_tags[0][0][0].upper()+"-"+column_tags[-1][0][0].upper(), None, column_tags)])


    return render_template('sitemap.html', structure=structure, column_count=4, column_width=5)

@news.route('/about')
def about():
    g.cache_code = "S"
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrents", "torrents.com", "search engine", "download", "free", "movie", "software", "popular largest"])
    g.title.append("About us")
    return render_template('about.html')

@news.route('/products')
def products():
    g.cache_code = "S"
    g.category=False
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    g.keywords.clear()
    g.keywords.update(["torrents", "torrents.com", "search engine", "download", "free", "movie", "software", "popular largest"])
    g.title.append("Our products")
    return render_template('products.html')

@news.route('/legal')
def legal():
    g.cache_code = "S"
    g.category=False
    g.title.append("Terms & privacy")
    g.keywords.clear()
    g.keywords.update(["torrents search engine privacy terms of use"])
    g.page_description = "Torrents.com is a free torrent search engine that offers users fast, simple, easy access to every torrent in one place."
    return render_template('legal.html')

@news.route('/contact', methods=["GET","POST"])
def contact():
    '''
    Muestra el formulario para reportar enlaces
    '''
    g.cache_code = "S"
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
                return empty_redirect(url_for('.home', _anchor="sent"))

            except BaseException as e:
                g.alert["mail_error"] = ("error", "The message has not been sent. Try again later or send mail to %s."%to)
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
