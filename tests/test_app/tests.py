from django.test import TestCase
from customfields.inheritedfield import InheritedOnlyException
        
from models import *

class CachedManyToManyTests(TestCase):
    def test_runtime_model(self):
        d = TestModelC()
        self.assertEquals(d.cmtm_a_cache, set())
        self.assertEquals(d.cmtm_b_cache, set())

    def test_cache_field(self):
        c = TestModelC()
        assert hasattr(c, 'cmtm_a_cache')
        assert hasattr(c, 'cmtm_b_cache')

    def test_empty(self):
        c = TestModelC()
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_empty_save_load(self):
        c = TestModelC()
        c.save()
        pk = c.pk
        c = TestModelC.objects.get(pk=pk)
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_simple_sync(self):
        a = TestModelA()
        a.save()
        b = TestModelB()
        b.save()
        c = TestModelC()
        c.save() #muste save before addign mtm relations
        c.cmtm_a.add(a)
        c.cmtm_b.add(b)
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))
        c.save() #save and reload the object
        c = TestModelC.objects.all()[0]
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))

    def test_multiple_sync(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c.cmtm_a.add(*objs)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        self.assertEquals(c.cmtm_a_cache, set())

    def test_save_load_sequence(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c_pk = c.pk
        c.cmtm_a.add(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set())

    def test_set_field(self):
        sf = cachedmtmfield.SetField()

    def test_lookup(self):
        c = TestModelC()
        c.save()
        self.assertRaises(TypeError, lambda: TestModelC.objects.filter(cmtm_a_cache=1))

class InheritedFieldTests(TestCase):
    def test_model_field_inheritance_broken_parent(self):
        b = TestModel2()
        b.save()
        b.foo = 'abc'
        self.assertEquals(b.foo, 'abc')
        self.assertEquals(b.foo_value, 'abc')
        self.assertEquals(b.is_foo_inherited, False)

        # this tests handling for broken FKs
        b = TestModel2()
        b.parent_id = 99999
        b.foo = 'abc'
        self.assertEquals(b.foo, 'abc')
        self.assertEquals(b.foo_value, 'abc')
        self.assertEquals(b.is_foo_inherited, False)

    def test_model_field_inheritance_simple(self):
        a = TestModel1(bar="123")
        a.save()

        b = TestModel2(parent=a)
        b.save()

        self.assertEquals(a.bar, '123')
        self.assertEquals(b.foo, '123')
        self.assertEquals(b.is_foo_inherited, True)

        b.foo = 'abc'
        self.assertEquals(a.bar, '123')
        self.assertEquals(b.foo, 'abc')
        self.assertEquals(b.foo_value, 'abc')
        self.assertEquals(b.is_foo_inherited, False)

        self.assertEquals(b.ifoo, '123')
        a.bar = 'qwe'
        self.assertEquals(b.ifoo, 'qwe')

        try:
            b.ifoo = 'fail'
        except InheritedOnlyException, e:
            self.assertEquals(e.args[0], "Can't set value for field ifoo on TestModel2 object (field is inherit_only). Try to set it on parent.bar.")

        else:
            self.fail("Didn't raise any TypeError")

    def test_model_field_inheritance_silly(self):
        class TestModel3_Valid(models.Model):
            parent = models.ForeignKey(TestModel1)
            foo = inheritedfield.InheritedField('parent', 'bar')
            m2mrel = inheritedfield.InheritedField('parent')


        class TestModel_Temp2(models.Model):
            parent = models.ForeignKey("TestModel_Temp1")
            m2mrel = inheritedfield.InheritedField('parent')
        class TestModel_Temp1(models.Model):
            m2mrel = models.ManyToManyField(Stuff)

    def test_model_field_inheritance_validation(self):
        try:
            class TestModel4_Invalid(models.Model):
                foo = inheritedfield.InheritedField('no_parent', 'bar')
                parent = models.ForeignKey(TestModel1)

        except TypeError, e:
            self.assertEquals(e.args[0], "InheritedField: no_parent does not exist on <class 'test_app.tests.TestModel4_Invalid'>.")
        else:
            self.fail("Didn't raise any TypeError (no_parent test)")

        try:
            class TestModel5_Invalid(models.Model):
                parent = models.ForeignKey(TestModel1)
                foo = inheritedfield.InheritedField('parent', 'no_bar')
        except TypeError, e:
            self.assertEquals(e.args[0], "InheritedField: no_bar does not exist in <class 'test_app.models.TestModel1'>.")
        else:
            self.fail("Didn't raise any TypeError (no_bar (target field) test)")

        try:
            class TestModel6_Invalid(models.Model):
                parent = models.ForeignKey(TestModel2)
                foo = inheritedfield.InheritedField('parent', 'bar')
            class TestModel7_Invalid(models.Model):
                parent = models.ForeignKey(TestModel6_Invalid)
                foo = inheritedfield.InheritedField('parent', 'no_bar')
        except TypeError, e:
            self.assertEquals(e.args[0], "InheritedField: no_bar does not exist in <class 'test_app.tests.TestModel6_Invalid'>.")
        else:
            self.fail("Didn't raise any TypeError (no_bar (target field) test)")

    def test_parent_not_a_rel(self):
        try:
            class TestModel8_Invalid(models.Model):
                parent = models.BooleanField()
                foo = inheritedfield.InheritedField('parent', 'bar')
        except TypeError, e:
            self.assertEquals(e.args[0], "InheritedField: parent is a <class 'django.db.models.fields.BooleanField'> instead of a RelatedField.")
        else:
            self.fail("Didn't raise any TypeError (no_bar (target field) test)")

        class TestModel9_Invalid(models.Model):
            parent = models.BooleanField()
            foo = inheritedfield.InheritedField('parent', 'bar', validate=False)
        #should work :)


    def test_select_related(self):
        self.assertFalse(hasattr(TestModel8, "FIELD_INHERITANCE_REL"))
        qs = TestModel8.objects.filter()
        self.assertTrue(hasattr(TestModel8, "FIELD_INHERITANCE_REL"))
        self.assertEquals(`qs.query.select_related`, "{'parent_for_8': {'parent_for_7': {'parent_for_6': {}}}}")
        self.assertEquals(TestModel8.FIELD_INHERITANCE_REL, set(['parent_for_8__parent_for_7__parent_for_6']))
        qs = TestModel2.objects.filter()
        self.assertEquals(`qs.query.select_related`, "{'parent': {}}")

    def test_model_field_double_inheritance(self):
        a = TestModel1(bar="123")
        a.save()

        b = TestModel6(parent_for_6=a)
        b.save()

        c = TestModel7(parent_for_7=b)
        c.save()

        d = TestModel8(parent_for_8=c)
        d.save()

        self.assertEquals(b.foo, '123')
        self.assertEquals(d.goo, '123')
        self.assertEquals(b.is_foo_inherited, True)
        self.assertEquals(d.is_goo_inherited, True)

        c.boo = 'abc'
        self.assertEquals(c.boo, 'abc')
        self.assertEquals(c.is_boo_inherited, False)
        self.assertEquals(c.get_boo_display(), "abc")
        self.assertEquals(d.goo, 'abc')
        self.assertEquals(d.is_goo_inherited, True)
        self.assertEquals(d.get_goo_display(), "abc *Inherited")


class TestModelA(models.Model): # used to test cached many to many field
    x = models.CharField(max_length=1)

class TestModelB(models.Model): # used to thest cached many to many field
    x = models.CharField(max_length=1)

class TestModelC(models.Model): # used to thest cached many to many field
    cmtm_a = cachedmtmfield.CachedManyToManyField(TestModelA)
    cmtm_b = cachedmtmfield.CachedManyToManyField(TestModelB)

class CachedManyToManyTests(TestCase):
    #def test_that_is_not_a_test(self):
        #reload(cachedmtmfield)

    def test_inherited_field_compat(self):
        class TestModel3_Cached_Valid(models.Model):
            parent = models.ForeignKey(TestModel1_Cached)
            foo = inheritedfield.InheritedField('parent', 'bar')
            m2mrel = inheritedfield.InheritedField('parent')


    def test_runtime_model(self):
        class TestModelD(models.Model): # used to thest cached many to many field
            cmtm_a = cachedmtmfield.CachedManyToManyField(TestModelA)
            cmtm_b = cachedmtmfield.CachedManyToManyField(TestModelB)
        d = TestModelC()
        self.assertEquals(d.cmtm_a_cache, set())
        self.assertEquals(d.cmtm_b_cache, set())

    def test_cache_field(self):
        c = TestModelC()
        assert hasattr(c, 'cmtm_a_cache')
        assert hasattr(c, 'cmtm_b_cache')

    def test_empty(self):
        c = TestModelC()
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_empty_save_load(self):
        c = TestModelC()
        c.save()
        pk = c.pk
        c = TestModelC.objects.get(pk=pk)
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_simple_sync(self):
        a = TestModelA()
        a.save()
        b = TestModelB()
        b.save()
        c = TestModelC()
        c.save() #muste save before addign mtm relations
        c.cmtm_a.add(a)
        c.cmtm_b.add(b)
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))
        c.save() #save and reload the object
        c = TestModelC.objects.all()[0]
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))

    def test_multiple_sync(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c.cmtm_a.add(*objs)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        self.assertEquals(c.cmtm_a_cache, set())

    def test_save_load_sequence(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c_pk = c.pk
        c.cmtm_a.add(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set())

    def test_set_field(self):
        sf = cachedmtmfield.SetField()

    def test_lookup(self):
        c = TestModelC()
        c.save()
        self.assertRaises(TypeError, lambda: TestModelC.objects.filter(cmtm_a_cache=1))


######################################################




class CachedManyToManyTests(TestCase):
    #def test_that_is_not_a_test(self):
        #reload(cachedmtmfield)

    def test_inherited_field_compat(self):
        class TestModel3_Cached_Valid(models.Model):
            parent = models.ForeignKey(TestModel1_Cached)
            foo = inheritedfield.InheritedField('parent', 'bar')
            m2mrel = inheritedfield.InheritedField('parent')


    def test_runtime_model(self):
        class TestModelD(models.Model): # used to thest cached many to many field
            cmtm_a = cachedmtmfield.CachedManyToManyField(TestModelA)
            cmtm_b = cachedmtmfield.CachedManyToManyField(TestModelB)
        d = TestModelC()
        self.assertEquals(d.cmtm_a_cache, set())
        self.assertEquals(d.cmtm_b_cache, set())

    def test_cache_field(self):
        c = TestModelC()
        assert hasattr(c, 'cmtm_a_cache')
        assert hasattr(c, 'cmtm_b_cache')

    def test_empty(self):
        c = TestModelC()
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_empty_save_load(self):
        c = TestModelC()
        c.save()
        pk = c.pk
        c = TestModelC.objects.get(pk=pk)
        self.assertEquals(c.cmtm_a_cache, set())
        self.assertEquals(c.cmtm_b_cache, set())

    def test_simple_sync(self):
        a = TestModelA()
        a.save()
        b = TestModelB()
        b.save()
        c = TestModelC()
        c.save() #muste save before addign mtm relations
        c.cmtm_a.add(a)
        c.cmtm_b.add(b)
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))
        c.save() #save and reload the object
        c = TestModelC.objects.all()[0]
        self.assertEquals(c.cmtm_a_cache, set([a.pk]))
        self.assertEquals(c.cmtm_b_cache, set([b.pk]))

    def test_multiple_sync(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c.cmtm_a.add(*objs)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        self.assertEquals(c.cmtm_a_cache, set())

    def test_save_load_sequence(self):
        objs = [TestModelA() for x in range(5)]
        for o in objs:
            o.save()
        objs_pks = [obj.pk for obj in objs]
        c = TestModelC()
        c.save() #muste save before adding mtm relations
        c_pk = c.pk
        c.cmtm_a.add(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(objs_pks))
        new_obj = TestModelA()
        new_obj.save()
        new_objs_pks = objs_pks + [new_obj.pk]
        c.cmtm_a.add(new_obj)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set(new_objs_pks))
        c.cmtm_a.remove(*objs)
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set([new_obj.pk]))
        c.cmtm_a.clear()
        c.save()
        c = TestModelC.objects.get(pk=c_pk)
        self.assertEquals(c.cmtm_a_cache, set())

    def test_set_field(self):
        sf = cachedmtmfield.SetField()

    def test_lookup(self):
        c = TestModelC()
        c.save()
        self.assertRaises(TypeError, lambda: TestModelC.objects.filter(cmtm_a_cache=1))
        
        