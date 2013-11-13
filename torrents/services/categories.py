# -*- coding: utf-8 -*-

class CategoriesCache:
    def init_app(self, categories):
        self.categories = categories
        self.categories_by_url = {category.url:category for category in categories}

    def update_subcategories(self, subcategories):
        for category in self.categories:
            category.subcategories[:] = [subcat for subcat, info in sorted(subcategories[category.tag].iteritems(), key=lambda x:-x[1].get("c",0)) if info.get("c",0)>0]
            category.dynamic_tags[:] = [subcat.replace(" ","") for subcat in category.subcategories]
