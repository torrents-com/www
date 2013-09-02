import re, flask
from flask import g, url_for as flask_url_for, redirect, Blueprint, request, current_app

DOMAIN_SUFFIX = ""
_MultidomainBlueprint__rule_domains = {}
_MultidomainBlueprint__endpoint_domain = {}

DOMAIN_REPLACER=re.compile(r"^(https?://)[^\/?\:]*(.*)$")

def multidomain_view(*args, **kwargs):
    domains = _MultidomainBlueprint__rule_domains[request.url_rule.rule]
    view_func = domains.get(g.domain, None)
    if view_func:
        return view_func(*args, **kwargs)
    else:
        return redirect(DOMAIN_REPLACER.sub(r"\1"+domains.iterkeys().next()+r"\2", request.url.decode("utf-8")), 301)

def url_for(endpoint, **values):
    domain = _MultidomainBlueprint__endpoint_domain.get(endpoint, None)
    if domain and domain != g.domain:
        values["_external"]=False # Remove external parameter for flask
        return "http://"+ domain + DOMAIN_SUFFIX + flask_url_for(endpoint, **values)
    return flask_url_for(endpoint, **values)
flask.url_for = url_for

class MultidomainBlueprint(Blueprint):
    '''
    Blueprint for multiple domains handling.
    '''
    def __init__(self, *args, **kwargs):

        if "domain" in kwargs:
            domain = kwargs.pop("domain")
            self.domain = domain
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
                __rule_domains[rule][self.domain] = view_func
            else:
                __rule_domains[rule] = {self.domain: view_func}

            # Add endpoint to domain mapping
            __endpoint_domain[self.name+"."+endpoint] = self.domain

            return Blueprint.add_url_rule(self, rule, endpoint, multidomain_view, **options)
        else:
            return Blueprint.add_url_rule(self, rule, endpoint, view_func, **options)
