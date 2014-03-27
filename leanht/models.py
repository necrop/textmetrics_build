"""
Db models used for HT-lean database:

ThesClass
ThesInstance
"""

import re

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.dialects import mysql as sa_mysql

Base = declarative_base()


class ThesClass(Base):
    __tablename__ = 'tm_thesaurusclass'

    id = Column(Integer, primary_key=True)
    label = Column(String(200))
    level = Column(Integer)
    wordclass = Column(String(20))
    node_size = Column(Integer, nullable=False)
    branch_size = Column(Integer, nullable=False)

    parent_id = Column(Integer, ForeignKey('tm_thesaurusclass.id'))
    children = relationship('ThesClass',
                            backref=backref('parent', remote_side=[id]))

    def __init__(self, thesaurus_class, **kwargs):
        self.id = thesaurus_class.id()
        self.label = thesaurus_class.label() or None
        self.level = thesaurus_class.level()
        self.wordclass = thesaurus_class.wordclass(penn=True)
        self.node_size = kwargs.get('size') or thesaurus_class.size(branch=False)
        self.branch_size = thesaurus_class.size(branch=True)
        self.parent_id = thesaurus_class.parent()
        if self.label is not None:
            self.label = self.label[0:200]

    def __repr__(self):
        return '<ThesClass %d (%s)>' % (self.id, self.signature())

    def __eq__(self, other):
        return int(self.id) == int(other.id)

    def __hash__(self):
        return int(self.id)

    def signature(self):
        sig = ''
        if self.wordclass is not None:
            sig += '[' + self.wordclass + '] '
        if self.label is not None and self.label:
            sig += self.label
        return sig.strip()

    #========================================================
    # Functions for displaying the class breadcrumb as a string
    #========================================================

    def breadcrumb_components(self):
        try:
            return self._breadcrumb_components
        except AttributeError:
            self._breadcrumb_components = []
            for ancestor in reversed(self.ancestors()):
                self._breadcrumb_components.append(ancestor.signature())
            return self._breadcrumb_components

    def breadcrumb(self):
        return ' > '.join(self.breadcrumb_components()[1:])

    def breadcrumb_tail(self):
        return ' > '.join(self.breadcrumb_components()[-3:])

    def breadcrumb_short(self):
        return ' > '.join(self.breadcrumb_components()[1:3]) + ' ... ' + \
            ' > '.join(self.breadcrumb_components()[-3:])

    #========================================================
    # Functions for finding descendants and ancestors
    #========================================================

    def ancestors(self):
        """
        Return a list of ancestor classes in ascending order,
        beginning with self.

        Note that that the present class is included as the first element
        of the list
        """
        try:
            return self._ancestors
        except AttributeError:
            self._ancestors = [self, ]
            if self.parent is not None:
                parent = self.parent
                while parent is not None:
                    self._ancestors.append(parent)
                    try:
                        parent = parent.parent
                    except NoResultFound:
                        parent = None
            return self._ancestors

    def ancestors_ascending(self):
        return self.ancestors()

    def ancestors_descending(self):
        try:
            return self._ancestors_descending
        except AttributeError:
            self._ancestors_descending = list(reversed(self.ancestors()))
            return self._ancestors_descending

    def ancestor_ids(self):
        return set([a.id for a in self.ancestors()])

    def ancestor(self, level=1):
        """
        Return the ancestor class at ancestor specified level (defaults to 1)
        """
        if self.level == level:
            return self
        for ancestor in self.ancestors():
            if ancestor.level == level:
                return ancestor
        return None

    def is_descendant_of(self, class_id):
        """
        Return True is the present class is a descendant of the argument.

        Argument can be either another ThesaurusClass object, or a
        thesaurus class ID
        """
        if class_id is None or not class_id:
            return False
        if isinstance(class_id, ThesClass):
            class_id = class_id.id
        class_id = int(class_id)
        if class_id in [a.id for a in self.ancestors()]:
            return True
        else:
            return False

    def descendants(self):
        """
        Recursively list all descendant classes
        """
        def recurse(node, stack):
            stack.append(node)
            for child in node.children:
                stack = recurse(child, stack)
            return stack

        descendants = []
        for child in self.children:
            descendants = recurse(child, descendants)
        return descendants

    def oed_url(self):
        """
        Return the URL to this class in OED Online
        """
        return 'http://www.oed.com/view/th/class/%d' % self.id


class ThesInstance(Base):
    __tablename__ = 'tm_thesaurusinstance'

    id = Column(Integer, primary_key=True)
    lemma = Column(String(100), index=True)
    refentry = Column(Integer, nullable=False, index=True)
    refid = Column(Integer, nullable=False, index=True)
    start_year = Column(Integer)
    end_year = Column(Integer)

    class_id = Column(Integer, ForeignKey('tm_thesaurusclass.id'))
    thesclass = relationship('ThesClass', backref=backref('instances'))

    def __init__(self, data):
        for key, value in data.items():
            self.__dict__[key] = value
        if self.lemma is not None:
            self.lemma = self.lemma[0:100]

    def __repr__(self):
        if self.thesclass is not None:
            return '<ThesInstance (%s, %d#eid%d, HTclass=%d)>' % (self.lemma,
                self.refentry, self.refid, self.thesclass.id)
        else:
            return '<ThesInstance (%s, %d#eid%d, HTclass=null)>' % (self.lemma,
                self.refentry, self.refid)

    def breadcrumb(self):
        if self.thesclass is None:
            return ''
        else:
            return self.thesclass.breadcrumb()

    def oed_url(self):
        return 'http://www.oed.com/view/Entry/%d#eid%d' % (self.refentry,
                                                           self.refid)
