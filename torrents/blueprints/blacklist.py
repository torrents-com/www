# -*- coding: utf-8 -*-

from flask import render_template, redirect, request, url_for, g, flash, Markup

from foofind.utils import logging
from torrents.multidomain import MultidomainBlueprint
from foofind.services import *
from torrents.services import *
import urllib

blacklist = MultidomainBlueprint('blacklist', __name__, domain="torrents.fm")

def parse_entry(text):
    if "+" in text:
        return [word.strip() for word in text.split("+") if word.strip()]
    else:
        return text.strip()

@blacklist.route('/blacklist')
def home():
    form = BlacklistForm(request.args)
    if form.action.data=="add" and form.validate():
        try:
            text = form.text.data
            category = form.category.data
            if "_age_" in text:
                for i in xrange(18):
                    torrentsdb.add_blacklist_entry(category, parse_entry(text.replace("_age_",str(i))))
            else:
                torrentsdb.add_blacklist_entry(category, parse_entry(text))

            # Avisa para que se refresque las blacklist en la web y fuerza a que se haga en este hilo antes de mostrar la lista actualizada
            configdb.run_action("refresh_blacklists")
            configdb.pull_actions()

            form.text.data = ""
            flash(Markup("Entry added: %s. <a href='%s'>Undo</a>" % (text, url_for('blacklist.delete', category=category, text=text))))
        except BaseException as e:
            logging.exception(e)
            flash("Error adding entry.")

    return render_template('blacklist.html', blacklists=blacklists, form=form)

@blacklist.route('/blacklist/delete/<category>/<text>')
def delete(category, text):
    try:
        if "_age_" in text:
            for i in xrange(18):
                torrentsdb.remove_blacklist_entry(category, parse_entry(text.replace("_age_",str(i))))
        else:
            torrentsdb.remove_blacklist_entry(category, parse_entry(text))

        # Avisa para que se refresque las blacklist en la web y fuerza a que se haga en este hilo antes de mostrar la lista actualizada
        configdb.run_action("refresh_blacklists")
        configdb.pull_actions()

        flash(Markup("Entry deleted: %s. <a href='%s?category=%s&text=%s'>Undo</a>" % (text, url_for('blacklist.home'), category, urllib.quote(text))))
    except BaseException as e:
        logging.exception(e)
        flash("Error deleting entry.")
    return redirect(url_for('blacklist.home'))

from flask.ext.wtf import Form, TextField, Required, SelectField, HiddenField
class BlacklistForm(Form):
    action = HiddenField("Action")
    text = TextField("Word(s)", [Required("Required field.")])
    test = TextField("Word(s)")
    category = SelectField("Category", choices=[('forbidden','Forbidden'),('underage','Underage'),('misconduct','Misconduct'),('spamsearch','Spam Search'),('searchblocked','Search Blocked')])
