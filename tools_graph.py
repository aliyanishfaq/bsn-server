from ifc import IfcModel
from langchain_core.tools import tool, InjectedToolArg
from typing_extensions import Annotated
import ifcopenshell
import ifcopenshell.api
from ifcopenshell.api import run
import asyncio
from socket_server import sio
from collections import OrderedDict
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import numpy as np
from feature_extractor import IfcEntityFeatureExtractor
from tool_helpers import format_output_search_canvas
from groq import Groq
from global_store import global_store

load_dotenv()

global levels_dict
levels_dict = {}

global openai_client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
global groq_client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))


## ---- TOOLS FOR MODEL TO CALL ----- #

# global IFC_MODEL
# IFC_MODEL = None
O = 0., 0., 0.
X = 1., 0., 0.
Y = 0., 1., 0.
Z = 0., 0., 1.


@tool
async def create_on_start():
    """
    Creates a new IFC model for the user.
    WARNING: This function no longer works as expected because of SIDs.
    """
    # 1. Tries to make the IFC model.
    try:
        print('Creating a new IFC model')
        # 2. Writes info in the IFC model.
        ifc_model = IfcModel(
            creator="Aliyan",
            organization="BuildSync",
            application="IfcOpenShell",
            application_version="0.5",
            project_name="Modular IFC Project",
            filename=None
        )
        ifc_model.save_ifc("public/canvas.ifc")
        return True
        # 2. Errors out if necessary.
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_session(sid: Annotated[str, InjectedToolArg]) -> bool:
    """
    Creates a new IFC model for the user.
    """
    # 1. Tries to make the session.
    try:
        # 2. Writes info in the IFC model.
        print('Creating a new IFC model for session', sid)
        ifc_model = IfcModel(
            creator="Aliyan",
            organization="BuildSync",
            application="IfcOpenShell",
            application_version="0.5",
            project_name="Modular IFC Project",
            filename=None
        )
        global_store.sid_to_ifc_model[sid] = ifc_model
        ifc_model.save_ifc(f"public/{sid}/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_building_story(sid: Annotated[str, InjectedToolArg], elevation: float = 0.0, name: str = "Level 1") -> bool:
    """
    Creates building stories with the specified amount, elevation, and height.

    Parameters:
    - elevation (float): The elevation of the building stories in feet. If there are already stories been created, then this is the elevation of the tallest building story
    - name (string): The name of the elevation. Name of each story should be unique.
    """
    global retrieval_tool
    global levels_dict
    IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
    if IFC_MODEL is None:
        print("No IFC model found for the given session.")
        create_session(sid)
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
    try:
        # 1. Create the building story
        IFC_MODEL.create_building_stories(elevation, name)
        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")

        # 2. Update the global dictionary
        levels_dict[name] = elevation

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_beam(sid: Annotated[str, InjectedToolArg], start_coord: str = "0,0,0", end_coord: str = "1,0,0", section_name: str = 'W16X40', story_n: int = 1, material: str = None,) -> None:
    """
    Creates a beam at the specified start coordinate with the given dimensions.

    Parameters:
    - start_coord (str): The (x, y, z) coordinates of the beam's start point in the format "x,y,z".
    - end_coord (str): The (x, y, z) coordinates of the beam's end point in the format "x,y,z".
    - section_name (str): The beam profile name (e.g. W16X40).
    - story_n (int): The story number that the user wants to place the beam on
    - material (string): What the beam is made out of.
    """
    if material:
        material = material.lower()
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        # 1. Format coord and direction
        start_coord = tuple(map(float, start_coord.split(',')))
        end_coord = tuple(map(float, end_coord.split(',')))

        direction = IFC_MODEL.calc_direction(start_coord, end_coord)
        length = IFC_MODEL.calc_length(start_coord, end_coord)

        # 2. Setup the IFC model.
        context = IFC_MODEL.ifcfile.by_type(
            "IfcGeometricRepresentationContext")[0]
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
        if len(IFC_MODEL.building_story_list) < story_n:
            IFC_MODEL.create_building_stories(
                elevation=0, name="Level 1")
        story = IFC_MODEL.building_story_list[story_n - 1]

        # 3. Initiate beam creation.
        # Note: eventually, we'll want to pass in various beam names.
        bm = IFC_MODEL.ifcfile.createIfcBeam(
            IFC_MODEL.create_guid(), owner_history, "Beam")

        # 4. Define beam placement
        Z = (0.0, 0.0, 1.0)

        # 4-1. Define beam starting point, hosting axis, & direction.
        bm_axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
            IFC_MODEL.ifcfile.createIfcCartesianPoint(start_coord))
        bm_axis2placement.Axis = IFC_MODEL.ifcfile.createIfcDirection(
            direction)

        crossprod = IFC_MODEL.calc_cross(direction, Z)
        bm_axis2placement.RefDirection = IFC_MODEL.ifcfile.createIfcDirection(
            crossprod)

        # 4-2. Create LocalPlacement for beam.
        bm_placement = IFC_MODEL.ifcfile.createIfcLocalPlacement(
            story, bm_axis2placement)  # can pass building stories as host
        bm.ObjectPlacement = bm_placement

        # 4-3. Create 3D axis placement for extrusion.
        bm_extrudePlacement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
            IFC_MODEL.ifcfile.createIfcCartesianPoint((0., 0., 0.)))

        # 4-4. Create extruded area section for beam.
        bm_extrusion = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid()
        ifcclosedprofile = IFC_MODEL.get_wshape_profile(section_name)

        ifcclosedprofile.ProfileName = section_name
        bm_extrusion.SweptArea = ifcclosedprofile
        bm_extrusion.Position = bm_extrudePlacement
        bm_extrusion.ExtrudedDirection = IFC_MODEL.ifcfile.createIfcDirection(
            (0.0, 0.0, 1.0))
        bm_extrusion.Depth = length
        print(f"bm_extrusion: {bm_extrusion}")

        # 5. Create shape representation for beam.
        bm_rep = IFC_MODEL.ifcfile.createIfcShapeRepresentation(
            context, "Body", "SweptSolid", [bm_extrusion])

        IFC_MODEL.add_style_to_product(material, bm)

        # 6. Create a product shape for beam.
        bm_prod = IFC_MODEL.ifcfile.createIfcProductDefinitionShape()
        bm_prod.Representations = [bm_rep]

        bm.Representation = bm_prod

        # 7. Add beam to IFC file & save
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building story Container", None, [bm], story)

        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_column(sid: Annotated[str, InjectedToolArg], story_n: int = 1, start_coord: str = "0,0,0", height: float = 30, section_name: str = "W12X53", material: str = None) -> bool:
    """
    Creates a single column in the Revit document based on specified location, width, depth, and height.

    Parameters:
    - story_n (int): The story number that the user wants to place the column on
    - start_coord (str): The (x, y, z) coordinates of the column's location in the format "x,y,z".
    - height (float): The height of the column in feet.
    - material (string): what the column is made out of.
    - section_name (string): The name of the column type.
    """
    # global retrieval_tool
    if material:
        material = material.lower()
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        # 1. Get the appropriate story and its elevation.
        if len(IFC_MODEL.building_story_list) < story_n:
            IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")
        story = IFC_MODEL.building_story_list[story_n - 1]
        elevation = (story.Elevation)

        # 2. Populate the coordinates.
        start_coord = list(map(float, start_coord.split(',')))
        start_coord[2] = elevation
        start_coord = tuple(start_coord)

        # 3. Set up the IFC model.
        context = IFC_MODEL.ifcfile.by_type(
            "IfcGeometricRepresentationContext")[0]
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # 4. Get the story's placement.
        story_placement = story.ObjectPlacement

        # 5. Create the column placement.
        column_placement = IFC_MODEL.create_ifclocalplacement(
            start_coord, Z, X, relative_to=story_placement)

        # 6. Create the column.
        column = IFC_MODEL.create_column(
            context=context, owner_history=owner_history, column_placement=column_placement, height=height, section_name=section_name, material=material)
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building story Container", None, [column], story)

        # 7. Save structure
        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_grid(sid: Annotated[str, InjectedToolArg], grids_x_distance_between: float = 10.0, grids_y_distance_between: float = 10.0, grids_x_direction_amount: int = 5, grids_y_direction_amount: int = 5, grid_extends: float = 50.0) -> bool:
    """
    Creates a grid of lines in the given document based on the specified number of rows and columns,
    and the spacing between them.

    Parameters:
    - grids_x_distance_between (float): The distance between the x grids.
    - grids_y_distance_between (float): The distance between the y grids.
    - grids_x_direction_amount (int): The number of grids in the x direction.
    - grids_y_direction_amount (int): The number of grids in the y direction.
    - grid_extends (float): The distance on how much the grid extends.
    """
    try:
        # global retrieval_tool
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        grids_x_dictionary = OrderedDict()
        grids_y_dictionary = OrderedDict()

        x = -float(grids_x_distance_between)
        y = -float(grids_y_distance_between)

        for x_grids in range(0, int(grids_x_direction_amount), 1):
            x += float(grids_x_distance_between)
            grids_x_dictionary[x_grids] = x
            print(f"X Grid {x_grids}: {x}")

        for y_grids in range(0, int(grids_y_direction_amount), 1):
            y += grids_y_distance_between
            grids_y_dictionary[y_grids] = y
            print(f"Y Grid {y_grids}: {y}")

        x_min = list(grids_x_dictionary.items())[0][1]
        x_max = list(grids_x_dictionary.items())[-1][1]

        y_min = list(grids_y_dictionary.items())[0][1]
        y_max = list(grids_y_dictionary.items())[-1][1]

        x_min_overlap = x_min-grid_extends
        x_max_overlap = x_max+grid_extends

        y_min_overlap = y_min-grid_extends
        y_max_overlap = y_max+grid_extends

        print(
            f"x_min: {x_min}, x_max: {x_max}, y_min: {y_min}, y_max: {y_max}")
        print(
            f"x_min_overlap: {x_min_overlap}, x_max_overlap: {x_max_overlap}, y_min_overlap: {y_min_overlap}, y_max_overlap: {y_max_overlap}")

        polylineSet = []
        gridX = []
        gridY = []

        for i_grid in grids_x_dictionary.items():
            print(f"Creating X grid line at {i_grid[1]}")

            point_1 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (i_grid[1], y_min_overlap))
            point_2 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (i_grid[1], y_max_overlap))

            Line = IFC_MODEL.ifcfile.createIfcPolyline([point_1, point_2])
            polylineSet.append(Line)

            grid = IFC_MODEL.ifcfile.createIfcGridAxis()
            grid.AxisTag = str(i_grid[0]) + "X"
            grid.AxisCurve = Line
            grid.SameSense = True
            gridX.append(grid)

        for i_grid in grids_y_dictionary.items():
            print(f"Creating Y grid line at {i_grid[1]}")

            point_1 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (x_min_overlap, i_grid[1]))
            point_2 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (x_max_overlap, i_grid[1]))

            Line = IFC_MODEL.ifcfile.createIfcPolyline([point_1, point_2])
            polylineSet.append(Line)

            grid = IFC_MODEL.ifcfile.createIfcGridAxis()
            grid.AxisTag = str(i_grid[0]) + "Y"
            grid.AxisCurve = Line
            grid.SameSense = True
            gridY.append(grid)

        print(f"polylineSet: {polylineSet}")
        print(f"gridX: {gridX}")
        print(f"gridY: {gridY}")

        # Defining the grid
        PntGrid = IFC_MODEL.ifcfile.createIfcCartesianPoint(O)

        myGridCoordinateSystem = IFC_MODEL.ifcfile.createIfcAxis2Placement3D()
        myGridCoordinateSystem.Location = PntGrid
        myGridCoordinateSystem.Axis = IFC_MODEL.ifcfile.createIfcDirection(Z)
        myGridCoordinateSystem.RefDirection = IFC_MODEL.ifcfile.createIfcDirection(
            X)

        grid_placement = IFC_MODEL.ifcfile.createIfcLocalPlacement()
        print(f"IFC story PLACEMENT: {IFC_MODEL.story_placement}")
        grid_placement.PlacementRelTo = IFC_MODEL.story_placement
        grid_placement.RelativePlacement = myGridCoordinateSystem

        print(f"Grid Placement: {grid_placement}")

        grid_curvedSet = IFC_MODEL.ifcfile.createIfcGeometricCurveSet(
            polylineSet)

        print("Creating grid shape representation...")
        gridShape_Reppresentation = IFC_MODEL.ifcfile.createIfcShapeRepresentation()
        gridShape_Reppresentation.ContextOfItems = IFC_MODEL.footprint_context
        gridShape_Reppresentation.RepresentationIdentifier = 'FootPrint'
        gridShape_Reppresentation.RepresentationType = 'GeometricCurveSet'
        gridShape_Reppresentation.Items = [grid_curvedSet]
        print(f"Grid Shape Representation: {gridShape_Reppresentation}")

        print("Creating grid product definition shape...")
        grid_Representation = IFC_MODEL.ifcfile.createIfcProductDefinitionShape()
        grid_Representation.Representations = [gridShape_Reppresentation]
        print(f"Grid Product Definition Shape: {grid_Representation}")

        print("Creating grid...")
        myGrid = IFC_MODEL.ifcfile.createIfcGrid(
            IFC_MODEL.create_guid(), IFC_MODEL.owner_history)
        myGrid.ObjectPlacement = grid_placement
        myGrid.Representation = grid_Representation
        myGrid.UAxes = gridX
        myGrid.VAxes = gridY
        print(f"Grid: {myGrid}")

        print("Creating container spatial structure...")
        container_SpatialStructure = IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(
            IFC_MODEL.create_guid(), IFC_MODEL.owner_history)
        container_SpatialStructure.Name = 'BuildingstoryContainer'
        container_SpatialStructure.Description = 'BuildingstoryContainer for Elements'
        container_SpatialStructure.RelatingStructure = IFC_MODEL.site
        container_SpatialStructure.RelatedElements = [myGrid]
        print(f"Container Spatial Structure: {container_SpatialStructure}")

        print("Grid creation completed.")

        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_wall(sid: Annotated[str, InjectedToolArg], story_n: int = 1, start_coord: str = "10,0,0", end_coord: str = "0,0,0", height: float = 30.0, thickness: float = 1.0, material: str = None, ) -> bool:
    """
    Creates a single wall in the Revit document based on specified start and end coordinates, level, wall type, structural flag, height, and thickness.

    Parameters:
    - story_n (int): The story number that the user wants to place the column on
    - start_coord (str): The (x, y, z) coordinates of the wall's start point in the format "x,y,z".
    - end_coord (str): The (x, y, z) coordinates of the wall's end point in the format "x,y,z".
    - height (float): The height of the wall. The default should be each story's respective elevations.
    - thickness (float): The thickness of the wall in ft.
    - material (str): what the wall is made out of.
    """
    # global retrieval_tool
    if material:
        material = material.lower()
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        print('IFC_MODEL IN CREATE WALL: ', IFC_MODEL)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        print("length of ifc building storey",
              len(IFC_MODEL.building_story_list))
        if len(IFC_MODEL.building_story_list) < story_n:
            IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")
            print("created building storey. current length:",
                  len(IFC_MODEL.building_story_list))

        story = IFC_MODEL.building_story_list[story_n - 1]
        elevation = (story.Elevation)
        story_placement = story.ObjectPlacement

        # 1. Populate the coordinates for start and end
        start_coord, end_coord = list(map(float, start_coord.split(','))), list(tuple(
            map(float, end_coord.split(','))))
        start_coord[2], end_coord[2] = elevation, elevation
        start_coord, end_coord = tuple(start_coord), tuple(end_coord)

        # 2. Calculate the wall length and direction
        length = ((end_coord[0] - start_coord[0]) ** 2 +
                  (end_coord[1] - start_coord[1]) ** 2) ** 0.5

        if length > 0:
            direction = (
                (end_coord[0] - start_coord[0]) /
                length,  # normalized x component
                (end_coord[1] - start_coord[1]) / \
                length,  # normalized y component
                0.0  # z component remains 0 as we're dealing with a 2D plane
            )

            # 3. IFC model setup
            context = IFC_MODEL.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
            # 4. Create the wall placement with correct direction
            wall_placement = IFC_MODEL.create_ifclocalplacement(
                start_coord, Z, direction, relative_to=story_placement)
            # 5. Create the wall
            wall = IFC_MODEL.create_wall(
                context, owner_history, wall_placement, length, height, thickness, material)
            wall_guid = wall.GlobalId
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building story Container", None, [wall], story)

            IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        return True, wall_guid
    except Exception as e:
        print(f"Error creating wall: {e}")
        raise


@tool
def create_isolated_footing(sid: Annotated[str, InjectedToolArg], story_n: int = 1, location: tuple = (0.0, 0.0, 0.0), length: float = 10.0, width: float = 10.0, thickness: float = 1.0) -> bool:
    """
    Creates a shallow isolated structural foundation footing on the specified story.

    Parameters:
    - story_n (int): The story number where the footing will be created.
    - location (tuple): The (x, y, z) coordinates of the footing's location.
    - length (float): The length of the footing.
    - width (float): The width of the footing.
    - thickness (float): The thickness of the footing.
    """
    global retrieval_tool
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        # Get story information
        if len(IFC_MODEL.building_story_list) < story_n:
            IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")

        story = IFC_MODEL.building_story_list[story_n - 1]
        elevation = (story.Elevation)
        story_placement = story.ObjectPlacement
        print(f"elevation: {elevation}")

        # Adjust location Z-coordinate by adding the story's elevation
        location = (location[0], location[1], location[2] + elevation)

        # IFC model information
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # Call the function in ifc.py to create the footing
        footing = IFC_MODEL.create_isolated_footing(
            location, length, width, thickness)
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building story Container", None, [footing], story)

        # Save structure
        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        retrieval_tool = parse_ifc()

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_strip_footing(sid: Annotated[str, InjectedToolArg], story_n: int = 1, start_point: tuple = (0.0, 0.0, 0.0), end_point: tuple = (10.0, 0.0, 0.0), width: float = 1.0, depth: float = 1.0) -> bool:
    """
    Creates a continuous footing (strip footing) on the specified story.

    Parameters:
    - story_n (int): The story number where the footing will be created.
    - start_point (tuple): The (x, y, z) coordinates of the start point of the footing.
    - end_point (tuple): The (x, y, z) coordinates of the end point of the footing.
    - width (float): The width of the footing.
    - depth (float): The depth of the footing.
    """
    global retrieval_tool
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        # Get story information
        if len(IFC_MODEL.building_story_list) < story_n:
            IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")

        story = IFC_MODEL.building_story_list[story_n - 1]
        elevation = (story.Elevation)
        story_placement = story.ObjectPlacement
        print(f"elevation: {elevation}")

        # Adjust start and end points Z-coordinate by adding the story's elevation
        start_point = (start_point[0], start_point[1],
                       start_point[2] + elevation)
        end_point = (end_point[0], end_point[1], end_point[2] + elevation)

        # IFC model information
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # Call the function in ifc.py to create the continuous footing
        footing = IFC_MODEL.create_strip_footing(
            start_point, end_point, width, depth)
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building story Container", None, [footing], story)

        # Save structure
        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        # retrieval_tool = parse_ifc()

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_void_in_wall(sid: Annotated[str, InjectedToolArg], host_wall_id=None, width=1.0, height=1.0, depth=2.0, void_location=(1.0, 0.0, 1.0)) -> bool:
    """
    Creates a void in the specified host element and commits it to the IFC file.

    Parameters:
    - host_wall_id: The GUID of the IFC wall element in which the void will be created.
    - width (float): The width of the void (X axis).
    - height (float): The height of the void (Z axis).
    - depth (float): The depth of the void (thickness of the wall) (Y axis).
    - void_location (tuple): The local coordinates (x, y, z) of the void relative to the wall. Each value in this tuple should be a float. Example: (0., 0., 0.)
    """
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        # Retrieve wall with element ID
        walls = IFC_MODEL.ifcfile.by_type("IfcWall")
        host_wall = None
        for wall in walls:
            if str(wall.GlobalId).strip() == str(host_wall_id).strip():
                host_wall = wall
                break

        if host_wall is None:
            raise ValueError(f"No wall found with GlobalId: {host_wall_id}")

        # Convert void_location to list of floats
        try:
            # Handle both list and tuple inputs
            if isinstance(void_location, (list, tuple)):
                void_location = [float(coord) for coord in void_location]
            else:
                void_location = [float(x) for x in str(void_location).strip('()[]').split(',')]
            print(f"Void Location: {void_location}, Void Location type: {type(void_location)}")
        except:
            print(f"Cannot convert void_location to correct format. Original void_location: {void_location}")
            raise ValueError("Invalid void_location format")

        # Create void element
        IFC_MODEL.create_void_in_wall(
            wall=host_wall, 
            width=float(width), 
            height=float(height), 
            depth=float(depth), 
            void_location=void_location
        )

        # Save structure
        IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        print("Void created and committed to the IFC file successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while creating the void: {e}")
        raise


@tool
def create_floor(sid: Annotated[str, InjectedToolArg], story_n: int = 1, point_list: list = [(0., 0., 0.), (0., 100., 0.), (100., 100., 0.), (100., 0., 0.)], slab_thickness: float = 1.0) -> bool:
    """
    Creates a floor in the specified story with given dimensions and thickness.

    Parameters:
    - story_n (int): The story number where the slab will be created.
    - point_list (list): The list of points that make up the floor boundary. Each value should be a float.
    - slab_thickness (float): The thickness of the slab.
    """
    # global retrieval_tool
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        print(
            f"story_n: {story_n}, point_list: {point_list}, slab_thickness: {slab_thickness}")

        # 1. Get model information.
        try:
            context = IFC_MODEL.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
        except Exception as e:
            print(f"Error getting model context: {e}")
            raise

        try:
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
            owner_history.CreationDate = int(owner_history.CreationDate)
        except Exception as e:
            print(f"Error getting owner_history: {e}")
            raise

        # 2. Get story information
        try:
            if len(IFC_MODEL.building_story_list) < story_n:
                IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")

            story = IFC_MODEL.building_story_list[story_n - 1]
            elevation = story.Elevation
            story_placement = story.ObjectPlacement
        except Exception as e:
            print(f"Error getting story information: {e}")
            raise

        print(f"elevation: {elevation}")

        # 3. Create slab boundary
        try:
            slab = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlab")
            slab.Name = "Slab"
            slab_placement = IFC_MODEL.create_ifclocalplacement(
                (0., 0., float(elevation)), Z, X, relative_to=story_placement)
            slab.ObjectPlacement = slab_placement

            ifc_slabtype = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlabType")
            ifcopenshell.api.run("type.assign_type", IFC_MODEL.ifcfile,
                                 related_objects=[slab], relating_type=ifc_slabtype)

        except Exception as e:
            print(f"Error creating slab boundary: {e}")
            raise

        # 4. Create points for slab boundary
        try:
            points = [IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (x, y, z)) for x, y, z in point_list]
            points.append(points[0])  # close loop

            # 5. Create boundary polyline
            slab_line = IFC_MODEL.ifcfile.createIfcPolyline(points)
            slab_profile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef(
                "AREA", None, slab_line)
            ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)
        except Exception as e:
            print(f"Error creating points for slab boundary: {e}")
            raise

        # 6. Create local axis placement
        try:
            point = IFC_MODEL.ifcfile.createIfcCartesianPoint((0.0, 0.0, 0.0))
            dir1 = IFC_MODEL.ifcfile.createIfcDirection((0., 0., 1.0))
            dir2 = IFC_MODEL.ifcfile.createIfcDirection((1.0, 0., 0.0))
            axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                point, dir1, dir2)
        except Exception as e:
            print(f"Error creating local axis placement: {e}")
            raise

        # 7. Create extruded slab geometry
        try:
            extrusion = slab_thickness
            slab_solid = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid(
                slab_profile,  axis2placement, ifc_direction, extrusion)
            shape_representation = IFC_MODEL.ifcfile.createIfcShapeRepresentation(ContextOfItems=context,
                                                                                  RepresentationIdentifier='Body',
                                                                                  RepresentationType='SweptSolid',
                                                                                  Items=[slab_solid])
        except Exception as e:
            print(f"Error creating extruded slab geometry: {e}")
            raise

        print(
            f"Shape Representation: {shape_representation}, IFC Slab Type: {ifc_slabtype}, IFC Slab: {slab}, story: {story}, Elevation: {elevation}, Points: {points}")

        # 8. Create product entity and assign to spatial container
        try:
            ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                                 product=ifc_slabtype, representation=shape_representation)
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building story Container", None, [slab], story)
        except Exception as e:
            print(
                f"Error creating product entity and assigning to spatial container: {e}")
            raise

        # 9. Save the structure
        try:
            IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        except Exception as e:
            print(f"Error saving structure: {e}")
            raise

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_roof(sid: Annotated[str, InjectedToolArg], story_n: int = 1, point_list: list = [(0, 0, 0), (0, 100, 0), (100, 100, 0), (100, 0, 0)], roof_thickness: float = 1.0) -> bool:
    """
    Creates a roof on the specified story with given dimensions and thickness.

    Parameters:
    - story_n (int): The story number where the slab will be created.
    - point_list (list): The list of points that make up the roof boundary. The z-coordinate of the points should by default be the elevation of the story the roof is being placed at. Unless otherwise asked by the user.
    Each point should be a tuple of three floats. Note: If roof is being called within a structure, unless otherwise specified, the z-coordinate should be the height of the elements it is being placed on e.g. if its a set of walls, the z-coordinate should be the height of the walls so if the walls are 10 feet tall, the roof should be at 10 feet. 
    - roof_thickness (float): The thickness of the roof.
    """
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        print(
            f"story_n: {story_n}, point_list: {point_list}, roof_thickness: {roof_thickness}")
        try:
            # 1. Get model information
            context = IFC_MODEL.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
        except Exception as e:
            print(f"Error getting context: {e}")
            raise

        try:
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
            owner_history.CreationDate = int(owner_history.CreationDate)
        except Exception as e:
            print(f"Error getting owner_history: {e}")
            raise

        try:
            # 2. Get story information
            if len(IFC_MODEL.building_story_list) < story_n:
                IFC_MODEL.create_building_stories(0.0, f"Level {story_n}")
        except Exception as e:
            print(f"Error creating building stories: {e}")
            raise

        try:
            story = IFC_MODEL.building_story_list[story_n - 1]
            print(f"story: {story}")
            print(f"story_name: {story.Name}")
        except Exception as e:
            print(f"Error getting story: {e}")
            raise

        try:
            elevation = (float(story.Elevation) + float(point_list[0][2]))
        except Exception as e:
            print(f"Error getting elevation: {e}")
            raise

        try:
            story_placement = story.ObjectPlacement
        except Exception as e:
            print(f"Error getting story_placement: {e}")
            raise

        print(f"elevation: {elevation}")

        try:
            # 3. Create slab boundary
            roof = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcRoof")
        except Exception as e:
            print(f"Error creating roof entity: {e}")
            raise

        try:
            roof_placement = IFC_MODEL.create_ifclocalplacement(
                (0., 0., elevation), Z, X, relative_to=story_placement)
        except Exception as e:
            print(f"Error creating roof_placement: {e}")
            raise

        try:
            roof.ObjectPlacement = roof_placement
        except Exception as e:
            print(f"Error setting roof.ObjectPlacement: {e}")
            raise

        try:
            # 4. Create points for roof boundary
            points = [IFC_MODEL.ifcfile.createIfcCartesianPoint(
                [float(x), float(y), float(z)]) for x, y, z in point_list]
        except Exception as e:
            print(f"Error creating points: {e}")
            raise

        try:
            points.append(points[0])
        except Exception as e:
            print(f"Error appending first point: {e}")
            raise

        try:
            # 5. Create boundary polyline
            roof_line = IFC_MODEL.ifcfile.createIfcPolyline(points)
        except Exception as e:
            print(f"Error creating roof_line: {e}")
            raise

        try:
            roof_profile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef(
                "AREA", None, roof_line)
        except Exception as e:
            print(f"Error creating roof_profile: {e}")
            raise

        try:
            ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)
        except Exception as e:
            print(f"Error creating ifc_direction: {e}")
            raise

        try:
            # 6. Create local axis placement
            point = IFC_MODEL.ifcfile.createIfcCartesianPoint([0.0, 0.0, 0.0])
        except Exception as e:
            print(f"Error creating point: {e}")
            raise

        try:
            dir1 = IFC_MODEL.ifcfile.createIfcDirection([0., 0., 1.])
        except Exception as e:
            print(f"Error creating dir1: {e}")
            raise

        try:
            dir2 = IFC_MODEL.ifcfile.createIfcDirection([1., 0., 0.])
        except Exception as e:
            print(f"Error creating dir2: {e}")
            raise

        try:
            axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                point, dir1, dir2)
        except Exception as e:
            print(f"Error creating axis2placement: {e}")
            raise

        try:
            # 7. Create extruded roof geometry
            extrusion = roof_thickness
        except Exception as e:
            print(f"Error setting extrusion: {e}")
            raise

        try:
            roof_solid = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid(
                roof_profile,  axis2placement, ifc_direction, extrusion)
        except Exception as e:
            print(f"Error creating roof_solid: {e}")
            raise

        try:
            shape_representation = IFC_MODEL.ifcfile.createIfcShapeRepresentation(ContextOfItems=context,
                                                                                  RepresentationIdentifier='Body',
                                                                                  RepresentationType='SweptSolid',
                                                                                  Items=[roof_solid])
        except Exception as e:
            print(f"Error creating shape_representation: {e}")
            raise
        try:
            # 8. Assign representation using ifcopenshell.api.run
            ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                                 product=roof, representation=shape_representation)

        except Exception as e:
            print(f"Error assigning representation: {e}")
            raise

        try:
            # 9. Create product entity and assign to spatial container
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building story Container", None, [roof], story)
        except Exception as e:
            print(f"Error assigning container: {e}")
            raise

        try:
            # 10. Save structure
            IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
        except Exception as e:
            print(f"Error saving IFC file: {e}")
            raise

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def search_canvas(sid: Annotated[str, InjectedToolArg], search_query: str, search_file: str = 'canvas.ifc') -> str:
    """
    Provided a user query, this function will search the IFC file and return the relevant objects in a string format.
    Parameters:
    - search_query (str): The user query that the user inputs. e.g. find all walls, find all columns, find all beams, find left most wall
    - search file (str): The file to be searched. If the user wants to search the canvas (the current file they are working on), the value should be canvas.ifc. If the user wants to search the loaded file, the value should be user.ifc
    """
    global openai_client
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)

        loaded_file = ifcopenshell.open(f"public/{sid}/" + search_file)
        res = openai_client.chat.completions.create(
            model='gpt-4o',
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": """You are an AI BIM Modeler part of a larger workflow. Your task is to assist with the search the IFC file (3-D model file)
                        Specifically, you will be provided with a search query by the user. You must understand the search query and then return which IFC objects
                        the query is relevant to. You will return a JSON object with the the key as 'objects' and the value as list of all the IFC entities that are
                        relevant. Sometimes the user request may be to delete certain objects or search for certain objects. In that case, you will return a JSON object with the the key as 'objects' 
                        and the value as list of all the IFC entities that are relevant.
                        Here's the mapping of objects to their relevant IFC mapping:
                        walls -> IFCWall & IfcWallStandardCase
                        window -> IFCWindow
                        column -> IfcColumn
                        roof -> IfcRoof
                        building -> IfcBuilding
                        door -> IfcDoor
                        beam -> IfcBeam
                        slab -> IfcSlab
                        floor -> IfcSlab
                        story -> IfcBuildingStorey
                        """
                },
                {
                    "role": "user",
                    "content": f"Search Query: {search_query}"
                }
            ]
        )
        try:
            json_object = json.loads(res.choices[0].message.content) or {}
        except json.JSONDecodeError:
            print("Invalid JSON response.")
            raise
        if json_object:
            objects_list = json_object.get('objects', [])
            all_entities_list = []
            for object in objects_list:
                try:
                    all_entities_list.extend(loaded_file.by_type(object))
                except:
                    raise Exception('No such object found in IFC file', object)
            print(all_entities_list)

            all_relevant_objects = []
            feature_extractor = IfcEntityFeatureExtractor()
            for entity in all_entities_list:
                features = feature_extractor.extract_entity_features(entity)
                if features:
                    all_relevant_objects.append(features)
            # Format the output as a string
            formatted_output = format_output_search_canvas(
                all_relevant_objects)
            return formatted_output
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def delete_objects(sid: Annotated[str, InjectedToolArg], delete_query: str) -> bool:
    """
    Provided a user query, this function will delete the relevant objects from the ifc file.
    Parameters:
    - delete_query (str): The user query that the user inputs. e.g. delete the right most wall, delete all the columns etc.
    """
    global openai_client
    print('[delete_objects] sid', sid)
    print('[delete_objects] delete_query', delete_query)
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        print('[delete_objects] IFC_MODEL', IFC_MODEL)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)
            IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        try:
            tool_input = {
                "sid": sid,
                "search_query": delete_query,
                "search_file": "canvas.ifc"
            }
            relevant_objects = search_canvas(tool_input)
            print('[delete_objects] relevant_objects', relevant_objects)
        except Exception as e:
            print('[delete_objects][search_canvas] An error occurred: ', e)
            raise
        res = openai_client.chat.completions.create(
            model='gpt-4o',
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": """You are an AI BIM Modeler part of a larger workflow. Your specific task is to identify which objects need to be deleted based on the user query.
                    You will be provided with a string that contains information about the relevant objects related to the user query. The information about each object will include
                    its global id. Your job is to return a JSON object with key as 'objects' and the value as list of all the global ids of the objects that need to be deleted.
                    """
                },
                {
                    "role": "user",
                    "content": f"Relevant Objects: {relevant_objects}, Delete Query: {delete_query}"
                }
            ]
        )
        print('[delete_objects] res', res)
        try:
            json_object = json.loads(res.choices[0].message.content) or {}
        except json.JSONDecodeError:
            print("Invalid JSON response.")
            raise
        if json_object:
            objects_ids_list = json_object.get('objects', [])
            print('[delete_objects] objects_ids_list', objects_ids_list)
            for object_id in objects_ids_list:
                ifc_object = IFC_MODEL.ifcfile.by_guid(object_id)
                IFC_MODEL.ifcfile.remove(ifc_object)
                IFC_MODEL.save_ifc(f"public/{sid}/canvas.ifc")
            return True
    except Exception as e:
        print('[delete_objects] An error occurred: ', e)
        raise
    return False


@tool
def refresh_canvas(sid: Annotated[str, InjectedToolArg]) -> bool:
    """
    Refreshes the canvas by sending a socket call of file change.
    The function is invoked when user types in 'refresh', 'refresh canvas' or 'refresh the canvas'
    """
    try:
        sio.emit('fileChange', {
                 'userId': 'BuildSync', 'message': 'A new change has been made to the file', 'file_name': f'public/{sid}/canvas.ifc'})
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
async def step_by_step_planner(sid: Annotated[str, InjectedToolArg], user_request: str) -> str:
    """
    The function is provided with the user_request. If the user's request is unclear, lacks architectural clarity, or is not specific,
    the function is invoked to make the request more clearer and specific with step by step guidelines of the process to perform the user's
    request. The function should not be unnecessarily called for simple requests to avoid latency and should be used for complex requests e.g.
    Create a basic 3D model of a four-story residential house with dimensions of 10 by 6 meters,
    Create a 3-story L-shaped house with each leg of the L being 8 meters long and 4 meters wide. Place a door at the corner of the L and a window on each side of the L. I want the whole building to be made of wood.

    Parameters:
    - user_request (str): The user request that the user inputs.

    Returns:
    - step_by_step_plan (str): The step by step plan to perform the user's request.
    """
    global groq_client
    try:
        IFC_MODEL = global_store.sid_to_ifc_model.get(sid, None)
        if IFC_MODEL is None:
            print("No IFC model found for the given session.")
            create_session(sid)

        completion = await groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": architect_prompt
                }
            ],
            temperature=0.8,
        )
        print(completion.choices[0].message.content)
        return completion.choices[0].message.content
    except Exception as e:
        print('[tools_graph.py] step_by_step_planner: ', e)
        return ''


@tool
async def _get_column_name(column_index: int) -> str:
    """
    Generates a unique name for a column based on its index.

    Parameters:
    - column_index (int): The index of the column for which a name is being generated.

    Returns:
    str: A unique name for the column.
    """
    return "Column" + str(column_index)


@tool
async def edit_location(element_id: int = None, target_transformation: str = "0,0,0", doc=None) -> None:
    """
    Moves an element to a new location based on the target transformation coordinates.

    Parameters:
    - element_id (int): The ID of the element to move.
    - target_transformation (str): The new coordinates in the format "x,y,z".
    - doc: The Revit document where the element is located.
    """


@tool
async def _get_row_name(row_index: int) -> str:
    """
    Generates a unique name for a row based on its index using an alphabetical naming scheme.

    Parameters:
    - row_index (int): The index of the row for which a name is being generated.

    Returns:
    str: A unique name for the row.
    """
    return "Row" + str(row_index)


async def get_selected_elements() -> list:
    """
    Returns elements that are currently selected in the Revit UI.

    Returns:
    list: List of selected elements.
    """
    return []


@tool
async def get_all_elements() -> list:
    """
    Returns all elements in the current document.

    Returns:
    list: List of all elements in the current document.
    """
    return []


@tool
async def element_to_text(element: object) -> str:
    """
    Generates a text description for a Revit element.

    Parameters:
    - element (object): The Revit element to describe.

    Returns:
    str: A string describing the element in a language model-friendly way.
    """
    return "Description of element"
