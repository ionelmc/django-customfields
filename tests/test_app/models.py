from customfields import cachedmtmfield, inheritedfield
from django.db import models

class Stuff(models.Model):
    pass

class TestModel1(models.Model):
    bar = models.CharField(max_length=10)
    m2mrel = models.ManyToManyField(Stuff)

class TestModel1_Cached(models.Model):
    bar = models.CharField(max_length=10)
    m2mrel = cachedmtmfield.CachedManyToManyField(Stuff)

class TestModelA(models.Model): # used to test cached many to many field
    x = models.CharField(max_length=1)

class TestModelB(models.Model): # used to thest cached many to many field
    x = models.CharField(max_length=1)

class TestModelC(models.Model): # used to thest cached many to many field
    cmtm_a = cachedmtmfield.CachedManyToManyField(TestModelA)
    cmtm_b = cachedmtmfield.CachedManyToManyField(TestModelB)
    
class Stuff(models.Model):
    pass

class TestModel1(models.Model):
    bar = models.CharField(max_length=10)
    m2mrel = models.ManyToManyField(Stuff)

class TestModel1_Cached(models.Model):
    bar = models.CharField(max_length=10)
    m2mrel = cachedmtmfield.CachedManyToManyField(Stuff)

class TestModel2(models.Model):
    parent = models.ForeignKey(TestModel1, null=True)

    bar = models.CharField(max_length=10)
    foo = inheritedfield.InheritedField('parent', 'bar', validate=False)
    ifoo = inheritedfield.InheritedField('parent', 'bar', inherit_only=True)

class TestModel6(models.Model): #used in test_model_field_double_inheritance
    parent_for_6 = models.ForeignKey(TestModel1)
    foo = inheritedfield.InheritedField('parent_for_6', 'bar')
class TestModel7(models.Model): #used in test_model_field_double_inheritance
    parent_for_7 = models.ForeignKey(TestModel6)
    bogus_relation = models.ForeignKey(TestModel6, related_name="bogus", null=True)
    boo = inheritedfield.InheritedField('parent_for_7', 'foo')
class TestModel8(models.Model): #used in test_model_field_double_inheritance
    parent_for_8 = models.ForeignKey(TestModel7)
    goo = inheritedfield.InheritedField('parent_for_8', 'boo')

class TestModelA(models.Model): # used to test cached many to many field
    x = models.CharField(max_length=1)

class TestModelB(models.Model): # used to thest cached many to many field
    x = models.CharField(max_length=1)

class TestModelC(models.Model): # used to thest cached many to many field
    cmtm_a = cachedmtmfield.CachedManyToManyField(TestModelA)
    cmtm_b = cachedmtmfield.CachedManyToManyField(TestModelB)