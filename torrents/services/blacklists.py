# -*- coding: utf-8 -*-

def prepare_phrase(phrase):
    return " "+phrase.lower().strip()+" "

class Blacklists:
    def __init__(self):
        self.debug = False

    def load_data(self, data):
        self.categories = {category:BlacklistCategory(category, entries, self.debug) for category, entries in data.iteritems()}

    def __iter__(self):
        return self.categories.itervalues()

    def __getitem__(self, category):
        return self.categories.get(category, None)

    def __contains__(self, phrase):
        if self.debug:
            assert phrase == prepare_phrase(phrase)
        return any(phrase in cat for cat in self.categories.itervalues())

    def prepare_phrase(self, phrase):
        return prepare_phrase(phrase)

    def clone_into(self, new_blacklist, ffilter):
        new_blacklist.categories = {key:value for key, value in self.categories.iteritems() if ffilter(key)}
        new_blacklist.debug = self.debug

class BlacklistCategory:
    def __init__(self, name, entries, debug):
        self.debug = debug
        self.name = name
        self.texts = [entry for entry in entries if isinstance(entry, (str,unicode))]
        self.groups = [entry for entry in entries if isinstance(entry, list)]
        self.search_texts = [" "+text+" " for text in self.texts]
        self.search_groups = [[" "+text+" " for text in texts] for texts in self.groups]

    def __contains__(self, phrase):
        if self.debug:
            assert phrase == prepare_phrase(phrase)
        return any(text in phrase for text in self.search_texts) or any(all(text in phrase for text in texts) for texts in self.search_groups)

    def count(self, phrase):
        if self.debug:
            assert phrase == prepare_phrase(phrase)
        return sum(1 for text in self.search_texts if text in phrase) + sum(1 for texts in self.search_groups if all(text in phrase for text in texts))

    def exact(self, phrase):
        return phrase in self.texts
