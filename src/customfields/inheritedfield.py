import logging
logger = logging.getLogger(__name__)

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, Field, BooleanField, Manager, ManyToManyField, Q
from django.db.models.query import QuerySet
from django.db.models.fields.related import RelatedField, add_lazy_relation, \
                        ReverseManyRelatedObjectsDescriptor, ManyToManyField
from django.db.models.base import ModelBase
from django.db.models import signals
from django.db.models.sql.constants import QUERY_TERMS
try:
    from django.db.models.sql.constants import LOOKUP_SEP
except ImportError:
    from django.db.models.constants import LOOKUP_SEP
from django.utils.functional import curry

import copy
from collections import defaultdict

INHERIT_FLAG_NAME = "is_%s_inherited"
VALUE_FIELD_NAME = "%s_value"

__all__ = (
    'INHERIT_FLAG_NAME', 'VALUE_FIELD_NAME', 'InheritedOnlyException',
    'InheritedField', 'find_in_parent', 'find_on_model'
)

class InheritedOnlyException(Exception):
    pass

class InheritedField(Field):
    """
    This field will:

        - check if the model refered by ``parent_name`` contains ``field_name``
          and raise according exceptions if `validate=True` (default).
        - copy the field from the parent, or the parent's parent if the field in
          the parent has is an InheritedField too if `inherit_only=False`
          (default)
        - create a boolean flag ``is_<fieldname>_inherited`` in the current
          model.

    This field implements a descriptor interface so it will work like a property
    with getters and setters.

        - get will return the value from the parent if
          `is_{fieldname}_inherited` is `True`
        - set will raise `InheritedOnlyException` if the field is `inherit_only`
        - set will save the value in `{fieldname}_value` and set the
          `is_{fieldname}_inherited` flag accordingly
    """
    def __init__(self, parent_name, field_name=None, inherit_only=False, validate=True):
        super(InheritedField, self).__init__()

        self.parent_object_field_name = parent_name
        self.inherited_field_name_in_parent = field_name
        self.inherit_only = inherit_only
        self.validate = validate

    def get_field_display(self, instance, name):
        if self.inherit_only or getattr(instance, self.inherit_flag_name):
            rel = getattr(instance, self.parent_object_field_name)
            pname = self.inherited_field_name_in_parent or name
            displayfname = "get_%s_display" % pname
            return u"%s *Inherited" % (
                getattr(rel, displayfname)()
                if hasattr(rel, displayfname)
                else getattr(rel, pname)
            )
        else:
            return getattr(instance, VALUE_FIELD_NAME % name)

    def contribute_to_class(self, cls, name):
        self.name = self.attname = name
        cls._meta.add_virtual_field(self)

        self.inherit_flag_name = INHERIT_FLAG_NAME % name
        self.value_field_name = VALUE_FIELD_NAME % name

        if not self.inherit_only:
            flag_field = BooleanField(default=True)
            flag_field.creation_counter = self.creation_counter

            # Adjust the creation_counter
            # cls.add_to_class(self.inherit_flag_name, flag_field)
            flag_field.contribute_to_class(cls, self.inherit_flag_name)

            signals.class_prepared.connect(
                curry(self.add_value_field, name=name),
                sender=cls,
                weak=False
            )

        setattr(cls, name, self)
        display_name = 'get_%s_display' % name
        setattr(cls, display_name, curry(self.get_field_display, name=name))
        getattr(cls, display_name).__dict__['short_description'] = name.replace('_', ' ')

        if not hasattr(cls, 'FIELD_INHERITANCE_MAP'): #TODO: test
            cls.FIELD_INHERITANCE_MAP = {}

        cls.FIELD_INHERITANCE_MAP[name] = (self.parent_object_field_name, self.inherited_field_name_in_parent or name)
        signals.class_prepared.connect(self.patch_manager, sender=cls)

    def patch_manager(self, sender, **kwargs):
        if not hasattr(sender.objects, 'original_get_query_set'):
            _get_query_set = sender.objects.get_query_set
            def get_query_set(qs):
                model = qs.model

                if hasattr(model, 'FIELD_INHERITANCE_REL'):
                    related = model.FIELD_INHERITANCE_REL
                else:
                    related = set()
                    for field, (parent, target_field) in model.FIELD_INHERITANCE_MAP.iteritems():
                        chain = []
                        find_in_parent(model, parent, target_field, validate=False, chain=chain)
                        related.add('__'.join(chain))
                    model.FIELD_INHERITANCE_REL = related

                return _get_query_set().select_related(*related)

            sender.objects.original_get_query_set = _get_query_set
            sender.objects.get_query_set = get_query_set.__get__(sender.objects)
            logger.debug("Patching %s's get_query_set method to slap a select_related on the returned qs.", sender.__name__)

    def add_value_field(self, sender, name=None, robust=True, **kwargs):
        def contribute(field):
            if hasattr(field, '_choices') and field._choices:
                self._choices = field._choices

            if isinstance(field, ReverseManyRelatedObjectsDescriptor):
                field = field.field

            xfield = copy.deepcopy(field)
            xfield.blank = True
            if isinstance(xfield, ManyToManyField):
                xfield.rel.through = None

            xfield.creation_counter = self.creation_counter
            xfield.contribute_to_class(sender, VALUE_FIELD_NAME % name)

        value_field = find_in_parent(
            sender,
            self.parent_object_field_name,
            self.inherited_field_name_in_parent or name,
            robust and self.validate,
            callback = contribute
        )
    def __get__(self, instance, instance_type=None):
        if self.inherit_only or getattr(instance, self.inherit_flag_name):
            rel = getattr(instance, self.parent_object_field_name)
            if rel:
                return getattr(rel, self.inherited_field_name_in_parent or self.name)
        return getattr(instance, self.value_field_name, None)

    def __set__(self, instance, value):
        if self.inherit_only:
            raise InheritedOnlyException(
                "Can't set value for field %s on %s (field is inherit_only). Try to set it on %s.%s." %
                (self.name, instance, self.parent_object_field_name, self.inherited_field_name_in_parent or self.name))
        try:
            rel = getattr(instance, self.parent_object_field_name)
            if rel:
                parent_value = getattr(rel, self.inherited_field_name_in_parent or self.name)
                setattr(instance, self.inherit_flag_name, value == parent_value)
            else:
                setattr(instance, self.inherit_flag_name, False)
        except ObjectDoesNotExist:
            setattr(instance, self.inherit_flag_name, False)
        setattr(instance, self.value_field_name, value)

def find_on_model(model, field_name, validate=True, callback=None, chain=None):
    target_fields = [
        target for target in model._meta.fields
            if target.name == field_name
    ]

    if target_fields:
        return target_fields[0]

    if hasattr(model, field_name):
        return getattr(model, field_name)

    if hasattr(model, 'FIELD_INHERITANCE_MAP'):
        MAP = getattr(model, 'FIELD_INHERITANCE_MAP')
        if field_name in MAP:
            rel, field = MAP[field_name]
            return find_in_parent(model, rel, field, validate, callback, chain)
        elif validate:
            raise TypeError("InheritedField: %s does not exist in %s." %
                                (field_name, model))


    if validate:
        raise TypeError("InheritedField: %s does not exist in %s." %
                                    (field_name, model))

def find_in_parent(model_class, relation_name, field_name, validate=True, callback=None, chain=None):
    """
    This function will take a model class and search for the relation so that:

        - if `validate` is `True` will raise `TypeError`'s if the field isn't
          found in the parent.
        - will call `callback` if there is something found

    Note that this will not always return the field instance as the field may be
    on a uninstantiated model class. Use `callback` to do stuff with the field.
    """
    for ifield in model_class._meta.fields:
        if ifield.name == relation_name:
            if not chain is None:
                chain.append(relation_name)
            if isinstance(ifield, RelatedField):
                if isinstance(ifield.rel.to, basestring):
                    # the model class isn't instantiated yet so we need to add a
                    # hook
                    def resolve_related_class(xfield, xmodel, xcls):
                        xfield.rel.to = xmodel
                        field_instance = find_on_model(xmodel, field_name, validate, callback, chain)
                        if field_instance:
                            callback(field_instance)

                    add_lazy_relation(model_class, ifield, ifield.rel.to,
                                        resolve_related_class)
                    return
                else:
                    return find_on_model(ifield.rel.to, field_name, validate, callback, chain)
            else:
                if validate:
                    raise TypeError(
                        "InheritedField: %s is a %s instead of a RelatedField."%
                        (relation_name, type(ifield)))
                else:
                    return
    if validate:
        raise TypeError("InheritedField: %s does not exist on %s." %
                        (relation_name, model_class))

class InheritedFieldQuerySet(QuerySet):
    def is_inherited(self, parts):
        _parts = parts[:]
        last_field_name, model = self.traverse_models(_parts, self.model)
        return hasattr(model, 'FIELD_INHERITANCE_MAP') and \
               last_field_name in model.FIELD_INHERITANCE_MAP

    def traverse_models(self, parts, model):
        next_part = parts.pop(0)
        if(parts):
            next_model = self.model._meta.get_field(next_part).rel.to
            return self.traverse_models(parts, next_model)
        return (next_part, model)

    def split_field(self, field):
        parts = field.split(LOOKUP_SEP)
        lookup = None
        if parts[-1] in QUERY_TERMS:
            lookup = parts.pop(-1)
        return (parts,lookup)

    def patch_child(self, parts, lookup, value):
        inherited_flag = ["is_%s_inherited" % parts[-1]]
        inherited_value = ["%s_value" % parts[-1]]
        lookup = [lookup] if lookup else []
        is_inherited = LOOKUP_SEP.join(parts[:-1] + inherited_flag)
        field = LOOKUP_SEP.join(parts[:-1] + inherited_value + lookup)
        print is_inherited
        print field
        return Q(**{is_inherited: False, field: value})

    def patch_parent(self, parts, lookup, value):
        _parts = parts[:]
        last_field_name, model = self.traverse_models(_parts, self.model)
        lookup = [lookup] if lookup else []
        parents_name, parents_field_name = model.FIELD_INHERITANCE_MAP[last_field_name]
        parent_lookup = LOOKUP_SEP.join(parts[:-1] + [parents_name] + [parents_field_name] + lookup)
        print parent_lookup
        return Q(**{parent_lookup: value})

    def patch(self, parts, lookup, value):
        child = self.patch_child(parts, lookup, value)
        parent = self.patch_parent(parts, lookup, value)
        return child | parent

    def filter(self, *args, **kwargs):
        # We don't support Q objects, bail out if any
        assert not args
        args = []
        old_kwargs = kwargs.copy()
        for field, value in kwargs.items():
            parts, lookup = self.split_field(field)
            if self.is_inherited(parts):
                old_kwargs.pop(field)
                args.append(self.patch(parts, lookup, value))
        return super(InheritedFieldQuerySet, self).filter(*args, **old_kwargs)

class InheritedFieldManager(Manager):
    def get_query_set(self):
        return InheritedFieldQuerySet(self.model, using=self._db)