# -*- coding: utf-8 -*-
from flask import session, request
from flask.ext.login import UserMixin, AnonymousUser as AnonymousUserMixin
from datetime import datetime
from time import time

from foofind.services import *
from foofind.utils import logging

class UserBase(object):
    id = 0
    def __init__(self, data):
        pass

    @classmethod
    def current_user(cls, userid = None):
        return AnonymousUser(None)

class User(UserMixin, UserBase):
    '''
    Guarda los datos de usuario en sesión.
    '''
    def __init__(self, user_id, data = None):
        UserBase.__init__(self, data)
        self.id = 0

class AnonymousUser(AnonymousUserMixin, UserBase):
    def __init__(self, data):
        UserBase.__init__(self, data)
        self.id = 0
