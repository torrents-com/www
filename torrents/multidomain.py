# -*- coding: utf-8 -*-
import re, flask
from newrelic.agent import transaction_name
from flask import g, url_for as flask_url_for, redirect, Blueprint, request, current_app, _request_ctx_stack

DOMAIN_SUFFIX = ""
_MultidomainBlueprint__rule_domains = {}
_MultidomainBlueprint__endpoint_domain = {}

DOMAIN_REPLACER=re.compile(r"^(https?://)[^\/?]*(.*)$")

def redirect_to_domain(domain, http_code):
    return redirect(DOMAIN_REPLACER.sub(r"\1"+domain + DOMAIN_SUFFIX + r"\2", request.url), http_code)

def multidomain_view(*args, **kwargs):
    domains = _MultidomainBlueprint__rule_domains[request.url_rule.rule]
    info = domains.get(g.domain, None)
    if info:
        if info[0]!=request.blueprint:
            g.domain_conflict = True
            request.url_rule = next(r for r in _request_ctx_stack.top.url_adapter.map._rules if r.rule==request.url_rule.rule and r.endpoint.startswith(info[0]+"."))
        return info[1](*args, **kwargs)
    else:
        return redirect_to_domain(domains.iterkeys().next(), 301)

def url_for(endpoint, **values):
    # check for language change order
    target_lang = values.pop("_lang", g.lang)

    # absolute URL?
    external = values.pop("_external", False)

    # allows to use "." for current path
    if endpoint==".":
        endpoint = request.endpoint
        path = request.script_root + request.path
        if request.query_string:
            path += "?"+request.query_string
    else:
        path = flask_url_for(endpoint, **values)

    # check for domain change order
    target_domain = values.pop("_domain", _MultidomainBlueprint__endpoint_domain.get(endpoint, None))

    # if must change anything overrides this method
    if external or (target_domain and target_domain != g.domain) or (target_lang and target_lang!=g.lang) :
        if target_lang and target_domain in g.translate_domains and target_lang!=g.langs[0]:
            return "http://"+ target_lang + "." + target_domain + DOMAIN_SUFFIX + path
        else:
            return "http://"+ target_domain + DOMAIN_SUFFIX + path

    return path

def patch_flask():
    global flask
    flask.url_for = url_for

class MultidomainBlueprint(Blueprint):
    '''
    Blueprint for multiple domains handling.
    '''
    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop("domain") if "domain" in kwargs else None
        Blueprint.__init__(self, *args, **kwargs)

    def route(self, rule, **options):
        def decorator(f):
            endpoint = options.pop("endpoint", f.__name__)
            self.add_url_rule(rule, endpoint, f, **options)
            return f
        return decorator

    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        if self.domain:
            # Add rule to domain mapping
            if rule in __rule_domains:
                __rule_domains[rule][self.domain] = (self.name, transaction_name()(view_func))
            else:
                __rule_domains[rule] = {self.domain: (self.name, transaction_name()(view_func))}

            # Add endpoint to domain mapping
            __endpoint_domain[self.name+"."+endpoint] = self.domain

            return Blueprint.add_url_rule(self, rule, endpoint, multidomain_view, **options)
        else:
            return Blueprint.add_url_rule(self, rule, endpoint, view_func, **options)
