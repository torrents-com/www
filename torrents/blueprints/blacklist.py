# -*- coding: utf-8 -*-

from flask import render_template, redirect, request, url_for, g, flash, Markup
from foofind.utils.fooprint import Fooprint
from torrents.services import *

blacklist = Fooprint('blacklist', __name__)

def op_blacklist(block, add=True):
    if " " in block:
        block = block.split(" ")
    if add:
        torrentsdb.add_blacklist(block)
    else:
        torrentsdb.del_blacklist(block)

@blacklist.route('/blacklist')
def home():
    g.section = None
    add = AddBlacklistForm(request.args)
    if add.block.data and add.validate():
        try:
            numeric = False
            block = add.block.data
            if "__" in block:
                for i in xrange(18):
                    op_blacklist(block.replace("__",str(i)), True)
            else:
                op_blacklist(block, True)

            add.block.data = ""
            flash(Markup("Word added: %s. <a href='%s'>Undo</a>" % (block, url_for('blacklist.delete', block=block))))
        except:
            flash("Error adding word.")
    words, sets = torrentsdb.get_blacklists()
    sets = [sorted(aset) for aset in sets]
    return render_template('blacklist.html', words=words, sets=sets, form=add)

@blacklist.route('/blacklist/delete/<block>')
def delete(block):
    try:
        if "__" in block:
            for i in xrange(18):
                op_blacklist(block.replace("__",str(i)), False)
        else:
            op_blacklist(block, False)
        flash(Markup("Word deleted: %s. <a href='%s?block=%s'>Undo</a>" % (block, url_for('blacklist.home'), block)))
    except:
        flash("Error deleting word.")
    return redirect(url_for('blacklist.home'))

from flask.ext.wtf import Form, TextField, Required
class AddBlacklistForm(Form):
    block = TextField("Word(s)", [Required("Required field.")])
