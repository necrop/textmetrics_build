
import re

from lex.oed.thesaurus.contentiterator import ContentIterator
from lex.oed.resources.mainsenses import MainSensesCache
import textmetricsconfig

MAIN_SENSE_CHECKER = MainSensesCache()
OUT_DIR = textmetricsconfig.LEANHT_DIR


def make_lean_ht():
    iterator = ContentIterator(out_dir=OUT_DIR, yield_mode='file')
    for classes in iterator.iterate():
        # Build a map of each class indexed by ID
        classmap = {thesclass.id(): thesclass for thesclass in classes}
        # Set of IDs marking classes which will be dropped
        dropped_classes = set()

        # Drop instances that represent minor senses
        for thesclass in classes:
            if thesclass.instances():
                wordclass = thesclass.wordclass(penn=True)
                stripnodes = []
                for instance in thesclass.instances():
                    minor_sense, minor_homograph = _test_status(instance, wordclass)
                    if minor_sense or minor_homograph:
                        stripnodes.append(instance.node)
                if stripnodes:
                    container = stripnodes[0].getparent()
                    for node in stripnodes:
                        container.remove(node)
                    # Reset the listed size of the class
                    new_size = thesclass.size() - len(stripnodes)
                    if thesclass.size() == thesclass.size(branch=True):
                        thesclass.reset_size(new_size, branch=True)
                    thesclass.reset_size(new_size)
                    if thesclass.size(branch=True) == 0:
                        dropped_classes.add(thesclass.id())

        # Roll up minor leaf nodes to the parent node
        for thesclass in [c for c in classes if not c.id() in dropped_classes]:
            thesclass.reload_instances()
            parentclass = classmap.get(thesclass.parent(), None)
            if _viable_for_rollup(thesclass, parentclass):
                # Move instances from this class to the parent class
                for instance in thesclass.instances():
                    parentclass.node.append(instance.node)
                # Mark this class to be dropped
                dropped_classes.add(thesclass.id())
                print('-----------------------------------------')
                print(thesclass.id(), thesclass.breadcrumb())
                print('->', parentclass.id(), parentclass.breadcrumb())

        # Remove child-node pointers for nodes which are about to be deleted
        for thesclass in [c for c in classes if not c.id() in dropped_classes]:
            for child_id in thesclass.child_nodes():
                if child_id in dropped_classes:
                    thesclass.remove_child(child_id)

        # Remove nodes for classes marked to be dropped
        for classid in dropped_classes:
            thesclass = classmap[classid]
            thesclass.node.getparent().remove(thesclass.node)

        # Redo counts in the remaining classes
        for thesclass in [c for c in classes if not c.id() in dropped_classes]:
            thesclass.reload_instances()
            thesclass.reset_size(len(thesclass.instances()))


def _test_status(instance, wordclass):
    is_minor_sense = MAIN_SENSE_CHECKER.is_minor_sense(
        instance.refentry(),
        instance.refid(),
        instance.lemma(),)
    is_minor_homograph = MAIN_SENSE_CHECKER.is_in_minor_homograph(
        instance.refentry(),
        instance.lemma(),
        wordclass,)
    return is_minor_sense, is_minor_homograph


def _viable_for_rollup(thesclass, parentclass):
    if (thesclass.is_leaf_node() and
            thesclass.size() <= 2 and
            thesclass.level() >= 4 and
            parentclass and
            parentclass.wordclass() and
            not parentclass.is_wordclass_level() and
            _label_viable_for_rollup(thesclass)):
        return True
    elif (thesclass.is_leaf_node() and
            thesclass.level() >= 4 and
            parentclass and
            parentclass.wordclass() and
            re.search(r'^(type|kind)s? of$', thesclass.label())):
        return True
    else:
        return False


def _label_viable_for_rollup(thesclass):
    label = thesclass.label()
    if thesclass.wordclass(penn=True) == 'NN':
        if (label.endswith(' of') and
                not re.search(r'(type|kind)s? of$', label)):
            return False
        elif re.search(r' (in|for|with|who|which)$', label):
            return False
    if label in ('not', 'without'):
        return False
    return True
