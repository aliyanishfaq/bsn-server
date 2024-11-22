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
        self.tests["IfcOpeningElement"] = self.product_equals
        self.tests["IfcGrid"] = self.product_equals
        self.tests["IfcMaterial"] = self.material_equals
    def entity_equals(self, first: ifcopenshell.entity_instance, second: ifcopenshell.entity_instance) :
        first_type = ifcopenshell.util.element.get_type(first)
        second_type = ifcopenshell.util.element.get_type(second)
        if first_type.Name == second_type.Name :
            return self.tests[first_type.Name](first, second)
        return False
    def product_equals(self, first: ifcopenshell.entity_instance, second: ifcopenshell.entity_instance) :
        first_place = ifcopenshell.util.placement.get_local_placement(first.ObjectPlacement)
        second_place = ifcopenshell.util.placement.get_local_placement(second.ObjectPlacement)
        settings = ifcopenshell.geom.settings()
        first_shape = ifcopenshell.geom.create_shape(settings, first)
        first_material = ifcopenshell.util.element.get_material(first)
        first_verts = ifcopenshell.util.shape.get_vertices(first_shape.geometry)
        first_edges = ifcopenshell.util.shape.get_edges(first_shape.geometry)
        first_faces = ifcopenshell.util.shape.get_faces(first_shape.geometry)
        second_shape = ifcopenshell.geom.create_shape(settings, second)
        second_material = ifcopenshell.util.element.get_material(second)
        second_verts = ifcopenshell.util.shape.get_vertices(second_shape.geometry)
        second_edges = ifcopenshell.util.shape.get_edges(second_shape.geometry)
        second_faces = ifcopenshell.util.shape.get_faces(second_shape.geometry)
        return np.array_equal(first_place, second_place) and np.array_equal(first_verts, second_verts) and np.array_equal(first_edges, second_edges) and np.array_equal(first_faces, second_faces) and self.material_equals(first_material, second_material)
    def material_equals(self, first: ifcopenshell.entity_instance, second: ifcopenshell.entity_instance) :
        if first is not None and second is not None :
            return first.Name == second.Name
    def file_equals(self, first_path: str, second_path: str) :
        try: 
            first = ifcopenshell.open(first_path)
            second = ifcopenshell.open(second_path)
        except Exception as e:
            print("Check that the paths to the files are correct")
            return
        elements = 0
        successes = 0
        incompletes = 0
        for key in iter(self.tests.keys()) :
            first_set = first.by_type(key)
            second_set = second.by_type(key)
            for first_element in first_set :
                elements += 1
                for second_element in second_set :
                    if self.tests[key](first_element, second_element) :
                        successes += 1
                        second_set.remove(second_element)
                        first_set.remove(first_element)
                        break
            if len(first_set) > 0 :
                incompletes += len(first_set)
            if len(second_set) > 0 :
                elements += len(second_set)
                incompletes += len(second_set)
        percentage = successes / (elements - incompletes)
        print(f"Score for the files ({first} and {second}): {percentage}\n Total number of elements: {elements}\n Number of elements that could not be successfully compared: {incompletes}")
