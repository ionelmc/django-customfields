"""
This module contains the :class:`CachedManyToManyField` will add a primitive ID
cache in the model that can be accessed via fieldname.cache (preferably) or
fieldname_cache. The cache is a :class:`SetField`.
"""

from django.db.models.fields.related import ReverseManyRelatedObjectsDescriptor
from django.db import models
import pickle
import compiler

CACHE_FIELD_POSTFIX = '_cache'

def unrepr(s):
    s = "a=" + s
    p = compiler.parse(s)
    return p.getChildren()[1].getChildren()[0].getChildren()[1].value

class SetField(models.TextField):
    """ Implements a set stored as pickled object."""

    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['editable'] = False #don't allow editing from admin
        #TODO: remove this: kwargs['max_length'] = 255 #this should be enough for now
        super(SetField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, basestring) and value:
            try:
                return pickle.loads(str(unrepr(value)))
            except TypeError:
                return set()
        if isinstance(value, set):
            return value
        return set()

    def get_db_prep_value(self, value, connection=None, prepared=False):
        if prepared:
            return value
        if not value:
            value = set()
        r = pickle.dumps(value)
        return repr(r)

    def get_prep_lookup(self, lookup_type, value):
        raise TypeError("Lookup type %s not supported." % lookup_type)

    def get_db_prep_lookup(self, lookup_type, value, connection=None, prepared=False):
        raise TypeError("Lookup type %s not supported." % lookup_type)

def _default_cached_value_getter(o):
    return int(o) if isinstance(o, (int, str, unicode)) else o.pk

def get_caching_related_manager(superclass, instance, field_name, related_name, cache_field_name, cached_value_getter):
    "Creates a new manager class that has some extra (synchronizing the cache field) handling."
    cached_value_getter = cached_value_getter or _default_cached_value_getter

    class CachingRelatedManager(superclass):
        def add(self, *objs):
            super(CachingRelatedManager, self).add(*objs)
            cached_field = getattr(instance, cache_field_name)
            cached_field.update(cached_value_getter(o) for o in objs)

        def remove(self, *objs):
            super(CachingRelatedManager, self).remove(*objs)
            cached_field = getattr(instance, cache_field_name)
            cached_field.symmetric_difference_update(cached_value_getter(o) for o in objs)

        def clear(self):
            super(CachingRelatedManager, self).clear()
            cached_field = getattr(instance, cache_field_name)
            cached_field.clear()

        @property
        def cache(self):
            return getattr(instance, cache_field_name)

    return CachingRelatedManager


class CachedReverseManyRelatedObjectsDescriptor(ReverseManyRelatedObjectsDescriptor):
    def __init__(self, field, cache_field_name, cached_value_getter):
        super(CachedReverseManyRelatedObjectsDescriptor, self).__init__(field)
        self.cache_field_name = cache_field_name
        self.cached_value_getter = cached_value_getter

    def __get__(self, instance, cls=None):
        manager = super(CachedReverseManyRelatedObjectsDescriptor, self).__get__(instance, cls)

        CachingRelatedManager = get_caching_related_manager(manager.__class__,
                                                            instance,
                                                            self.field.name,
                                                            self.field.rel.related_name,
                                                            self.cache_field_name,
                                                            self.cached_value_getter)

        manager.__class__ = CachingRelatedManager
        return manager

class CachedManyToManyField(models.ManyToManyField):
    """
    This field will add a primitive ID cache in the model that can be accessed
    via fieldname.cache (preferably) or fieldname_cache. The cache is a
    :class:`SetField`.
    """
    def __init__(self, to, cached_value_getter=None, **kwargs):
        super(CachedManyToManyField, self).__init__(to, **kwargs)
        self.cached_value_getter = cached_value_getter

    def contribute_to_class(self, cls, name):
        super(CachedManyToManyField, self).contribute_to_class(cls, name)
        cache_field_name = name + CACHE_FIELD_POSTFIX
        if not cls._meta.abstract:
            set_field = SetField()
            set_field.contribute_to_class(cls, cache_field_name)
            setattr(cls, name, CachedReverseManyRelatedObjectsDescriptor(self, cache_field_name, self.cached_value_getter))
