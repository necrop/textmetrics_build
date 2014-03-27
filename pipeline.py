"""
pipeline -- runs processes for building data for the text analysis app.

@author: James McCracken
"""

import textmetricsconfig


def dispatch():
    for function_name, status in textmetricsconfig.PIPELINE:
        if status:
            print('=' * 30)
            print('Running "%s"...' % function_name)
            print('=' * 30)
            function = globals()[function_name]
            function()


def make_leanht():
    from leanht.makeleanht import make_lean_ht
    make_lean_ht()


def store_leanht():
    from leanht.storetodb import store_content, store_taxonomy
    store_taxonomy()
    store_content()


def index_proper():
    from build.formindexer import FormIndexer
    form_indexer = FormIndexer()
    form_indexer.index_proper_names()


def index_forms():
    from build.formindexer import FormIndexer
    form_indexer = FormIndexer()
    form_indexer.index_raw_forms()


def refine_forms():
    from build.formindexer import FormIndexer
    form_indexer = FormIndexer()
    form_indexer.refine_index()


if __name__ == '__main__':
    dispatch()
