import ifcopenshell.util.element
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.placement
import numpy as np
class IfcEquality :
    def __init__(self) :
        self.tests = dict()
        self.tests["IfcWallStandardCase"] = self.product_equals
        self.tests["IfcSlab"] = self.product_equals
        self.tests["IfcFooting"] = self.product_equals
        self.tests["IfcWall"] = self.product_equals
        self.tests["IfcRoof"] = self.product_equals
        self.tests["IfcBeam"] = self.product_equals
        self.tests["IfcColumn"] = self.product_equals
    def entity_equals(self, first: ifcopenshell.entity_instance, second: ifcopenshell.entity_instance) :
        if ifcopenshell.util.element.get_type(first).Name == ifcopenshell.util.element.get_type(second).Name :
            return self.tests[ifcopenshell.util.element.get_type(first).Name](first, second)
        return False
    def product_equals(self, first: ifcopenshell.entity_instance, second: ifcopenshell.entity_instance) :
        first_place = ifcopenshell.util.placement.get_local_placement(first.ObjectPlacement)
        second_place = ifcopenshell.util.placement.get_local_placement(second.ObjectPlacement)
        settings = ifcopenshell.geom.settings()
        first_shape = ifcopenshell.geom.create_shape(settings, first)
        first_verts = ifcopenshell.util.shape.get_vertices(first_shape.geometry)
        first_edges = ifcopenshell.util.shape.get_edges(first_shape.geometry)
        first_faces = ifcopenshell.util.shape.get_faces(first_shape.geometry)
        second_shape = ifcopenshell.geom.create_shape(settings, second)
        second_verts = ifcopenshell.util.shape.get_vertices(second_shape.geometry)
        second_edges = ifcopenshell.util.shape.get_edges(second_shape.geometry)
        second_faces = ifcopenshell.util.shape.get_faces(second_shape.geometry)
        return np.array_equal(first_place, second_place) and np.array_equal(first_verts, second_verts) and np.array_equal(first_edges, second_edges) and np.array_equal(first_faces, second_faces)
