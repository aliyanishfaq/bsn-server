"""
Plan for this file: write test cases covering the combined functions of tools_graph.py and ifc.py 
hereafter referred to as the model.
TODO:
Refactor tools_graph.py to split out versions of the tools that a. accept an IFC_MODEL as a parameter and b. (done)
return the GlobalId of whatever object is created as prerequisites for testing. (actually unnecessary)
"""
from ifc import IfcModel
from tools_graph import session_create, wall_create, floor_create, roof_create, strip_footing_create, isolated_footing_create, beam_create, column_create, grid_create, create_story
import unittest
import ifcopenshell.util.element
import ifcopenshell.util.placement

class ModelTest(unittest.TestCase) :
    def setUp(self) :
        self.model = session_create("test")[1]
    def test_story_creation(self) :
        self.assertTrue(create_story("test", self.model, 0.25, "Level 1"), "Story creation failed")
        story = self.ifcfile.by_type("IfcBuildingStorey")[0]
        self.assertIsNotNone(story, "Story access failed")
        self.assertEqual("Level 1", story.Name, "Story naming failed")
        self.assertEqual(0.25, story.Elevation, "Story elevation failed")
    def test_beam_creation(self) :
        self.assertTrue(beam_create("test", self.model, "5,0,0", "8,4,0", "W16X40", "steel"), "Beam creation failed")
        beam = self.ifcfile.by_type("IfcBeam")[0]
        self.assertIsNotNone(beam, "Beam access failed")
        self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["steel"][0])[0], beam, "Material assignment failed")
        placement = ifcopenshell.util.placement.get_local_placement(beam.ObjectPlacement)
        self.assertEqual((5.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Beam placement not exacty")
        self.assertEqual(5.0, beam.Representation.Representations[0].Depth, "Beam length failed")
        # Todo: figure out how to test profiles
if __name__ == '__main__' :
    unittest.main()