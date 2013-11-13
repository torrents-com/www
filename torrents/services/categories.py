# -*- coding: utf-8 -*-

class CategoriesCache:
    def init_app(self, categories, min_occurs):
        self.categories = categories
        self.categories_by_url = {category.url:category for category in categories}
        self.min_occurs = min_occurs

    def update_subcategories(self, subcategories):
        for category in self.categories:
            category.all_subcategories.update({subcat for subcat in subcategories[category.tag].iterkeys()})
            category.subcategories[:] = [subcat for subcat, info in sorted(subcategories[category.tag].iteritems(), key=lambda x:-x[1].get("c",0)) if info.get("c",0)>=self.min_occurs]
            category.dynamic_tags[:] = [subcat.replace(" ","") for subcat in category.all_subcategories]
