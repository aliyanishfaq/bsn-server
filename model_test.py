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
import numpy as np
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import ifcopenshell.geom

class ModelTest(unittest.TestCase) :
    def setUp(self) :
        self.model = session_create("test")[1]
    def test_story_creation(self) :
        self.assertTrue(create_story("test", self.model, 0.25, "Level 1"), "Story creation failed")
        story = self.model.ifcfile.by_type("IfcBuildingStorey")[0]
        self.assertIsNotNone(story, "Story access failed")
        self.assertEqual("Level 1", story.Name, "Story naming failed")
        self.assertEqual(0.25, story.Elevation, "Story elevation failed")
    def test_beam_creation(self) :
        self.assertTrue(beam_create("test1", self.model, "5,0,0", "8,4,0", "W16X40", 1, "wood"), "Beam creation failed")
        beam = self.model.ifcfile.by_type("IfcBeam")[0]
        self.assertIsNotNone(beam, "Beam access failed")
        self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["wood"][0]), {beam}, "Material assignment failed")
        placement = ifcopenshell.util.placement.get_local_placement(beam.ObjectPlacement)
        self.assertEqual((5.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Beam placed improperly")
        wall_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), beam)
        wall_verts = ifcopenshell.util.shape.get_vertices(wall_shape.geometry)
        actual_verts = np.array(
            [[0., 0., 0.],
            [0., 0., 5.],
            [0., 1., 5.],
            [0., 1., 0.],
            [1., 1., 5.],
            [1., 1., 0.],
            [1., 0., 5.],
            [1., 0., 0.]]
        )
        self.assertTrue(np.array_equal(actual_verts, wall_verts), f"Beam points not properly created: {wall_verts}")
        # Todo: figure out how to test profiles
    def test_column_creation(self) :
        self.assertTrue(column_create("test", self.model, 1, "5,0,0", 5.0, "W16X40", "wood"), "Column creation failed")
        column = self.model.ifcfile.by_type("IfcColumn")[0]
        self.assertIsNotNone(column, "Column access failed")
        self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["wood"][0]), {column}, "Material assignment failed")
        placement = ifcopenshell.util.placement.get_local_placement(column.ObjectPlacement)
        self.assertEqual((5.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Column placed improperly")
        wall_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), column)
        wall_verts = ifcopenshell.util.shape.get_vertices(wall_shape.geometry)
        actual_verts = np.array(
            [[0., 0., 0.],
            [0., 0., 5.],
            [0., 1., 5.],
            [0., 1., 0.],
            [1., 1., 5.],
            [1., 1., 0.],
            [1., 0., 5.],
            [1., 0., 0.]]
        )
        self.assertTrue(np.array_equal(actual_verts, wall_verts), f"Beam points not properly created: {wall_verts}")
        # Todo: figure out how to test profiles
    def test_grid_creation(self) :
        self.assertTrue(grid_create("test", 5.0, 5.0, 5, 5, 10.0, self.model), "Grid creation failed")
        grid = self.model.ifcfile.by_type("IfcGrid")[0]
        self.assertIsNotNone(grid, "Grid access failed")
        self.assertEqual(5, len(grid.UAxes), "Improper number of UAxes created")
        self.assertEqual(5, len(grid.VAxes), "Improper number of VAxes created")
        # Todo: figure out how to measure length on grid axes
    def test_wall_creation(self) :
        self.assertTrue(wall_create("test", 1, "0,0,0", "10,0,0", 10.0, 1.0, "steel", self.model), "Wall creation failed")
        wall = self.model.ifcfile.by_type("IfcWallStandardCase")[0]
        self.assertIsNotNone(wall, "Wall access failed")
        self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["steel"][0]), {wall}, "Material assignment failed")
        placement = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
        self.assertEqual((0.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Wall placed improperly")
        wall_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), wall)
        wall_verts = ifcopenshell.util.shape.get_vertices(wall_shape.geometry)
        actual_verts = np.array(
            [[ 0.,  -0.5,  0. ],
            [ 0.,  -0.5, 10. ],
            [10.,  -0.5, 10. ],
            [10.,  -0.5,  0. ],
            [10.,   0.5, 10. ],
            [10.,   0.5,  0. ],
            [ 0.,   0.5, 10. ],
            [ 0.,   0.5,  0. ]]
        )
        self.assertTrue(np.array_equal(actual_verts, wall_verts), f"Wall points not properly created: {wall_verts}")
    def test_floor_creation(self) :
        self.assertTrue(floor_create("test", 1, [(0., 0., 0.), (0., 100., 0.), (100., 100., 0.), (100., 0., 0.)], 1.0, self.model), "Floor creation failed")
        floor = self.model.ifcfile.by_type("IfcSlab")[0]
        self.assertIsNotNone(floor, "Floor access failed")
        # self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["steel"][0]), {floor}, "Material assignment failed")
        # When materials can be added to floors enable this line (in one of my other branches)
        placement = ifcopenshell.util.placement.get_local_placement(floor.ObjectPlacement)
        self.assertEqual((0.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Floor placed improperly")
        floor_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), floor)
        floor_verts = ifcopenshell.util.shape.get_vertices(floor_shape.geometry)
        actual_verts = np.array(
            [[0., 0., 0.],
            [ 0.,  0,  1. ],
            [ 0.,  100., 1. ],
            [0.,  100., 0. ],
            [100.,  100.,  1. ],
            [100.,   100, 0. ],
            [100.,   0.,  1. ],
            [ 100.,   0., 0. ]]
        )
        self.assertTrue(np.array_equal(actual_verts, floor_verts), f"Floor points not properly created: {floor_verts}")
    def test_roof_creation(self) :
        self.assertTrue(roof_create("test", 1, [(0., 0., 0.), (0., 100., 0.), (100., 100., 0.), (100., 0., 0.)], 1.0, self.model), "Floor creation failed")
        roof = self.model.ifcfile.by_type("IfcRoof")[0]
        self.assertIsNotNone(roof, "Roof access failed")
        # self.assertEqual(ifcopenshell.util.element.get_elements_by_material(self.model.ifcfile, self.model.materials["steel"][0]), {roof}, "Material assignment failed")
        # When materials can be added to roofs enable this line (in one of my other branches)
        placement = ifcopenshell.util.placement.get_local_placement(roof.ObjectPlacement)
        self.assertEqual((0.0, 0.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Roof placed improperly")
        roof_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), roof)
        roof_verts = ifcopenshell.util.shape.get_vertices(roof_shape.geometry)
        actual_verts = np.array(
            [[0., 0., 0.],
            [ 0.,  0,  1. ],
            [ 0.,  100., 1. ],
            [0.,  100., 0. ],
            [100.,  100.,  1. ],
            [100.,   100, 0. ],
            [100.,   0.,  1. ],
            [ 100.,   0., 0. ]]
        )
        self.assertTrue(np.array_equal(actual_verts, roof_verts), f"Roof points not properly created: {roof_verts}")
    def test_isolated_footing_creation(self) :
        self.assertTrue(isolated_footing_create("test", self.model, 1, (12.0, 4.0, 0.0), 5.0, 4.0, 1.0), "Isolated footing creation failed")
        footing = self.model.ifcfile.by_type("IfcFooting")[0]
        self.assertIsNotNone(footing, "Footing access failed")
        placement = ifcopenshell.util.placement.get_local_placement(footing.ObjectPlacement)
        self.assertEqual((12.0, 4.0, 0.0), (placement[0][3], placement[1][3], placement[2][3]), "Footing placd improperly")
        footing_shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), footing)
        footing_verts = ifcopenshell.util.shape.get_vertices(footing_shape.geometry)
        actual_verts = np.array()
        self.assertTrue(np.array_equal(actual_verts, footing_verts), f"Footing points not properly created: {footing_verts}")
if __name__ == '__main__' :
    unittest.main()