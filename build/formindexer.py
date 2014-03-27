"""
FormIndexer

@author: James McCracken
"""

import os
import string
from collections import namedtuple, defaultdict
import pickle
import json

import stringtools
from lex.gel.fileiterator import entry_iterator
from lex.propernames import propernames
from lex.oed.resources.vitalstatistics import VitalStatisticsCache
from lex.oed.resources.mainsenses import MainSensesCache
import textmetricsconfig

FORM_INDEX_DIR = textmetricsconfig.FORM_INDEX_DIR
ENTRY_MINIMUM_END_DATE = textmetricsconfig.ENTRY_MINIMUM_END_DATE
VARIANT_MINIMUM_END_DATE = textmetricsconfig.VARIANT_MINIMUM_END_DATE
MAX_WORDLENGTH = textmetricsconfig.MAX_WORDLENGTH

BlockData = namedtuple('BlockData', ['refentry', 'refid', 'type', 'sort',
            'lemma', 'wordclass', 'definition', 'frequency',
            'start', 'end', 'language', 'standard_types',
            'variant_types', 'alien_types'])


class FormIndexer(object):

    def __init__(self):
        pass

    def index_raw_forms(self):
        for letter in string.ascii_lowercase:
            print('Indexing %s...' % letter)
            blocks = []
            for entry in entry_iterator(letters=letter):
                if (entry.date().end < ENTRY_MINIMUM_END_DATE or
                        entry.primary_wordclass() in ('NP', 'NPS') or
                        len(entry.lemma) > MAX_WORDLENGTH):
                    continue
                entry_type = entry.oed_entry_type()
                if entry_type is None:
                    continue
                seen = set()
                for block in entry.wordclass_sets():
                    # Check that this block is in OED, and does not shadow
                    #  something already covered (as e.g. vast adv. shadows
                    #  vast adj.).
                    refentry, refid = block.link(target='oed', asTuple=True)
                    if not refentry or (refentry, refid) in seen:
                        continue
                    block_data = _store_forms(block, entry, entry_type, letter)
                    if block_data.standard_types:
                        blocks.append(block_data)
                    seen.add((refentry, refid))

            out_file = os.path.join(FORM_INDEX_DIR, 'raw', letter)
            with open(out_file, 'wb') as filehandle:
                for block in blocks:
                    pickle.dump(block, filehandle)

    def refine_index(self):
        allowed_alien_types = _filter_alien_types()

        vitalstats = VitalStatisticsCache()
        main_sense_checker = MainSensesCache(with_definitions=True)
        for letter in string.ascii_lowercase:
            print('Refining index for %s...' % letter)
            blocks = []
            for block in raw_pickle_iterator(letter):
                blocks.append(block)

            # Remove duplicate types, so that only the version
            #  in the block with the highest frequency is retained.
            standardmap = defaultdict(list)
            for i, block in enumerate(blocks):
                for wordform in block.standard_types:
                    standardmap[wordform].append((i, block.frequency))
            for wordform, candidates in standardmap.items():
                if len(candidates) > 1:
                    # Sort by frequency
                    candidates.sort(key=lambda c: c[1], reverse=True)
                    # Remove the first candidate (the highest-frequency
                    #  one); this is the one we'll keep.
                    candidates.pop(0)
                    # Delete all the rest
                    for index in [c[0] for c in candidates]:
                        blocks[index].standard_types.discard(wordform)

            # Remove variant types which either duplicate each other
            #  or that shadow a standard type (standard types are always
            #  given precedence).
            varmap = defaultdict(list)
            for i, block in enumerate(blocks):
                for wordform in block.variant_types:
                    varmap[wordform].append((i, block.frequency))
            for wordform, candidates in varmap.items():
                if wordform not in standardmap:
                    # Sort by frequency
                    candidates.sort(key=lambda c: c[1], reverse=True)
                    # Remove the first candidate (the highest-frequency
                    #  one); this is the one we'll keep.
                    candidates.pop(0)
                # Delete all the rest
                for index in [c[0] for c in candidates]:
                    blocks[index].variant_types.discard(wordform)

            # Remove any alien types that are not allowed (because they
            #  shadow other standard types or variants).
            for block in blocks:
                to_be_deleted = set()
                for wordform in block.alien_types:
                    if wordform not in allowed_alien_types:
                        to_be_deleted.add(wordform)
                for wordform in to_be_deleted:
                    block.alien_types.discard(wordform)

            # Remove any blocks whose standard_types and
            #  variant_types sets have now been completely emptied
            # For the remainder, turn standard_forms and variant_forms
            #  from sets into lists
            blocks = [_listify_forms(b) for b in blocks if b.standard_types
                      or b.variant_types]

            blocks_filtered = []
            for block in blocks:
                language = vitalstats.find(block.refentry,
                                           field='indirect_language')
                if not language and block.start and block.start < 1200:
                    language = 'West Germanic'
                block = _replace_language(block, language)

                if block.type == 'entry':
                    # Make sure we use the OED headword, not the headword
                    #  that's been used in GEL (which could be the version
                    #  of the headword found in ODE or NOAD).
                    headword = vitalstats.find(block.refentry,
                                               field='headword')
                    if headword and headword != block.lemma:
                        block = _replace_lemma(block, headword)
                    # Make sure we use the correct main-sense definition
                    main_sense = main_sense_checker.find_main_sense_data(
                        block.refentry,
                        block.refid)
                    if main_sense and main_sense.definition:
                        block = _replace_definition(block, main_sense.definition)
                blocks_filtered.append(block)

            out_file = os.path.join(FORM_INDEX_DIR, 'refined', letter + '.json')
            with open(out_file, 'w') as filehandle:
                for block in blocks_filtered:
                    filehandle.write(json.dumps(block) + '\n')

    def index_proper_names(self):
        allnames = set()
        for name_type in ('firstname', 'surname', 'placename'):
            for name in propernames.names_list(name_type):
                if ' ' in name:
                    continue
                allnames.add(name)

        for letter in string.ascii_lowercase:
            print('Indexing proper names in %s...' % letter)
            for entry in entry_iterator(letters=letter):
                if entry.primary_wordclass() not in ('NP', 'NPS'):
                    continue
                for typeunit in entry.types():
                    if (' ' in typeunit.form or
                        not typeunit.lemma_manager().capitalization_type() == 'capitalized'):
                        continue
                    allnames.add(typeunit.form)

        out_file = os.path.join(FORM_INDEX_DIR, 'proper_names', 'all.txt')
        with open(out_file, 'w') as filehandle:
            for name in allnames:
                sortable = stringtools.lexical_sort(name)
                if (not sortable or
                        len(sortable) > MAX_WORDLENGTH or
                        len(name) > MAX_WORDLENGTH):
                    continue
                filehandle.write('%s\t%s\t%s\n' % (sortable,
                                                   name,
                                                   str(propernames.is_common(name))))


def raw_pickle_iterator(letter):
    in_file = os.path.join(FORM_INDEX_DIR, 'raw', letter.lower())
    with open(in_file, 'rb') as filehandle:
        while 1:
            try:
                block = pickle.load(filehandle)
            except EOFError:
                break
            else:
                yield(block)


def _store_forms(block, entry, block_type, letter):
    us_variant = entry.us_variant()
    standardtypes = set()
    varianttypes = set()
    alientypes = set()
    for morphset in block.morphsets():
        if morphset.form in (entry.lemma, us_variant, block.lemma):
            _add_types(morphset, standardtypes, letter)
        elif (block_type == 'entry' and
                morphset.date().end > VARIANT_MINIMUM_END_DATE and
                not morphset.is_nonstandard()):
            # Don't store variants for subentries; don't store
            #  very old or non-standard variants
            _add_types(morphset, varianttypes, letter)
            _add_alien_variants(morphset, alientypes, letter)
    varianttypes = varianttypes - standardtypes
    alientypes = alientypes - standardtypes

    refentry, refid = block.link(target='oed', asTuple=True)

    frequency = block.frequency()
    if frequency is not None:
        frequency = float('%.2g' % frequency)
        if frequency > 1:
            frequency = int(frequency)

    definition = block.definition(src='oed') or None

    return BlockData(refentry,
                     refid,
                     block_type,
                     stringtools.lexical_sort(block.lemma),
                     block.lemma,
                     block.wordclass(),
                     definition,
                     frequency,
                     block.date().exact('start'),
                     block.date().exact('end'),
                     None,
                     standardtypes,
                     varianttypes,
                     alientypes,)


def _add_types(morphset, target_set, letter):
    for t in morphset.types():
        if len(t.sort) > MAX_WORDLENGTH or len(t.form) > MAX_WORDLENGTH:
            continue
        if not t.sort.startswith(letter):
            continue
        target_set.add((t.sort, t.form))


def _add_alien_variants(morphset, target_set, letter):
    """
    Store variants that start with a letter *other* than the current
    letter (e.g. 'cimiter' under 'scimitar').
    """
    for t in morphset.types():
        if len(t.sort) > MAX_WORDLENGTH or len(t.form) > MAX_WORDLENGTH:
            continue
        if t.sort.startswith(letter):
            continue
        target_set.add((t.sort, t.form))


def _listify_forms(entry):
    return entry._replace(standard_types=list(entry.standard_types),
                          variant_types=list(entry.variant_types),
                          alien_types=list(entry.alien_types))


def _replace_lemma(entry, headword):
    return entry._replace(lemma=headword, sort=stringtools.lexical_sort(headword))


def _replace_definition(entry, definition):
    if definition != entry.definition:
        print('------------------------------------------------------------')
        print(entry.lemma)
        print(entry.definition)
        print(definition)
        return entry._replace(definition=definition)
    else:
        return entry


def _replace_language(entry, language):
    if language:
        language = language.split('/')[-1]
    if language == 'English':
        language = 'West Germanic'
    if (entry.start < 1150 and
            (not language or language.lower() in ('unknown', 'undefined', 'origin uncertain'))):
        language = 'West Germanic'
    if (entry.start < 1200 and
            (not language or language.lower() in ('undefined',))):
        language = 'West Germanic'
    return entry._replace(language=language)


def _filter_alien_types():
    """
    Check which alien types can be kept.
    (Alien types are variants
    which begin with a different letter from the standard lemma form,
    and which therefore may shadow lemmas or variants in other
    letter sets.)
    """
    # Store all the alien types
    alien_types = set()
    for letter in string.ascii_lowercase:
        for block in raw_pickle_iterator(letter):
            alien_types = alien_types | block.alien_types

    # Delete any which shadow standard types or other variants (ie. those
    #  which are not aliens, in their own letter sets).
    for letter in string.ascii_lowercase:
        for block in raw_pickle_iterator(letter):
            for typelist in (block.standard_types, block.variant_types):
                for wordform in typelist:
                    try:
                        alien_types.discard(wordform)
                    except KeyError:
                        pass

    return alien_types


