# -*- coding: utf-8 -*-

import os.path
from flask import render_template, current_app
from foofind.utils.fooprint import Fooprint
from foofind.services import *

news = Fooprint('news', __name__)

@cache.memoize(timeout=60*60)
def load_html_parts(filename):
    parts = {}
    open_block = None
    block_content = []
    full_filename = os.path.join(current_app.root_path, 'news', filename, "index.html")
    with open(full_filename) as input_file:
        for line in input_file:
            if open_block:
                if line.startswith("<!--}-->"):
                    parts[open_block] = "".join(block_content).decode("UTF-8")
                    block_content = []
                    open_block = None
                else:
                    block_content.append(line)
            else:
                if line.startswith("<!--{ "):
                    open_block = line[6:-4]

    return parts

@news.route('/news')
@news.route('/news/<path:path>')
def main(path=""):
    g.override_header = True
    path_parts = load_html_parts(path)
    return render_template('news.html', **path_parts)
