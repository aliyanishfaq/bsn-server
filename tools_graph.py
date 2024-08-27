from ifc_parser import parse_ifc
from ifc import IfcModel
from langchain_core.tools import tool
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

load_dotenv()

global levels_dict
levels_dict = {}

global client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

## ---- TOOLS FOR MODEL TO CALL ----- #

global IFC_MODEL
IFC_MODEL = None
O = 0., 0., 0.
X = 1., 0., 0.
Y = 0., 1., 0.
Z = 0., 0., 1.

@tool
async def create_on_start():
    """
    Creates a new IFC model for the user.
    """
    global IFC_MODEL
    # global retrieval_tool
    try:
        print('Creating a new IFC model')
        ifc_model = IfcModel(
            creator="Aliyan",
            organization="BuildSync",
            application="IfcOpenShell",
            application_version="0.5",
            project_name="Modular IFC Project",
            filename=None
        )
        IFC_MODEL = ifc_model
        ifc_model.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_session() -> bool:
    """
    Creates a new IFC model for the user.
    """
    global IFC_MODEL
    # global retrieval_tool
    try:
        print('Creating a new IFC model')
        ifc_model = IfcModel(
            creator="Aliyan",
            organization="BuildSync",
            application="IfcOpenShell",
            application_version="0.5",
            project_name="Modular IFC Project",
            filename=None
        )
        IFC_MODEL = ifc_model
        ifc_model.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_building_storey(elevation: float = 0.0, name: str = "Level 1") -> bool:
    """
    Creates building storeys with the specified amount, elevation, and height.

    Parameters:
    - elevation (float): The elevation of the building storeys in feet. If there are already storeys been created, then this is the elevation of the tallest building storey
    - name (string): The name of the elevation. Name of each story should be unique.
    """
    global retrieval_tool
    global levels_dict

    try:
        # Create the building storey
        IFC_MODEL.create_building_storeys(elevation, name)
        IFC_MODEL.save_ifc("public/canvas.ifc")

        # Update the global dictionary
        levels_dict[name] = elevation

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


def create_beam(start_coord: str = "0,0,0", end_coord: str = "1,0,0", section_name: str = 'W16X40', storey_n: int = 1) -> None:
    """
    Creates a beam at the specified start coordinate with the given dimensions.

    Parameters:
    - start_coord (str): The (x, y, z) coordinates of the beam's start point in the format "x,y,z".
    - end_coord (str): The (x, y, z) coordinates of the beam's end point in the format "x,y,z".
    - section_name (str): The beam profile name (e.g. W16X40).
    - storey_n (int): The storey number that the user wants to place the beam on
    """
    # global retrieval_tool
    try:

        # format coord and direction
        start_coord = tuple(map(float, start_coord.split(',')))
        end_coord = tuple(map(float, end_coord.split(',')))

        direction = IFC_MODEL.calc_direction(start_coord, end_coord)
        length = IFC_MODEL.calc_length(start_coord, end_coord)

        # IFC model setup
        context = IFC_MODEL.ifcfile.by_type(
            "IfcGeometricRepresentationContext")[0]
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
        if len(IFC_MODEL.building_storey_list) < storey_n:
            IFC_MODEL.create_building_storeys(
                elevation=0, name="Level 1")
        storey = IFC_MODEL.building_storey_list[storey_n - 1]

        # 0. Initiate IfcBeam
        # Note: eventually, we'll want to pass in various beam names.
        bm = IFC_MODEL.ifcfile.createIfcBeam(
            IFC_MODEL.create_guid(), owner_history, "Beam")

        # 1-3. Define beam placement
        Z = (0.0, 0.0, 1.0)

        # 1. Define beam starting point, hosting axis, & direction.
        bm_axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
            IFC_MODEL.ifcfile.createIfcCartesianPoint(start_coord))
        bm_axis2placement.Axis = IFC_MODEL.ifcfile.createIfcDirection(
            direction)

        crossprod = IFC_MODEL.calc_cross(direction, Z)
        bm_axis2placement.RefDirection = IFC_MODEL.ifcfile.createIfcDirection(
            crossprod)

        # 2. Create LocalPlacement for beam.
        bm_placement = IFC_MODEL.ifcfile.createIfcLocalPlacement(
            storey, bm_axis2placement)  # can pass building stories as host
        bm.ObjectPlacement = bm_placement

        # 3. Create 3D axis placement for extrusion.
        bm_extrudePlacement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
            IFC_MODEL.ifcfile.createIfcCartesianPoint((0., 0., 0.)))

        # 4. Create extruded area section for beam.
        bm_extrusion = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid()
        ifcclosedprofile = IFC_MODEL.get_wshape_profile(section_name)
        ifcclosedprofile.ProfileName = section_name
        bm_extrusion.SweptArea = ifcclosedprofile
        bm_extrusion.Position = bm_extrudePlacement
        bm_extrusion.ExtrudedDirection = IFC_MODEL.ifcfile.createIfcDirection(
            (0.0, 0.0, 1.0))
        bm_extrusion.Depth = length

        # 5. Create shape representation for beam.
        bm_rep = IFC_MODEL.ifcfile.createIfcShapeRepresentation(
            context, "Body", "SweptSolid", [bm_extrusion])

        # 6. Create a product shape for beam.
        bm_prod = IFC_MODEL.ifcfile.createIfcProductDefinitionShape()
        bm_prod.Representations = [bm_rep]

        bm.Representation = bm_prod

        # 7. Add beam to IFC file & save
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building Storey Container", None, [bm], storey)

        IFC_MODEL.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


"""
    @tool
    def create_beam(length: float = 10.0, start_coord: str = "0,0,0", direction: tuple = "1,0,0", section_name: str = 'W16X40', storey_n: int = 1) -> bool:

        Creates a beam at the specified start coordinate with the given dimensions.

        Parameters:
        - length (float): The length of the beam.
        - start_coord (str): The (x, y, z) coordinates of the beam's start point in the format "x,y,z".
        - direction (str): The direction the beam faces in the format "x,y,z". The default is X direction
        - section_name (str): The beam profile name (e.g. W16X40).

        global retrieval_tool

        try:
            # format coord and direction
            start_coord = tuple(list(map(float, start_coord.split(','))))
            direction = tuple(list(map(float, direction.split(','))))

            print(start_coord, direction)

            # IFC model setup
            context = IFC_MODEL.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
            if len(IFC_MODEL.building_storey_list) < storey_n:
                IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")
            storey = IFC_MODEL.building_storey_list[storey_n - 1]

            # 0. Initiate IfcBeam
            # Note: eventually, we'll want to pass in various beam names.
            bm = IFC_MODEL.ifcfile.createIfcBeam(
                IFC_MODEL.create_guid(), owner_history, "Beam")

            # 1-3. Define beam placement
            Z = (0.0, 0.0, 1.0)

            # 1. Define beam starting point, hosting axis, & direction.
            bm_axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                IFC_MODEL.ifcfile.createIfcCartesianPoint(start_coord))
            bm_axis2placement.Axis = IFC_MODEL.ifcfile.createIfcDirection(
                direction)

            # Calculate cross product & convert np.float64 to Python float
            crossprod = tuple(np.cross(direction, Z))
            crossprod_list = list(crossprod)  # convert tuple to list
            # modify the elements from np.float64 to Python float
            for i in range(len(crossprod_list)):
                crossprod_list[i] = float(crossprod_list[i])
            # convert the list back to a tuple
            crossprod = tuple(crossprod_list)

            bm_axis2placement.RefDirection = IFC_MODEL.ifcfile.createIfcDirection(
                crossprod)

            # 2. Create LocalPlacement for beam.
            bm_placement = IFC_MODEL.ifcfile.createIfcLocalPlacement(
                storey, bm_axis2placement)  # can pass building stories as host
            bm.ObjectPlacement = bm_placement

            # 3. Create 3D axis placement for extrusion.
            bm_extrudePlacement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                IFC_MODEL.ifcfile.createIfcCartesianPoint((0., 0., 0.)))

            # 4. Create extruded area section for beam.
            bm_extrusion = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid()
            bm_extrusion.SweptArea = IFC_MODEL.get_wshape_profile(section_name)
            bm_extrusion.Position = bm_extrudePlacement
            bm_extrusion.ExtrudedDirection = IFC_MODEL.ifcfile.createIfcDirection(
                (0.0, 0.0, 1.0))
            bm_extrusion.Depth = length

            # 5. Create shape representation for beam.
            bm_rep = IFC_MODEL.ifcfile.createIfcShapeRepresentation(
                context, "Body", "SweptSolid", [bm_extrusion])

            # 6. Create a product shape for beam.
            bm_prod = IFC_MODEL.ifcfile.createIfcProductDefinitionShape()
            bm_prod.Representations = [bm_rep]

            bm.Representation = bm_prod

            # 7. Add beam to IFC file & save
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [bm], storey)

            IFC_MODEL.save_ifc("public/canvas.ifc")
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            raise
"""


def create_column(storey_n: int = 1, start_coord: str = "0,0,0", height: float = 12, section_name: str = "W12X53") -> bool:
    """
    Creates a single column in the Revit document based on specified location, width, depth, and height.

    Parameters:
    - storey_n (int): The storey number that the user wants to place the column on
    - start_coord (str): The (x, y, z) coordinates of the column's location in the format "x,y,z".
    - height (float): The height of the column in feet.
    - section_name (string): The name of the column type.
    """
    # global retrieval_tool
    try:
        # first get the appropriate storey and its elevation, etc
        if len(IFC_MODEL.building_storey_list) < storey_n:
            IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")
        storey = IFC_MODEL.building_storey_list[storey_n - 1]
        elevation = (storey.Elevation)

        # populate the coordinate
        start_coord = list(map(float, start_coord.split(',')))
        start_coord[2] = elevation
        start_coord = tuple(start_coord)

        # IFC model setup
        context = IFC_MODEL.ifcfile.by_type(
            "IfcGeometricRepresentationContext")[0]
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # Get the storey's placement
        storey_placement = storey.ObjectPlacement

        # Create the column placement
        column_placement = IFC_MODEL.create_ifclocalplacement(
            start_coord, Z, X, relative_to=storey_placement)

        # Create the column
        column = IFC_MODEL.create_column(
            context=context, owner_history=owner_history, column_placement=column_placement, height=height, section_name=section_name)
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building Storey Container", None, [column], storey)

        # Save structure
        IFC_MODEL.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_grid(grids_x_distance_between: float = 10.0, grids_y_distance_between: float = 10.0, grids_x_direction_amount: int = 5, grids_y_direction_amount: int = 5, grid_extends: float = 50.0) -> bool:
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
        print("Creating grid...")
        # global retrieval_tool

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
        print(f"IFC STOREY PLACEMENT: {IFC_MODEL.storey_placement}")
        grid_placement.PlacementRelTo = IFC_MODEL.storey_placement
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
        container_SpatialStructure.Name = 'BuildingStoreyContainer'
        container_SpatialStructure.Description = 'BuildingStoreyContainer for Elements'
        container_SpatialStructure.RelatingStructure = IFC_MODEL.site
        container_SpatialStructure.RelatedElements = [myGrid]
        print(f"Container Spatial Structure: {container_SpatialStructure}")

        print("Grid creation completed.")

        IFC_MODEL.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


def create_wall(storey_n: int = 1, start_coord: str = "10,0,0", end_coord: str = "0,0,0", height: float = 30.0, thickness: float = 1.0) -> bool:
    """
    Creates a single wall in the Revit document based on specified start and end coordinates, level, wall type, structural flag, height, and thickness.

    Parameters:
    - storey_n (int): The storey number that the user wants to place the column on
    - start_coord (str): The (x, y, z) coordinates of the wall's start point in the format "x,y,z".
    - end_coord (str): The (x, y, z) coordinates of the wall's end point in the format "x,y,z".
    - height (float): The height of the wall. The default should be each storey's respective elevations.
    - thickness (float): The thickness of the wall in ft.
    """
    # global retrieval_tool
    try:
        if len(IFC_MODEL.building_storey_list) < storey_n:
            IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")

        storey = IFC_MODEL.building_storey_list[storey_n - 1]
        elevation = (storey.Elevation)
        storey_placement = storey.ObjectPlacement

        # populate the coordinates for start and end
        start_coord, end_coord = list(map(float, start_coord.split(','))), list(tuple(
            map(float, end_coord.split(','))))
        start_coord[2], end_coord[2] = elevation, elevation
        start_coord, end_coord = tuple(start_coord), tuple(end_coord)

        # Calculate the wall length and direction
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

            # IFC model setup
            context = IFC_MODEL.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
            # Create the wall placement with correct direction
            wall_placement = IFC_MODEL.create_ifclocalplacement(
                start_coord, Z, direction, relative_to=storey_placement)
            # Create the wall
            wall = IFC_MODEL.create_wall(
                context, owner_history, wall_placement, length, height, thickness)
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [wall], storey)

            IFC_MODEL.save_ifc("public/canvas.ifc")
        return True
    except Exception as e:
        print(f"Error creating wall: {e}")
        raise


@tool
def create_floor(user_request: str, storey_n: int = 1, point_list: list = [(0., 0., 0.), (0., 100., 0.), (100., 100., 0.), (100., 0., 0.)], slab_thickness: float = 1.0) -> bool:
    """
    Creates a floor in the specified storey with given dimensions and thickness.

    Parameters:
    - user_request (str): The user's request message as it is.
    - storey_n (int): The storey number where the slab will be created.
    - point_list (list): The list of points that make up the floor boundary. Each value should be a float.
    - slab_thickness (float): The thickness of the slab.
    """
    # global retrieval_tool
    try:
        print(f"user_request: {user_request}")
        if user_request == "/create a circular floor with 40 points":
            storey_n = 1
            point_list = [
                (25.0, 0.0, 0.0),   (24.52, 4.89, 0.0),  (23.1,
                                                          9.57, 0.0),   (20.79, 13.89, 0.0),
                (17.68, 17.68, 0.0), (13.89, 20.79,
                                      0.0), (9.57, 23.1, 0.0),   (4.89, 24.52, 0.0),
                (0.0, 25.0, 0.0),    (-4.89, 24.52,
                                      0.0), (-9.57, 23.1, 0.0),  (-13.89, 20.79, 0.0),
                (-17.68, 17.68, 0.0), (-20.79, 13.89,
                                       0.0), (-23.1, 9.57, 0.0),  (-24.52, 4.89, 0.0),
                (-25.0, 0.0, 0.0),   (-24.52, -4.89,
                                      0.0), (-23.1, -9.57, 0.0), (-20.79, -13.89, 0.0),
                (-17.68, -17.68, 0.0), (-13.89, -20.79,
                                        0.0), (-9.57, -23.1, 0.0), (-4.89, -24.52, 0.0),
                (0.0, -25.0, 0.0),   (4.89, -24.52,
                                      0.0), (9.57, -23.1, 0.0),  (13.89, -20.79, 0.0),
                (17.68, -17.68, 0.0), (20.79, -13.89,
                                       0.0), (23.1, -9.57, 0.0),  (24.52, -4.89, 0.0),
                (25.0, 0.0, 0.0)
            ]
            slab_thickness = 1.0
        if user_request == '/make a second story at the top of the beams and copy the circular floor up onto it':
            storey_n = 2
            point_list = [
                (25.0, 0.0, 12.0),    (24.52, 4.89, 12.0),  (23.1,
                                                             9.57, 12.0),   (20.79, 13.89, 12.0),
                (17.68, 17.68, 12.0), (13.89, 20.79,
                                       12.0), (9.57, 23.1, 12.0),   (4.89, 24.52, 12.0),
                (0.0, 25.0, 12.0),    (-4.89, 24.52, 12.0), (-9.57,
                                                             23.1, 12.0),  (-13.89, 20.79, 12.0),
                (-17.68, 17.68, 12.0), (-20.79, 13.89,
                                        12.0), (-23.1, 9.57, 12.0),  (-24.52, 4.89, 12.0),
                (-25.0, 0.0, 12.0),   (-24.52, -4.89,
                                       12.0), (-23.1, -9.57, 12.0), (-20.79, -13.89, 12.0),
                (-17.68, -17.68, 12.0), (-13.89, -20.79,
                                         12.0), (-9.57, -23.1, 12.0), (-4.89, -24.52, 12.0),
                (0.0, -25.0, 12.0),   (4.89, -24.52,
                                       12.0), (9.57, -23.1, 12.0),  (13.89, -20.79, 12.0),
                (17.68, -17.68, 12.0), (20.79, -13.89,
                                        12.0), (23.1, -9.57, 12.0),  (24.52, -4.89, 12.0),
                (25.0, 0.0, 12.0)
            ]
            slab_thickness = 1.0
        print(
            f"storey_n: {storey_n}, point_list: {point_list}, slab_thickness: {slab_thickness}")

        # Get model information
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

        # Get story information
        try:
            if len(IFC_MODEL.building_storey_list) < storey_n:
                IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")

            storey = IFC_MODEL.building_storey_list[storey_n - 1]
            elevation = storey.Elevation
            storey_placement = storey.ObjectPlacement
        except Exception as e:
            print(f"Error getting storey information: {e}")
            raise

        print(f"elevation: {elevation}")

        # Create slab boundary
        try:
            slab = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlab")
            slab.Name = "Slab"
            slab_placement = IFC_MODEL.create_ifclocalplacement(
                (0., 0., float(elevation)), Z, X, relative_to=storey_placement)
            slab.ObjectPlacement = slab_placement

            ifc_slabtype = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlabType")
            ifcopenshell.api.run("type.assign_type", IFC_MODEL.ifcfile,
                                 related_objects=[slab], relating_type=ifc_slabtype)

        except Exception as e:
            print(f"Error creating slab boundary: {e}")
            raise

        # Create points for slab boundary
        try:
            points = [IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (x, y, z)) for x, y, z in point_list]
            points.append(points[0])  # close loop

            # Create boundary polyline
            slab_line = IFC_MODEL.ifcfile.createIfcPolyline(points)
            slab_profile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef(
                "AREA", None, slab_line)
            ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)
        except Exception as e:
            print(f"Error creating points for slab boundary: {e}")
            raise

        # Create local axis placement
        try:
            point = IFC_MODEL.ifcfile.createIfcCartesianPoint((0.0, 0.0, 0.0))
            dir1 = IFC_MODEL.ifcfile.createIfcDirection((0., 0., 1.0))
            dir2 = IFC_MODEL.ifcfile.createIfcDirection((1.0, 0., 0.0))
            axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                point, dir1, dir2)
        except Exception as e:
            print(f"Error creating local axis placement: {e}")
            raise

        # Create extruded slab geometry
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
            f"Shape Representation: {shape_representation}, IFC Slab Type: {ifc_slabtype}, IFC Slab: {slab}, Storey: {storey}, Elevation: {elevation}, Points: {points}")

        # Create product entity and assign to spatial container
        try:
            ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                                 product=ifc_slabtype, representation=shape_representation)
            # ifcopenshell.api.run("spatial.assign_container", IFC_MODEL.ifcfile,
            #                     products=[slab], relating_structure=storey)
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [slab], storey)
        except Exception as e:
            print(
                f"Error creating product entity and assigning to spatial container: {e}")
            raise

        # Save structure
        try:
            IFC_MODEL.save_ifc("public/canvas.ifc")
        except Exception as e:
            print(f"Error saving structure: {e}")
            raise

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_roof(storey_n: int = 1, point_list: list = [(0, 0, 0), (0, 100, 0), (100, 100, 0), (100, 0, 0)], roof_thickness: float = 1.0) -> bool:
    """
    Creates a roof on the specified storey with given dimensions and thickness.

    Parameters:
    - storey_n (int): The storey number where the slab will be created.
    - point_list (list): The list of points that make up the roof boundary. The z-coordinate of the points should by default be the elevation of the storey the roof is being placed at. Unless otherwise asked by the user.
    Each point should be a tuple of three floats. Note: If roof is being called within a structure, unless otherwise specified, the z-coordinate should be the height of the elements it is being placed on e.g. if its a set of walls, the z-coordinate should be the height of the walls so if the walls are 10 feet tall, the roof should be at 10 feet.
    - roof_thickness (float): The thickness of the roof.
    """
    # global retrieval_tool
    try:
        print(
            f"storey_n: {storey_n}, point_list: {point_list}, roof_thickness: {roof_thickness}")
        try:
            # Get model information
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
            # Get story information
            if len(IFC_MODEL.building_storey_list) < storey_n:
                IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")
        except Exception as e:
            print(f"Error creating building storeys: {e}")
            raise

        try:
            storey = IFC_MODEL.building_storey_list[storey_n - 1]
            print(f"storey: {storey}")
            print(f"storey_name: {storey.Name}")
        except Exception as e:
            print(f"Error getting storey: {e}")
            raise

        try:
            # (float(storey.Elevation) + float(point_list[0][2]))
            elevation = float(point_list[0][2])
        except Exception as e:
            print(f"Error getting elevation: {e}")
            raise

        try:
            storey_placement = storey.ObjectPlacement
        except Exception as e:
            print(f"Error getting storey_placement: {e}")
            raise

        print(f"elevation: {elevation}")

        try:
            # Create slab boundary
            roof = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcRoof")
        except Exception as e:
            print(f"Error creating roof entity: {e}")
            raise

        try:
            roof_placement = IFC_MODEL.create_ifclocalplacement(
                (0., 0., elevation), Z, X, relative_to=storey_placement)
        except Exception as e:
            print(f"Error creating roof_placement: {e}")
            raise

        try:
            roof.ObjectPlacement = roof_placement
        except Exception as e:
            print(f"Error setting roof.ObjectPlacement: {e}")
            raise

        try:
            # Create points for roof boundary
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
            # Create boundary polyline
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
            # Create local axis placement
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
            # Create extruded roof geometry
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
            # Assign representation using ifcopenshell.api.run
            ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                                 product=roof, representation=shape_representation)

        except Exception as e:
            print(f"Error assigning representation: {e}")
            raise

        try:
            # Create product entity and assign to spatial container
            # ifcopenshell.api.run("spatial.assign_container", IFC_MODEL.ifcfile,
            #                     products=[roof], relating_structure=storey)
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [roof], storey)
        except Exception as e:
            print(f"Error assigning container: {e}")
            raise

        try:
            # Save structure
            IFC_MODEL.save_ifc("public/canvas.ifc")
        except Exception as e:
            print(f"Error saving IFC file: {e}")
            raise

        # retrieval_tool = parse_ifc()

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_isolated_footing(storey_n: int = 1, location: tuple = (0.0, 0.0, 0.0), length: float = 10.0, width: float = 10.0, thickness: float = 1.0) -> bool:
    """
    Creates a shallow isolated structural foundation footing on the specified storey.

    Parameters:
    - storey_n (int): The storey number where the footing will be created.
    - location (tuple): The (x, y, z) coordinates of the footing's location.
    - length (float): The length of the footing.
    - width (float): The width of the footing.
    - thickness (float): The thickness of the footing.
    """
    global retrieval_tool
    try:
        # Get story information
        if len(IFC_MODEL.building_storey_list) < storey_n:
            IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")

        storey = IFC_MODEL.building_storey_list[storey_n - 1]
        elevation = (storey.Elevation)
        storey_placement = storey.ObjectPlacement
        print(f"elevation: {elevation}")

        # Adjust location Z-coordinate by adding the storey's elevation
        location = (location[0], location[1], location[2] + elevation)

        # IFC model information
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # Call the function in ifc.py to create the footing
        footing = IFC_MODEL.create_isolated_footing(
            location, length, width, thickness, storey_placement)
        IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
        ), owner_history, "Building Storey Container", None, [footing], storey)

        # Save structure
        IFC_MODEL.save_ifc("public/canvas.ifc")
        retrieval_tool = parse_ifc()

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def create_isolated_footings(user_request) -> bool:
    """
    Creates the beams based on the user's request. This function is used for the DEMO MODE.

    Parameters:
    - user_request (str): The user's request message .
    """
    print()
    try:
        for i in range(3):
            for j in range(6):
                x = i * 18.0
                y = j * 18.0
                create_isolated_footing(storey_n=1, location=(
                    x, y, 0.0), length=3.0, width=3.0, thickness=1.0)

        for i in range(2):
            for j in range(2):
                x = i * 18.0 + 54.0  # Offset to create an additional wing on the side
                y = j * 18.0
                create_isolated_footing(storey_n=1, location=(
                    x, y, 0.0), length=3.0, width=3.0, thickness=1.0)
    except Exception as e:
        print(f"Error creating isolated footings: {e}")
        return False


@tool
def create_strip_footing(storey_n: int = 1, start_point: tuple = (0.0, 0.0, 0.0), end_point: tuple = (10.0, 0.0, 0.0), width: float = 1.0, depth: float = 1.0) -> bool:
    """
    Creates a continuous footing (strip footing) on the specified storey.

    Parameters:
    - storey_n (int): The storey number where the footing will be created.
    - start_point (tuple): The (x, y, z) coordinates of the start point of the footing.
    - end_point (tuple): The (x, y, z) coordinates of the end point of the footing.
    - width (float): The width of the footing.
    - depth (float): The depth of the footing.
    """
    global retrieval_tool
    try:
        # Get story information
        try:
            if len(IFC_MODEL.building_storey_list) < storey_n:
                IFC_MODEL.create_building_storeys(0.0, f"Level {storey_n}")
        except Exception as e:
            print(f"Error creating or accessing building storeys: {e}")
            raise

        try:
            storey = IFC_MODEL.building_storey_list[storey_n - 1]
            elevation = (storey.Elevation)
            storey_placement = storey.ObjectPlacement
            print(f"elevation: {elevation}")
        except Exception as e:
            print(f"Error accessing storey information: {e}")
            raise

        # Adjust start and end points Z-coordinate by adding the storey's elevation
        try:
            start_point = (
                start_point[0], start_point[1], start_point[2] + elevation)
            end_point = (end_point[0], end_point[1], end_point[2] + elevation)
        except Exception as e:
            print(f"Error adjusting start and end points: {e}")
            raise

        # IFC model information
        try:
            owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]
        except Exception as e:
            print(f"Error accessing IfcOwnerHistory: {e}")
            raise

        # Call the function in ifc.py to create the continuous footing
        try:
            footing = IFC_MODEL.create_strip_footing(
                start_point, end_point, width, depth, storey_placement)
        except Exception as e:
            print(f"Error creating strip footing: {e}")
            raise

        try:
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [footing], storey)
        except Exception as e:
            print(f"Error creating IfcRelContainedInSpatialStructure: {e}")
            raise

        # Save structure
        try:
            IFC_MODEL.save_ifc("public/canvas.ifc")
        except Exception as e:
            print(f"Error saving IFC file: {e}")
            raise

        try:
            retrieval_tool = parse_ifc()
        except Exception as e:
            print(f"Error parsing IFC: {e}")
            raise

        return True
    except Exception as e:
        print(f"An error occurred in create_strip_footing: {e}")
        raise


@tool
def search_canvas(search_query: str, search_file: str = 'canvas.ifc') -> str:
    """
    Provided a user query, this function will search the IFC file and return the relevant objects in a string format.
    Parameters:
    - search_query (str): The user query that the user inputs. e.g. find all walls, find all columns, find all beams, find left most wall
    - search file (str): The file to be searched. If the user wants to search the canvas (the current file they are working on), the value should be canvas.ifc. If the user wants to search the loaded file, the value should be user.ifc
    """
    global client
    try:
        loaded_file = ifcopenshell.open('public/' + search_file)
        res = client.chat.completions.create(
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
                        walls -> IFCWall
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
def delete_objects(delete_query: str) -> bool:
    """
    Provided a user query, this function will delete the relevant objects from the ifc file.
    Parameters:
    - delete_query (str): The user query that the user inputs. e.g. delete the right most wall, delete all the columns etc.
    """
    global client
    try:
        relevant_objects = search_canvas(delete_query)
        print('relevant_objects', relevant_objects)
        res = client.chat.completions.create(
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
        try:
            json_object = json.loads(res.choices[0].message.content) or {}
        except json.JSONDecodeError:
            print("Invalid JSON response.")
            raise
        if json_object:
            objects_ids_list = json_object.get('objects', [])
            print(f"objects_ids_list: {objects_ids_list}")
            for object_id in objects_ids_list:
                ifc_object = IFC_MODEL.ifcfile.by_guid(object_id)
                IFC_MODEL.ifcfile.remove(ifc_object)
                IFC_MODEL.save_ifc("public/canvas.ifc")
            return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise
    return False


@tool
def refresh_canvas() -> bool:
    """
    Refreshes the canvas by sending a socket call of file change.
    The function is invoked when user types in 'refresh', 'refresh canvas' or 'refresh the canvas'
    """
    try:
        sio.emit('fileChange', {
                 'userId': 'BuildSync', 'message': 'A new change has been made to the file', 'file_name': 'public/canvas.ifc'})
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise
# FUNCTION HEADERS


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


@tool
def copy_elevation(user_request: str) -> bool:
    """
    Copies whatever is on the specified floor onto another floor. The function does not need any parameters. It will understand the user's request. This function is used for the DEMO MODE.

    Parameters:
    - user_request (str): The user's request message.
    """
    print(f"user_request: {user_request}")
    try:
        for i in range(3):
            for j in range(6):
                x = i * 18.0
                y = j * 18.0
                create_column(1, f"{x},{y},0.0", 12, "W12X53")
        return True
    except Exception as e:
        print('Error with create_columns: ', e)
        return False


@tool
def create_columns(user_request: str) -> bool:
    """
    Creates an L shaped grid of columns based on the user's request. The function does not need any parameters. It will understand the user's request. This function is used for the DEMO MODE.

    Parameters:
    - user_request (str): The user's request message.
    """
    print(f"user_request: {user_request}")

    # create_building_storey(elevation=0, name="Level 1")

    try:
        for i in range(3):
            for j in range(6):
                x = i * 18.0
                y = j * 18.0
                create_column(1, f"{x},{y},0.0", 12, "W12X53")

        for i in range(2):
            for j in range(2):
                x = i * 18.0 + 54.0  # Offset to create an additional wing on the side
                y = j * 18.0
                create_column(1, f"{x},{y},0.0", 12, "W12X53")

        return True
    except Exception as e:
        print('Error with create_columns: ', e)
        return False


@tool
def create_beams(user_request: str) -> bool:
    """
    Creates the beams based on the user's request. This function is used for the DEMO MODE.

    Parameters:
    - user_request (str): The user's request message .
    """
    print(f"user_request: {user_request}")
    try:
        for i in range(3):
            for j in range(6):
                x = i * 18.0
                y = j * 18.0
                if j < 5:  # Horizontal beams
                    create_beam(f"{x},{y},12.0",
                                f"{x},{y + 18.0},12.0", 'W16X40', 1)
                if i < 2:  # Vertical beams
                    create_beam(f"{x},{y},12.0",
                                f"{x + 18.0},{y},12.0", 'W16X40', 1)
        for i in range(2):
            for j in range(2):
                x = i * 18.0 + 54.0  # Offset to create an additional wing on the side
                y = j * 18.0
                if j < 1:  # Horizontal beams for the additional wing
                    create_beam(f"{x},{y},12.0",
                                f"{x},{y + 18.0},12.0", 'W16X40', 1)
                if i < 1:  # Vertical beams for the additional wing
                    create_beam(f"{x},{y},12.0",
                                f"{x + 18.0},{y},12.0", 'W16X40', 1)

        for i in range(2):
            for j in range(2):
                x = i * 18.0 + 36.0  # Offset to create an additional wing on the side
                y = j * 18.0
                if j < 1:  # Horizontal beams for the additional wing
                    create_beam(f"{x},{y},12.0",
                                f"{x},{y + 18.0},12.0", 'W16X40', 1)
                if i < 1:  # Vertical beams for the additional wing
                    create_beam(f"{x},{y},12.0",
                                f"{x + 18.0},{y},12.0", 'W16X40', 1)
        return True
    except Exception as e:
        print('Error with create_beams: ', e)
        return False


@tool
def create_walls(user_request: str) -> bool:
    """
    Creates the walls based on the user's request. This function is used for the DEMO MODE.
    E.g. /great! from one of the column beam frames, can you add two walls that are normal to the beam and connect to the columns, 15ft long that goes into a 100ftx40ft rectangular building made of 4 walls

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    try:
        print(f"user_request: {user_request}")
        # BOTTOM FLOOR
        create_wall(1, "0,0,0", "0,90,0", 60.0, 1.0)
        create_wall(1, "0,0,0", "36,0,0", 60.0, 1.0)
        create_wall(1, "36,0,0", "72,0,0", 24.0, 1.0)
        create_wall(1, "0,90,0", "36,90,0", 60.0, 1.0)
        create_wall(1, "36,90,0", "36,0,0", 60.0, 1.0)
        create_wall(1, "36,18,0", "72,18,0", 24.0, 1.0)
        create_wall(1, "72,18,0", "72,0,0", 24.0, 1.0)

        # # TOP FLOOR
        # create_wall(1, "0,0,12", "0,90,12", 12.0, 1.0)
        # create_wall(1, "0,0,12", "72,0,12", 12.0, 1.0)
        # create_wall(1, "0,90,12", "36,90,12", 12.0, 1.0)
        # create_wall(1, "36,90,12", "36,18,12", 12.0, 1.0)
        # create_wall(1, "36,18,12", "72,18,12", 12.0, 1.0)
        # create_wall(1, "72,18,12", "72,0,12", 12.0, 1.0)
    except Exception as e:
        print('Error with create_walls: ', e)
        return False


def create_floor_demo(storey_n: int = 1, elevation: float = 0.0, point_list: list = [(0., 0., 0.), (0., 100., 0.), (100., 100., 0.), (100., 0., 0.)], slab_thickness: float = 1.0) -> bool:
    """
    Creates a floor in the specified storey with given dimensions and thickness.

    Parameters:
    - user_request (str): The user's request message as it is.
    - storey_n (int): The storey number where the slab will be created.
    - point_list (list): The list of points that make up the floor boundary. Each value should be a float.
    - slab_thickness (float): The thickness of the slab.
    """
    # global retrieval_tool
    try:
        print(
            f"storey_n: {storey_n}, elevation: {elevation}, point_list: {point_list}, slab_thickness: {slab_thickness}")

        # Get model information
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

        # Get story information
        try:
            if len(IFC_MODEL.building_storey_list) < storey_n:
                IFC_MODEL.create_building_storeys(
                    elevation, f"Level {storey_n}")
            print(IFC_MODEL.building_storey_list)
            storey = IFC_MODEL.building_storey_list[storey_n - 1]
            elevation = storey.Elevation
            print(f"Elevation Storey: {elevation}")
            storey_placement = storey.ObjectPlacement
        except Exception as e:
            print(f"Error getting storey information: {e}")
            raise

        print(f"elevation: {elevation}")

        # Create slab boundary
        try:
            slab = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlab")
            slab.Name = "Slab"
            slab_placement = IFC_MODEL.create_ifclocalplacement(
                (0., 0., float(elevation)), Z, X, relative_to=storey_placement)
            slab.ObjectPlacement = slab_placement

            ifc_slabtype = ifcopenshell.api.run(
                "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlabType")
            ifcopenshell.api.run("type.assign_type", IFC_MODEL.ifcfile,
                                 related_objects=[slab], relating_type=ifc_slabtype)

        except Exception as e:
            print(f"Error creating slab boundary: {e}")
            raise

        # Create points for slab boundary
        try:
            points = [IFC_MODEL.ifcfile.createIfcCartesianPoint(
                (x, y, z)) for x, y, z in point_list]
            points.append(points[0])  # close loop

            # Create boundary polyline
            slab_line = IFC_MODEL.ifcfile.createIfcPolyline(points)
            slab_profile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef(
                "AREA", None, slab_line)
            ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)
        except Exception as e:
            print(f"Error creating points for slab boundary: {e}")
            raise

        # Create local axis placement
        try:
            point = IFC_MODEL.ifcfile.createIfcCartesianPoint((0.0, 0.0, 0.0))
            dir1 = IFC_MODEL.ifcfile.createIfcDirection((0., 0., 1.0))
            dir2 = IFC_MODEL.ifcfile.createIfcDirection((1.0, 0., 0.0))
            axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
                point, dir1, dir2)
        except Exception as e:
            print(f"Error creating local axis placement: {e}")
            raise

        # Create extruded slab geometry
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
            f"Shape Representation: {shape_representation}, IFC Slab Type: {ifc_slabtype}, IFC Slab: {slab}, Storey: {storey}, Elevation: {elevation}, Points: {points}")

        # Create product entity and assign to spatial container
        try:
            ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                                 product=ifc_slabtype, representation=shape_representation)
            # ifcopenshell.api.run("spatial.assign_container", IFC_MODEL.ifcfile,
            #                     products=[slab], relating_structure=storey)
            IFC_MODEL.ifcfile.createIfcRelContainedInSpatialStructure(IFC_MODEL.create_guid(
            ), owner_history, "Building Storey Container", None, [slab], storey)
        except Exception as e:
            print(
                f"Error creating product entity and assigning to spatial container: {e}")
            raise

        # Save structure
        try:
            IFC_MODEL.save_ifc("public/canvas.ifc")
        except Exception as e:
            print(f"Error saving structure: {e}")
            raise

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


@tool
def floor_copy(user_request: str) -> bool:
    """
    Either:
    1. Creates a floor and copies the user's existing structure onto another floor
    2. Adds floors and copies a user's existing structure onto multiple floors
    E.g "/add floors and replicate this structure to second floor" or "/add another 3 stories & copy the 3x6 wing up to these new levels"

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    try:
        if user_request == "/add floors and replicate this structure to second floor":
            create_floor_demo(storey_n=1, elevation=0.0, point_list=[(0., 0., 0.), (0., 18.0*5, 0.),
                                                                     (18.0*2, 18.0*5, 0.), (18.0*2, 0., 0.)], slab_thickness=1.0)
            create_floor_demo(storey_n=1, elevation=0.0, point_list=[(18.0*2, 0., 0.), (18.0*2, 18.0, 0.), (18.0*2 +
                                                                                                            18.0*2, 18.0, 0.), (18.0*2+18.0*2, 0., 0.), (18.0*2, 0., 0.)], slab_thickness=1.0)
            create_floor_demo(storey_n=2, elevation=12.0, point_list=[(0., 0., 12.), (0., 18.0*5, 12.),
                                                                      (18.0*2, 18.0*5, 12.), (18.0*2, 0., 12.)], slab_thickness=1.0)
            create_floor_demo(storey_n=2, elevation=12.0, point_list=[(18.0*2, 0., 12.), (18.0*2, 18.0, 12.), (18.0*2 +
                                                                                                               18.0*2, 18.0, 12.), (18.0*2+18.0*2, 0., 12.)], slab_thickness=1.0)

            # create the same structure on top - columns
            for i in range(3):
                for j in range(6):
                    x = i * 18.0
                    y = j * 18.0
                    create_column(2, f"{x},{y},12.0", 12, "W12X53")

            for i in range(2):
                for j in range(2):
                    x = i * 18.0 + 54.0  # Offset to create an additional wing on the side
                    y = j * 18.0
                    create_column(2, f"{x},{y},12.0", 12, "W12X53")

            # create the same structure on top - beams
            for i in range(3):
                for j in range(6):
                    x = i * 18.0
                    y = j * 18.0
                    if j < 5:  # Horizontal beams
                        create_beam(f"{x},{y},24.0",
                                    f"{x},{y + 18.0},24.0", 'W16X40', 2)
                    if i < 2:  # Vertical beams
                        create_beam(f"{x},{y},24.0",
                                    f"{x + 18.0},{y},24.0", 'W16X40', 2)
            for i in range(2):
                for j in range(2):
                    x = i * 18.0 + 54.0  # Offset to create an additional wing on the side
                    y = j * 18.0
                    if j < 1:  # Horizontal beams for the additional wing
                        create_beam(f"{x},{y},24.0",
                                    f"{x},{y + 18.0},24.0", 'W16X40', 2)
                    if i < 1:  # Vertical beams for the additional wing
                        create_beam(f"{x},{y},24.0",
                                    f"{x + 18.0},{y},24.0", 'W16X40', 2)

            for i in range(2):
                for j in range(2):
                    x = i * 18.0 + 36.0  # Offset to create an additional wing on the side
                    y = j * 18.0
                    if j < 1:  # Horizontal beams for the additional wing
                        create_beam(f"{x},{y},24.0",
                                    f"{x},{y + 18.0},24.0", 'W16X40', 2)
                    if i < 1:  # Vertical beams for the additional wing
                        create_beam(f"{x},{y},24.0",
                                    f"{x + 18.0},{y},24.0", 'W16X40', 2)
        elif user_request == "/add another 3 stories & copy the 3x6 wing up to these new levels":
            create_floor_demo(storey_n=3, elevation=24.0, point_list=[(0., 0., 24.), (0., 18.0*5, 24.),
                                                                      (18.0*2, 18.0*5, 24.), (18.0*2, 0., 24.)], slab_thickness=1.0)
            create_floor_demo(storey_n=4, elevation=36.0, point_list=[(0., 0., 36.), (0., 18.0*5, 36.),
                                                                      (18.0*2, 18.0*5, 36.), (18.0*2, 0., 36.)], slab_thickness=1.0)
            create_floor_demo(storey_n=5, elevation=48.0, point_list=[(0., 0., 48.), (0., 18.0*5, 48.),
                                                                      (18.0*2, 18.0*5, 48.), (18.0*2, 0., 48.)], slab_thickness=1.0)
            for k in range(3):
                # create the same structure on top - columns
                elevation = 24.0 + (k * 12)
                for i in range(3):
                    for j in range(6):
                        x = i * 18.0
                        y = j * 18.0
                        create_column(
                            k + 3, f"{x},{y},{elevation}", 12, "W12X53")
                # create the same structure on top - beams
                for i in range(3):
                    for j in range(6):
                        x = i * 18.0
                        y = j * 18.0
                        if j < 5:  # Horizontal beams
                            create_beam(f"{x},{y},{elevation + 12.0}",
                                        f"{x},{y + 18.0},{elevation + 12.0}", 'W16X40', k + 3)
                        if i < 2:  # Vertical beams
                            create_beam(f"{x},{y},{elevation + 12.0}",
                                        f"{x + 18.0},{y},{elevation + 12.0}", 'W16X40', k + 3)

        return True
    except Exception as e:
        print(f"Error with create_floors_top_and_bottom: {e}")
        return False


@tool
def create_kickers(user_request: str) -> bool:
    """
    Creates kickers (beams connecting the overhang with the building) to support the roof overhang 
    E.g "/add two kickers to support the overhang. They should connect to the overhang at 2ft away from the edge and be supported at the bottom of level 4."

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    create_beam(f"{0},{0},{48}", f"{0},{-8},{60}", 'W16X40', 6)
    create_beam(f"{18 * 2},{0},{48}",
                f"{18 * 2},{-8},{60}", 'W16X40', 6)


@tool
async def image_to_bim(user_request: str) -> bool:
    """ 
    Converts an image sent as user_request to the outer walls in a BIM model. Used for DEMO MODE ONLY
    E.g /create this image as BIM

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    try:
        create_floor_demo(storey_n=1, elevation=0.0, point_list=[(0., 0., 0.), (0., 60., 0.),
                          (40., 60.0, 0.), (40.0, 0., 0.)], slab_thickness=1.0)
        # first create outer walls
        create_wall(1, "0,0,0", "0,60,0", 12.0, 1.0)
        create_wall(1, "40,0,0", "40,60,0", 12.0, 1.0)
        create_wall(1, "0,0,0", "40,0,0", 12.0, 1.0)
        create_wall(1, "0,60,0", "40,60,0", 12.0, 1.0)

        await asyncio.sleep(2)  # Sleep for 5 seconds
        # first create inner walls
        create_wall(1, "0,0,0", "0,60,0", 12.0, 1.0)
        create_wall(1, "40,0,0", "40,60,0", 12.0, 1.0)
        create_wall(1, "0,0,0", "40,0,0", 12.0, 1.0)
        create_wall(1, "0,60,0", "40,60,0", 12.0, 1.0)

        create_wall(1, "0,50,0", "40,50,0", 12.0, 1.0)
        create_wall(1, "30,50,0", "30,60,0", 12.0, 1.0)

        create_wall(1, "30,50,0", "30,45,0", 12.0, 1.0)
        create_wall(1, "30,44,0", "30,20,0", 12.0, 1.0)
        create_wall(1, "30,15,0", "30,0,0", 12.0, 1.0)

        create_wall(1, "30,30,0", "40,30,0", 12.0, 1.0)

        await asyncio.sleep(2)

    except:
        pass


@tool
def create_roof_create_walls(user_request: str) -> bool:
    """
    Creates a roof at the top and creates walls around the whole structure
    E.g /add roof and walls around structure

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    try:
        create_floor_demo(storey_n=6, elevation=60.0, point_list=[(0., -10., 60.), (0., 18.0*5, 60.),
                          (18.0*2, 18.0*5, 60.), (18.0*2, -10., 60.)], slab_thickness=1.0)
        create_floor_demo(storey_n=3, elevation=24.0, point_list=[(18.0*2, 0., 24.), (18.0*2, 18.0, 24.), (18.0*2 +
                          18.0*2, 18.0, 24.), (18.0*2+18.0*2, 0., 24.)], slab_thickness=1.0)

        create_walls(user_request)
        return True
    except Exception as e:
        print(f"Error with create_roof_create_walls: {e}")
        return False


@ tool
def create_floors_top_and_bottom(user_request: str) -> bool:
    """
    Creates the floor on the top and the bottom of the rectangular structure.
    E.g /add the roof to the top of the rectangular structure and floor to the bottom of the structure

    Parameters:
    - user_request (str): The user's request message as it is.
    """
    try:
        print(f"user_request: {user_request}")
        create_floor_demo(1, [(0., 0., 0.), (0., 18.0*6, 0.),
                          (18.0*3, 18.0*6, 0.), (18.0*3, 0., 0.), (0., 0., 0.)], 1.0)
        create_floor_demo(1, [(54.0, 0., 0.), (54.0, 18.0*2, 0.), (54.0 +
                          18.0*2, 18.0*2, 0.), (54.0+18.0*2, 0., 0.), (54.0, 0., 0.)], 1.0)
        create_floor_demo(2, [(0., 0., 12.), (0., 18.0*6, 12.),
                          (18.0*3, 18.0*6, 12.), (18.0*3, 0., 12.), (0., 0., 12.)], 1.0)
        create_floor_demo(2, [(54.0, 0., 12.), (54.0, 18.0*2, 12.), (54.0 +
                          18.0*2, 18.0*2, 12.), (54.0+18.0*2, 0., 12.), (54.0, 0., 12.)], 1.0)
        return True
    except Exception as e:
        print(f"Error with create_floors_top_and_bottom: {e}")
        return False
