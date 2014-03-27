"""
textmetricsconfig - configuration for building textmetrics source data

@author: James McCracken
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lex import lexconfig

PIPELINE = (
    ('make_leanht', 0),
    ('store_leanht', 0),
    ('index_proper', 0),
    ('index_forms', 0),
    ('refine_forms', 1),
)

BASE_DIR = os.path.join(lexconfig.OED_DIR, 'projects', 'textmetrics')
FORM_INDEX_DIR = os.path.join(BASE_DIR, 'form_index')

ENTRY_MINIMUM_END_DATE = 1750
VARIANT_MINIMUM_END_DATE = 1650
MAX_WORDLENGTH = 40


DB_URL = 'postgresql://james:shapo1PSQL@localhost/wordrobot'
ENGINE = create_engine(DB_URL, client_encoding='utf8')
SESSION = sessionmaker(bind=ENGINE)()

LEANHT_DIR = os.path.join(BASE_DIR, 'leanht')


