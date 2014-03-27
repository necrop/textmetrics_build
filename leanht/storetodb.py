

from lex.oed.thesaurus.contentiterator import ContentIterator
from lex.oed.thesaurus.taxonomymanager import TaxonomyManager
from leanht.models import ThesClass, ThesInstance
import textmetricsconfig

IN_DIR = textmetricsconfig.LEANHT_DIR
DB_ENGINE = textmetricsconfig.ENGINE
DB_SESSION = textmetricsconfig.SESSION


def store_taxonomy():
    ThesInstance.__table__.drop(DB_ENGINE, checkfirst=True)
    ThesClass.__table__.drop(DB_ENGINE, checkfirst=True)
    ThesClass.__table__.create(DB_ENGINE, checkfirst=True)

    ci = ContentIterator(path=IN_DIR, fixLigatures=True, verbosity='low')
    valid_ids = {thesclass.id(): thesclass.size()
                 for thesclass in ci.iterate()}

    tree_manager = TaxonomyManager(lazy=True, verbosity=None)
    for level in range(1, 20):
        classes = [c for c in tree_manager.classes if c.level() == level
                   and c.id() in valid_ids]
        print(level, len(classes))
        buffer_size = 0
        for thesaurus_class in classes:
            revised_size = valid_ids[thesaurus_class.id()]
            record = ThesClass(thesaurus_class, size=revised_size)
            DB_SESSION.add(record)
            buffer_size += 1
            if buffer_size > 1000:
                DB_SESSION.commit()
                buffer_size = 0
        DB_SESSION.commit()


def store_content():
    ThesInstance.__table__.drop(DB_ENGINE, checkfirst=True)
    ThesInstance.__table__.create(DB_ENGINE, checkfirst=True)

    ci = ContentIterator(path=IN_DIR, fixLigatures=True, verbosity='low')
    buffer_size = 0
    for thesclass in ci.iterate():
        for instance in thesclass.instances():
            record_data = {
                'lemma': instance.lemma(),
                'refentry': instance.refentry(),
                'refid': instance.refid(),
                'start_year': instance.start_date(),
                'end_year': instance.end_date(),
                'class_id': thesclass.id(),
            }
            DB_SESSION.add(ThesInstance(record_data))
            buffer_size += 1
        if buffer_size > 1000:
            DB_SESSION.commit()
            buffer_size = 0
    DB_SESSION.commit()
