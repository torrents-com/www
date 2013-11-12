# -*- coding: utf-8 -*-
from collections import namedtuple
class Category(namedtuple('Category', ['cat_id','url','title','tag','content','content_main','adult_content','subcategories'])):
    def __new__(cls, cat_id, url, title, tag, content, content_main, adult_content):
        return super(Category, cls).__new__(cls, cat_id, url, title, tag, content, content_main, adult_content, [])
