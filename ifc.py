import pandas as pd
import numpy as np
import math
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.api.material
import ifcopenshell.api.style
import ifcopenshell.api.context
import time
import tempfile
import ifcopenshell
import uuid
import sys
import pdb

print("version: ifc openshell", ifcopenshell.version)


O = 0., 0., 0.
X = 1., 0., 0.
Y = 0., 1., 0.
Z = 0., 0., 1.


class IfcModel:
    def __init__(self, creator, organization, application, application_version, project_name, filename=None):
        """
        Initializes the model based on the provided info.

        Parameters:
        - creator: the model's maker.
        - organization: who the creator wroks for.
        - application: the program that produced the model.
        - application_version: the specific iteration of the producing program.
        - project_name: the name of the model's project.
        - filename: the name of the file to store it in. Defaults to none.
        """
        # 1. Stores all the uncomplicated stuff.
        self.creator = creator
        self.organization = organization
        self.application = application
        self.application_version = application_version
        self.project_name = project_name
        self.timestamp = time.time()
        self.timestring = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.gmtime(self.timestamp))
        self.materials = dict()
        self.support_types = dict()
        self.steel_types = dict()
        self.object_types = dict()
        self.project_globalid = self.create_guid()
        # 2. If there is no file name provided, create a new file. anad store all the necessary info
        if filename is None:
            self.ifcfile = self.initialize_ifc()
            self.owner_history = self.ifcfile.by_type("IfcOwnerHistory")[0]
            self.site_placement = self.create_ifclocalplacement()
            self.site = self.ifcfile.createIfcSite(self.create_guid(
            ), self.owner_history, "Site", None, None, self.site_placement, None, None, "ELEMENT", None, None, None, None, None)
            self.building_placement = self.create_ifclocalplacement(
                relative_to=self.site_placement)
            self.building = self.ifcfile.createIfcBuilding(self.create_guid(
            ), self.owner_history, "Building", None, None, self.building_placement, None, None, "ELEMENT", None, None, None)
            self.story_placement = self.create_ifclocalplacement(
                relative_to=self.building_placement)
            self.building_story_list = []

            # 3. Create the world coordinate system.
            WorldCoordinateSystem = self.ifcfile.createIfcAxis2Placement3D()
            WorldCoordinateSystem.Location = self.ifcfile.createIfcCartesianPoint(
                O)
            WorldCoordinateSystem.Axis = self.ifcfile.createIfcDirection(Z)
            WorldCoordinateSystem.RefDirection = self.ifcfile.createIfcDirection(
                X)

            # 4. Define the context
            context = self.ifcfile.createIfcGeometricRepresentationContext()
            context.ContextType = "Model"
            context.CoordinateSpaceDimension = 3
            context.Precision = 1.e-05
            context.WorldCoordinateSystem = WorldCoordinateSystem
            # 5. Store the rest.
            self.footprint_context = self.ifcfile.createIfcGeometricRepresentationSubContext()
            self.footprint_context.ContextIdentifier = 'Footprint'
            self.footprint_context.ContextType = "Model"
            self.footprint_context.ParentContext = context
            self.footprint_context.TargetView = 'MODEL_VIEW'

        # 2. Otherwise open the existing file.
        else:
            self.ifcfile = ifcopenshell.open(filename)

        self.add_support_type("wood", 1, 0.5764705882, 0, self.get_rectangle)
        self.add_material("brick", 1, 0, 0)
        self.add_support_type("concrete", 0.662745098,
                              0.662745098, 0.662745098, self.get_rectangle)
        self.add_support_type("steel", 106 / 255, 127 /
                              255, 169 / 255, self.get_steel_shape_profile)
        # print("Support Types/Materials:", self.support_types, self.materials)
        self.support_types.setdefault(self.get_rectangle)
        self.steel_types["L"] = self.get_lshape_profile
        self.steel_types["C"] = self.get_cshape_profile
        self.steel_types["HSS"] = self.get_hss_profile
        self.steel_types["W"] = self.get_wshape_profile
        print(f"steel types done: {self.steel_types}")
        self.object_types["wall"] = "IfcWall"
        self.object_types['window'] = "IfcWindow"
        self.object_types['column'] = "IfcColumn"
        self.object_types['roof'] = "IfcRoof"
        self.object_types['building'] = 'IfcBuilding'
        self.object_types['door'] = 'IfcDoor'
        self.object_types['beam'] = 'IfcBeam'
        self.object_types['slab'] = 'IfcSlab'
        self.object_types['floor'] = 'IfcSlab'
        self.object_types['story'] = 'IfcBuildingStorey'

    def add_material(self, name, red, green, blue):
        style = ifcopenshell.api.style.add_style(self.ifcfile)
        material = ifcopenshell.api.material.add_material(self.ifcfile, name)
        ifcopenshell.api.style.add_surface_style(self.ifcfile, style=style, ifc_class="IfcSurfaceStyleShading", attributes={
            "SurfaceColour": {"Name": None, "Red": red, "Green": green, "Blue": blue}
        })
        self.materials[name] = (material, style)
        return self.materials[name]

    def add_support_type(self, name, red, green, blue, shaper):
        # print(f"""Name: {name}, Red: {red}, Green: {
        #       green}, Blue: {blue}, Shaper: {shaper}""")
        self.add_material(name, red, green, blue)
        self.support_types[name] = shaper

    def create_guid(self):
        """
        Create and return a unique identifier.
        """
        return ifcopenshell.guid.compress(uuid.uuid1().hex)

    def initialize_ifc(self):
        # A template IFC file to quickly populate entity instances for an IfcProject with its dependencies
        template = """ISO-10303-21;
        HEADER;
        FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
        FILE_NAME('%(filename)s','%(timestring)s',('%(creator)s'),('%(organization)s'),'%(application)s','%(application)s','');
        FILE_SCHEMA(('IFC2X3'));
        ENDSEC;
        DATA;
        #1=IFCPERSON($,$,'%(creator)s',$,$,$,$,$);
        #2=IFCORGANIZATION($,'%(organization)s',$,$,$);
        #3=IFCPERSONANDORGANIZATION(#1,#2,$);
        #4=IFCAPPLICATION(#2,'%(application_version)s','%(application)s','');
        #5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,#3,#4,%(timestamp)s);
        #6=IFCDIRECTION((1.,0.,0.));
        #7=IFCDIRECTION((0.,0.,1.));
        #8=IFCCARTESIANPOINT((0.,0.,0.));
        #9=IFCAXIS2PLACEMENT3D(#8,#7,#6);
        #10=IFCDIRECTION((0.,1.,0.));
        #11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#9,#10);
        #12=IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0);
        #13=IFCSIUNIT(*,.LENGTHUNIT.,$,.FEET.);
        #14=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_FEET.);
        #15=IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_FEET.);
        #16=IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.DEGREE.);
        #17=IFCMEASUREWITHUNIT(IFCPLANEANGLEMEASURE(0.017453292519943295),#16);
        #18=IFCCONVERSIONBASEDUNIT(#12,.PLANEANGLEUNIT.,'DEGREE',#17);
        #19=IFCUNITASSIGNMENT((#13,#14,#15,#18));
        #20=IFCPROJECT('%(project_globalid)s',#5,'%(project_name)s',$,$,$,$,(#11),#19);
        ENDSEC;
        END-ISO-10303-21;
        """ % {
            "filename": "temp.ifc",
            "timestring": self.timestring,
            "creator": self.creator,
            "organization": self.organization,
            "application": self.application,
            "application_version": self.application_version,
            "timestamp": self.timestamp,
            "project_globalid": self.project_globalid,
            "project_name": self.project_name
        }

        temp_handle, temp_filename = tempfile.mkstemp(suffix=".ifc")
        with open(temp_filename, "w") as f:
            f.write(template)

        ifcfile = ifcopenshell.open(temp_filename)
        return ifcfile

    def create_ifcaxis2placement(self, point=(0., 0., 0.), dir1=(0., 0., 1.), dir2=(1., 0., 0.)):
        """
        Creates and returns a given 2-axis placement based on a point and two directions.

        Parameters:
        - point: the center of the given placement. Defaults to origin.
        - dir1: the first 3D directional vector. Defaults to the z-unit vector.
        - dir2: the second 3D directional vector. Defaults to the x-unit vector.
        """
        # 1. Create the IFC file representations of the point and directions.
        point = self.ifcfile.createIfcCartesianPoint(point)
        dir1 = self.ifcfile.createIfcDirection(dir1)
        dir2 = self.ifcfile.createIfcDirection(dir2)
        # 2. Combine the representations and return them.
        axis2placement = self.ifcfile.createIfcAxis2Placement3D(
            point, dir1, dir2)
        return axis2placement

    def create_ifclocalplacement(self, point=(0., 0., 0.), dir1=(0., 0., 1.), dir2=(1., 0., 0.), relative_to=None):
        """
        Creates and returns a local placement based on a point, two directions, and a relative position.

        Parameters:
        - point: the point to be placed. Defaults to origin.
        - dir1: the first 3D directional vector. Defaults to the z-unit vector.
        - dir2: the second 3D directional vector. Defaults to the x-unit vector.
        - relative_to: the place which this is all in relation to. Defaults to none.
        """
        # 1. Create the placement without relation to anything else.
        axis2placement = self.create_ifcaxis2placement(point, dir1, dir2)
        # 2. Add the point to this is in relation to and returns it.
        ifclocalplacement = self.ifcfile.createIfcLocalPlacement(
            relative_to, axis2placement)
        return ifclocalplacement

    def create_ifcpolyline(self, point_list):
        """
        Creates and returns a piecewise line that connects all points inputted in order of placement in list.

        Parameters:
        - point_list: the points to be connected.
        """
        # 1. Creates the IFC representation of the point list.
        ifcpts = [self.ifcfile.createIfcCartesianPoint(
            point) for point in point_list]
        # 2. Creates the IFC file version of the line and returns it.
        polyline = self.ifcfile.createIfcPolyLine(ifcpts)
        return polyline

    def create_ifcextrudedareasolid(self, point_list, ifcaxis2placement, extrude_dir, extrusion):
        """
        Creates and returns a extruded solid based on the inputs provided.

        Parameters:
        - point_list: the list of points to be turned into an area.
        - ifcaxis2placemnt: the point to start on.
        - extrude_dir: the direction the extrusion should go in.
        - extrusion: the shape to create.
        """
        # 1. Create the area containing the solid.
        polyline = self.create_ifcpolyline(point_list)
        ifcclosedprofile = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline)
        # 2. Create the IFC representation of the extrusion direction.
        ifcdir = self.ifcfile.createIfcDirection(extrude_dir)
        # 3. Create and return the solid in its place
        ifcextrudedareasolid = self.ifcfile.createIfcExtrudedAreaSolid(
            ifcclosedprofile, ifcaxis2placement, ifcdir, extrusion)
        return ifcextrudedareasolid

    def create_building_stories(self, elevation, name):
        """
        Adds a story to the building based on elevation and the name.

        Parameters:
        - elevation: the height of the story.
        - name: the name of the story.
        """
        # 1. Creates the placement of the story.
        story_placement = self.create_ifclocalplacement(point=(0.0, 0.0, float(elevation)),
                                                        relative_to=self.building_placement)
        # 2. Creates the story and adds it to the list of storys.
        building_story = self.ifcfile.createIfcBuildingStorey(self.create_guid(), self.owner_history, str(
            name), None, None, story_placement, None, None, "ELEMENT", float(elevation))
        self.building_story_list.append(building_story)

    def create_wall(self, context, owner_history, wall_placement, length, height, thickness, material):
        """
        Creates and returns a single wall in the IFC model, based on placement, height, length, and thickness.

        Parameters:
        - context: the scene in which to place the wall in.
        - owner_history: what the wall belongs to.
        - wall_placement: where the wall is in the blueprints
        - length: the length of the wall.
        - height: how tall the wall is.
        - thickness: how wide the wall is.
        """
        # 1. Create polyline representing wall axis in 2D
        polyline = self.create_ifcpolyline(
            [(0.0, 0.0, 0.0), (length, 0.0, 0.0)])
        axis_rep = self.ifcfile.createIfcShapeRepresentation(
            context, "Axis", "Curve2D", [polyline])
        # 2. Create full 3D geometric representation
        # Define placement for extrusion operation
        extrusion_placement = self.create_ifcaxis2placement()
        # Define point list for extrusion (4 points for wall profile, 1 to close rectangle)
        point_list = [
            (0.0, -thickness/2, 0.0), (length, -thickness/2, 0.0),
            (length, thickness/2, 0.0), (0.0,
                                         thickness/2, 0.0), (0.0, -thickness/2, 0.0)
        ]
        # Create volume using point list, global axis, direction, and height
        solid = self.create_ifcextrudedareasolid(
            point_list, extrusion_placement, (0.0, 0.0, 1.0), height)
        # Create shape representation for volume
        body_rep = self.ifcfile.createIfcShapeRepresentation(
            context, "Body", "SweptSolid", [solid])

        # 3. Combine 2D simplification & 3D representation into 1 product
        product_shape = self.ifcfile.createIfcProductDefinitionShape(
            None, None, [axis_rep, body_rep])
        # 4. Create and return wall
        wall = self.ifcfile.createIfcWallStandardCase(self.create_guid(), owner_history, "Wall", None, None,
                                                      wall_placement, product_shape, None)
        self.add_style_to_product(material, wall)
        return wall

    def create_column(self, context, owner_history, column_placement, height, section_name, material):
        """
        Creates and returns a single column in the IFC model, based on placement and height.

        Parameters:
        - context: the scene in which to place the column in.
        - owner_history: what the column belongs to.
        - column_placement: where the column is.
        - height: how tall the column is.
        - section_name: the name of the section.
        """
        # 1. Create the column profile
        ifcclosedprofile = self.get_wshape_profile(section_name)
        # print('IFC Closed Profile: ', dir(ifcclosedprofile))
        ifcclosedprofile.ProfileName = section_name
        # 2. Create the 3D extrusion.
        extrusion_placement = self.create_ifcaxis2placement()
        ifcdir = self.ifcfile.createIfcDirection((0.0, 0.0, 1.0))
        solid = self.ifcfile.createIfcExtrudedAreaSolid(
            ifcclosedprofile, extrusion_placement, ifcdir, height)
        # 3. Create the shape representation.
        body_rep = self.ifcfile.createIfcShapeRepresentation(
            context, "Body", "SweptSolid", [solid])
        # 4. Create the product shape.
        product_shape = self.ifcfile.createIfcProductDefinitionShape(None, None, [
                                                                     body_rep])
        # 4. Create the final column and return it
        column = self.ifcfile.createIfcColumn(self.create_guid(
        ), owner_history, "W-Shaped Column", None, None, column_placement, product_shape, None)
        self.add_style_to_product(material, column)
        return column

    def create_beam(self, context, owner_history, beam_placement, length, section_name, material):
        """
        Creates and returns a single beam in the IFC model, based on placement and length.

        Parameters:
        - context: the scene in which to place the beam in.
        - owner_history: what the beam belongs to.
        - beam_placement: where the beam is.
        - length: how long the beam is.
        - section_name: the name of the section.
        """
        # 1. Create the beam profile
        point_list = self.get_wshape_points(section_name)

        # 2. Create extrusion
        extrusion_placement = self.create_ifcaxis2placement()
        # solid = self.create_ifcextrudedareasolid(
        #     point_list, extrusion_placement, (1.0, 0.0, 0.0), length)

        solid = self.create_ifcextrudedareasolid(
            point_list, extrusion_placement, (0.0, 1.0, 0.0), length)

        # 3. Create shape representation
        body_rep = self.ifcfile.createIfcShapeRepresentation(
            context, "Body", "SweptSolid", [solid])

        # 4. Create product shape
        product_shape = self.ifcfile.createIfcProductDefinitionShape(None, None, [
                                                                     body_rep])

        # 5. Create the beam and return it
        beam = self.ifcfile.createIfcBeam(self.create_guid(), owner_history, "Beam", None, None,
                                          beam_placement, product_shape, None)
        self.add_style_to_product(material, beam)
        return beam

    def create_isolated_footing(self, location: tuple, length: float, width: float, thickness: float) -> None:
        """
        Creates an IFC footing entity with the specified parameters.

        Parameters:
        - location (tuple): The (x, y, z) coordinates of the footing's location.
        - length (float): The length of the footing.
        - width (float): The width of the footing.
        - thickness (float): The thickness of the footing.
        """
        try:
            # Get geometric representation context (not the storey)
            context = self.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = self.ifcfile.by_type("IfcOwnerHistory")[0]

            # Create footing entity
            footing = self.ifcfile.create_entity("IfcFooting", GlobalId=self.create_guid(
            ), OwnerHistory=owner_history, Name="Isolated Footing", ObjectPlacement=None, Representation=None, Tag=None, PredefinedType="PAD_FOOTING")

            # Create local placement for the footing
            footing_placement = self.create_ifclocalplacement(location, Z, X)
            footing.ObjectPlacement = footing_placement

            # Create points for footing boundary with the center as the start point
            half_length = float(length / 2)
            half_width = float(width / 2)
            points = [
                self.ifcfile.createIfcCartesianPoint(
                    (-half_length, -half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (half_length, -half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (half_length, half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (half_length, half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (-half_length, half_width, 0.0))
            ]

            # Create boundary polyline
            footing_line = self.ifcfile.createIfcPolyline(Points=points)
            footing_profile = self.ifcfile.createIfcArbitraryClosedProfileDef(
                ProfileType="AREA", ProfileName=None, OuterCurve=footing_line)
            ifc_direction = self.ifcfile.createIfcDirection((0.0, 0.0, 1.0))

            # Create local axis placement
            point = self.ifcfile.createIfcCartesianPoint([0.0, 0.0, 0.0])
            dir1 = self.ifcfile.createIfcDirection((0.0, 0.0, 1.0))
            dir2 = self.ifcfile.createIfcDirection((1.0, 0.0, 0.0))
            axis2placement = self.ifcfile.createIfcAxis2Placement3D(
                Location=point, Axis=dir1, RefDirection=dir2)

            # Create extruded footing geometry
            extrusion = thickness
            footing_solid = self.ifcfile.create_entity(
                "IfcExtrudedAreaSolid", SweptArea=footing_profile, Position=axis2placement, ExtrudedDirection=ifc_direction, Depth=extrusion)
            shape_representation = self.ifcfile.create_entity(
                "IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier='Body', RepresentationType='SweptSolid', Items=[footing_solid])

            # Assign representation to the footing
            product_definition_shape = self.ifcfile.create_entity(
                "IfcProductDefinitionShape", Representations=[shape_representation])
            footing.Representation = product_definition_shape

        except Exception as e:
            print(f"An error occurred while creating the footing: {e}")
            raise

        return footing

    def create_strip_footing(self, start_point: tuple, end_point: tuple, width: float, depth: float) -> None:
        """
        Creates an IFC continuous footing (strip footing) entity with the specified parameters.

        Parameters:
        - start_point (tuple): The (x, y, z) coordinates of the start point of the footing.
        - end_point (tuple): The (x, y, z) coordinates of the end point of the footing.
        - width (float): The width of the footing.
        - depth (float): The depth of the footing.
        """
        try:
            # Get geometric representation context (not the storey)
            context = self.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = self.ifcfile.by_type("IfcOwnerHistory")[0]

            # Create footing entity
            footing = self.ifcfile.create_entity("IfcFooting", GlobalId=self.create_guid(
            ), OwnerHistory=owner_history, Name="Continuous Footing", ObjectPlacement=None, Representation=None, Tag=None, PredefinedType="FOOTING_BEAM")

            # Calculate direction and length
            direction = self.ifcfile.createIfcDirection(
                self.calc_direction(start_point, end_point))
            length = self.calc_length(start_point, end_point)
            crossprod = self.ifcfile.createIfcDirection(
                self.calc_cross(self.calc_direction(start_point, end_point), Z))

            # Create local placement for the footing
            footing_placement = self.create_ifclocalplacement(
                start_point, self.calc_direction(start_point, end_point), Z)
            footing.ObjectPlacement = footing_placement

            # Create points for footing boundary with the center as the start point
            half_width = width / 2
            length = float(length)
            points = [
                self.ifcfile.createIfcCartesianPoint((0.0, -half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (length, -half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint(
                    (length, half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint((0.0, half_width, 0.0)),
                self.ifcfile.createIfcCartesianPoint((0.0, -half_width, 0.0))
            ]

            # Create boundary polyline
            footing_line = self.ifcfile.createIfcPolyline(Points=points)
            footing_profile = self.ifcfile.createIfcArbitraryClosedProfileDef(
                ProfileType="AREA", ProfileName=None, OuterCurve=footing_line)
            ifc_direction = self.ifcfile.createIfcDirection((0.0, 0.0, 1.0))

            # Create local axis placement
            start = self.ifcfile.createIfcCartesianPoint(start_point)
            axis2placement = self.ifcfile.createIfcAxis2Placement3D(
                start, Axis=direction, RefDirection=crossprod)

            # Create extruded footing geometry
            footing_solid = self.ifcfile.create_entity(
                "IfcExtrudedAreaSolid", SweptArea=footing_profile, Position=axis2placement, ExtrudedDirection=ifc_direction, Depth=depth)
            shape_representation = self.ifcfile.create_entity(
                "IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier='Body', RepresentationType='SweptSolid', Items=[footing_solid])

            # Assign representation to the footing
            product_definition_shape = self.ifcfile.create_entity(
                "IfcProductDefinitionShape", Representations=[shape_representation])
            footing.Representation = product_definition_shape

        except Exception as e:
            print(
                f"An error occurred while creating the continuous footing: {e}")
            raise

        return footing

    def create_void_in_wall(self, wall, width: float, height: float, depth: float, void_location: tuple):
        """
        Creates a rectangular void in a wall.

        Parameters:
        - wall: The wall element in which the void will be created.
        - width (float): The width of the void (X axis).
        - height (float): The height of the void (Z axis).
        - depth (float): The depth of the void (thickness of the wall) (Y axis).
        - void_location (tuple): The local coordinates (x, y, z) of the void relative to the wall.
        """
        try:
            print(
                f"Wall: {wall}, Width: {width}, Height: {height}, Depth: {depth}, Void Location: {void_location}")
            # Get geometric representation context
            context = self.ifcfile.by_type(
                "IfcGeometricRepresentationContext")[0]
            owner_history = self.ifcfile.by_type("IfcOwnerHistory")[0]

            # pdb.set_trace()
            wall_placement = wall.ObjectPlacement  # Get wall placement
            wall_storey = ifcopenshell.util.element.get_container(wall)
            print(f"Wall Storey: {wall_storey}")
            if not wall_storey:
                print("Cannot find wall_storey")
                raise ValueError

            # Defining the void placement
            try:
                void_placement = self.create_ifclocalplacement(
                    void_location, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), wall_placement)
            except Exception as e:
                print(
                    f"An error occurred while creating the void placement: {e}")
                raise

            try:
                void_extrusion_placement = self.create_ifcaxis2placement(
                    (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            except Exception as e:
                print(
                    f"An error occurred while creating the void extrusion placement: {e}")
                raise

            point_list_void_extrusion_area = [
                (0.0, -depth, 0.0), (width, -depth, 0.0), (width,
                                                           depth, 0.0), (0.0, depth, 0.0), (0.0, -depth, 0.0)
            ]
            try:
                # Create the extruded area solid for the void element
                void_solid = self.create_ifcextrudedareasolid(
                    point_list_void_extrusion_area, void_extrusion_placement, (0.0, 0.0, 1.0), height)
            except Exception as e:
                print(f"An error occurred while creating the void solid: {e}")
                raise

            try:
                # Create the shape representation for the void element
                void_representation = self.ifcfile.createIfcShapeRepresentation(
                    context, "Body", "SweptSolid", [void_solid])
            except Exception as e:
                print(
                    f"An error occurred while creating the void representation: {e}")
                raise

            try:
                # Create the product definition shape for the void element
                void_shape = self.ifcfile.createIfcProductDefinitionShape(
                    None, None, [void_representation])
            except Exception as e:
                print(f"An error occurred while creating the void shape: {e}")
                raise

            try:
                # Create the opening element with the specified attributes
                opening_element = self.ifcfile.createIfcOpeningElement(
                    self.create_guid(), owner_history, "Void", "Wall void", None, void_placement, void_shape, None)
            except Exception as e:
                print(
                    f"An error occurred while creating the opening element: {e}")
                raise

            try:
                # Relate the opening element to the wall
                self.ifcfile.createIfcRelVoidsElement(
                    self.create_guid(), owner_history, None, None, wall, opening_element)
            except Exception as e:
                print(
                    f"An error occurred while relating the opening element to the wall: {e}")
                raise

            # # Now create the window within the void
            # try:
            #     window_placement = self.create_ifclocalplacement(
            #         (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), void_placement)
            # except Exception as e:
            #     print(
            #         f"An error occurred while creating the window placement: {e}")
            #     raise

            # try:
            #     window_extrusion_placement = self.create_ifcaxis2placement(
            #         (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            # except Exception as e:
            #     print(
            #         f"An error occurred while creating the window extrusion placement: {e}")
            #     raise

            # try:
            #     point_list_window_extrusion_area = [
            #         (0.0, -0.01, 0.0), (width, -0.01, 0.0), (width, 0.01, 0.0), (0.0, 0.01, 0.0), (0.0, -0.01, 0.0)]
            #     window_solid = self.create_ifcextrudedareasolid(
            #         point_list_window_extrusion_area, window_extrusion_placement, (0.0, 0.0, 1.0), height)
            # except Exception as e:
            #     print(
            #         f"An error occurred while creating the window solid: {e}")
            #     raise

            # try:
            #     window_representation = self.ifcfile.createIfcShapeRepresentation(
            #         context, "Body", "SweptSolid", [window_solid])
            # except Exception as e:
            #     print(
            #         f"An error occurred while creating the window representation: {e}")
            #     raise

            # try:
            #     window_shape = self.ifcfile.createIfcProductDefinitionShape(
            #         None, None, [window_representation])
            # except Exception as e:
            #     print(
            #         f"An error occurred while creating the window shape: {e}")
            #     raise

            # try:
            #     window = self.ifcfile.createIfcWindow(
            #         self.create_guid(), owner_history, "Window", "Window in void", None, window_placement, window_shape, None, None)
            # except Exception as e:
            #     print(f"An error occurred while creating the window: {e}")
            #     raise

            # # Relate the window to the opening element
            # self.ifcfile.createIfcRelFillsElement(
            #     self.create_guid(), owner_history, None, None, opening_element, window)
            # self.ifcfile.createIfcRelContainedInSpatialStructure(self.create_guid(
            # ), owner_history, "Building Storey Container", None, [wall, window], wall_storey)

        except Exception as e:
            print(f"An error occurred while creating the void: {e}")
            raise

    def calc_direction(self, start_coord, end_coord):
        """
        Calculates and returns the 3D vector that describes how to travel between the start and end coordinates.

        Parameters:
        - start_coord: the beginning point.
        - end_coord: the ending point.
        """
        # 1. Calculate the vector by subtracting the start coordinates from the end coordinates.
        direction = tuple(
            [end_coord[i] - start_coord[i] for i in range(3)])
        # 2. Returns the vector.
        return direction

    def calc_length(self, start_coord, end_coord):
        """
        Calculates and returns the distance between the start and end coordinates.

        Parameters:
        - start_coord: the beginning point.
        - end_point: the ending point.
        """
        # 1. Calculate the length by subtracting the start coordinates from the end vector and normalizing them.
        length = np.linalg.norm(np.array(end_coord) - np.array(start_coord))
        # 2. Returns the length
        return length

    def calc_cross(self, dir1, dir2):
        """
        Calculates and returns the cross product of two directions.

        Parameters:
        - dir1: the first vector.
        - dir2: the second vector.
        """
        # 1. Calculate cross product & convert np.float64 to Python float.
        crossprod = np.cross(dir1, dir2)
        crossprod = tuple(map(float, crossprod))
        # 2. Return the cross product.
        return crossprod

    def _create_single_grid(self, xMin: int, xMax: float, grid_info: dict = {'id': '1', 'distance': 0.0}) -> bool:
        """
        Creates a grid of lines in the given document based on the specified number of rows and columns,
        and the spacing between them.

        Parameters:
        - xMin (int): The minimum distance from the grid.
        - xMax (int): The maximum distance from the grid.
        - grid_info (dict): The information about the grid.

        Returns:
        line, grid: The polyline and grid axis.
        """

        # 1. Create the points for the polyline.
        pnt1 = self.ifcfile.createIfcCartesianPoint(
            (grid_info['distance'], xMin))
        pnt2 = self.ifcfile.createIfcCartesianPoint(
            (grid_info['distance'], xMax))
        # 2. Create the polyline based on the point.
        line = self.ifcfile.createIfcPolyline([pnt1, pnt2])

        # 3. Create the grid with the specified data..
        grid = self.ifcfile.createIfcGridAxis()
        grid.AxisTag = grid_info['id']
        grid.AxisCurve = line
        grid.SameSense = True

        # 4. Return the polyline and the grid.
        return line, grid

    def _create_grid_array(self, MinMaxOffset: float = 120.0, GridInfo: list = [{'id': '1', 'distance': 0.0}, {'id': '2', 'distance': 300.0}]) -> bool:
        """
        Creates a grid of lines in the given document based on the specified number of rows and columns,
        and the spacing between them.

        Parameters:
        - MinMaxOffset (int): The offset from the minimum and maximum distances.
        - GridInfo (list): The list of grids and their information.

        Returns:
        grid_lines, grid_axes: the arrays of the polylines representing grid lines and the grid object axes.
        """

        # 1. Initialize two arrays for the grid lines and the axes.
        grid_lines = []
        grid_axes = []

        # 2. Calculate minimum & maximum distances from the grid
        xMin = GridInfo[0]['distance'] - MinMaxOffset
        xMax = GridInfo[-1]['distance'] + MinMaxOffset

        # 3. for each grid passed in: create the polyline and grid axis, and add them to the appropriate storage.
        for grid_info in GridInfo:
            line, grid = self._create_single_grid(
                grid_info=grid_info, xMin=xMin, xMax=xMax)

            grid_lines.append(line)
            grid_axes.append(grid)
        # 4. Return the array of grid lines and array of grid axes
        return grid_lines, grid_axes

    def save_ifc(self, filename):
        """
        Save self to the given filename.

        Parameters:
        - filename: the name of the file to save to.
        """
        self.ifcfile.write(filename)

    def get_steel_shape_profile(self, section_name, length, width):
        """
        Returns the shape of the specified section.

        Parameters:
        - section_name: the name of the section to get the shape of.
        """
        # 1. Read in the csv file with profile data.
        try:
            wshapes_df = pd.read_csv(
                "aisc-shapes-database-v15.0.csv", encoding='utf-8')
        except UnicodeDecodeError:
            try:
                wshapes_df = pd.read_csv(
                    "aisc-shapes-database-v15.0.csv", encoding='ISO-8859-1')
            except FileNotFoundError:
                print('File not found: aisc-shapes-database-v15.0.csv')
                raise
            except Exception as e:
                print(
                    f'An unexpected error occurred while reading the file with ISO-8859-1 encoding: {e}')
                raise
        except FileNotFoundError:
            print('File not found: aisc-shapes-database-v15.0.csv')
            raise
        except Exception as e:
            print(
                f'An unexpected error occurred while reading the file with utf-8 encoding: {e}')
            raise

        # 2. Get the necessary dimensions.
        section_data = wshapes_df[wshapes_df["AISC_Manual_Label"]
                                  == section_name]

        if not section_data.empty:  # check that section exists in database
            if self.steel_types[section_name[0]] != None:
                return self.steel_types[section_name[0]](section_data, section_name)
            else:
                raise NotImplementedError(
                    f"AISC Shape Type {section_name[0]} not implemented for use")
        else:
            raise ValueError(
                f"Section {section_name} not found in AISC database.")

    def get_wshape_profile(self, section_name):
        """
        Returns the shape of the specified section.

        Parameters:
        - section_name: the name of the section to get the shape of.
        """
        # 1. Read in the csv file with profile data.
        try:
            wshapes_df = pd.read_csv(
                "aisc-shapes-database-v15.0.csv", encoding='utf-8')
        except UnicodeDecodeError:
            try:
                wshapes_df = pd.read_csv(
                    "aisc-shapes-database-v15.0.csv", encoding='ISO-8859-1')
            except FileNotFoundError:
                print('File not found: aisc-shapes-database-v15.0.csv')
                raise
            except Exception as e:
                print(
                    f'An unexpected error occurred while reading the file with ISO-8859-1 encoding: {e}')
                raise
        except FileNotFoundError:
            print('File not found: aisc-shapes-database-v15.0.csv')
            raise
        except Exception as e:
            print(
                f'An unexpected error occurred while reading the file with utf-8 encoding: {e}')
            raise

        # 2. Get the necessary dimensions.
        section_data = wshapes_df[wshapes_df["AISC_Manual_Label"]
                                  == section_name]

        if not section_data.empty:  # check that section exists in database
            d = float(section_data['d'].iloc[0]) / 12  # depth [feet]
            bf = float(section_data['bf'].iloc[0]) / 12  # width [feet]
            kdes = float(section_data['kdes'].iloc[0]
                         ) / 12  # fillet radius [feet]
            tf = float(section_data['tf'].iloc[0]) / \
                12  # thickness of flange [feet]
            tw = float(section_data['tw'].iloc[0]) / \
                12  # thickness of web [feet]
        else:
            raise ValueError(
                f"Section {section_name} not found in AISC database.")

        # 3. Create the point list of the profile.
        point_list = [
            (bf/2, 0.0), (bf/2, tf), (tw/2, tf),  # lower right
            (tw/2, d-tf), (bf/2, d-tf), (bf/2, d),  # upper right
            (-bf/2, d), (-bf/2, d-tf), (-tw/2, d-tf),  # upper left
            (-tw/2, tf), (-bf/2, tf), (-bf/2, 0.0)  # lower left
        ]

        # 4. Convert the point list to a closed profile.
        ifcpts = [self.ifcfile.createIfcCartesianPoint(
            point) for point in point_list]
        polyline = self.ifcfile.createIfcPolyline(ifcpts)
        ifcclosedprofile = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline)

        # 5. Return the closed profile
        return ifcclosedprofile

    def add_style_to_product(self, name, product):
        try:
            print(f"Product type: {type(product)}")
            material_set = self.materials[name]
            print(f"Material set: {material_set}")
            print(f"Material set for {name}: {material_set}")
            file3D = ifcopenshell.api.context.add_context(
                self.ifcfile, context_type="Model")
            print(f"3D file context created: {file3D}")
            body = ifcopenshell.api.context.add_context(self.ifcfile, context_type="Model", context_identifier="Body",
                                                        target_view="MODEL_VIEW", parent=file3D)
            print(f"Body context created: {body}")
            ifcopenshell.api.material.assign_material(
                self.ifcfile, products=[product], material=material_set[0])
            print(f"Material {material_set[0]} assigned to product {product}")
            result = ifcopenshell.api.style.assign_material_style(
                self.ifcfile, material=material_set[0], style=material_set[1], context=body)
            return result

        except Exception as e:
            print(f"An error occurred in add_style_to_product: {e}")

    def get_cshape_profile(self, section_data, section_name):
        d = float(section_data['d'].iloc[0]) / 12
        t = float(section_data['T'].iloc[0]) / 12
        k = float(section_data['k'].iloc[0]) / 12
        bf = float(section_data['bf'].iloc[0]) / 12
        tw = float(section_data['tw'].iloc[0]) / 12
        point_list = [
            (bf/2, 0.0), (bf/2, k), (-bf/2 + tw, d - t),  # Lower right corner
            (-bf/2 + tw, t), (bf/2, t + k), (bf/2, d),  # Upper right corner
            (-bf/2, d),  # Upper left corner
            (-bf/2, 0.0)  # Lower right corner
        ]
        # 4. Convert the point list to a closed profile.
        ifcpts = [self.ifcfile.createIfcCartesianPoint(
            point) for point in point_list]
        polyline = self.ifcfile.createIfcPolyline(ifcpts)
        ifcclosedprofile = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline)

        # 5. Return the closed profile
        return ifcclosedprofile

    def get_hss_profile(self, section_data, section_name):
        if section_name.count('X') == 1:
            return self.get_hssround_profile(section_data, section_name)
        else:
            return self.get_hssrect_profile(section_data, section_name)

    def get_lshape_profile(self, section_data, section_name):
        parameters = section_name.removeprefix('L')
        numbers = parameters.split(sep='X')
        x = self.get_parameter(numbers[0])
        y = self.get_parameter(numbers[1])
        d = self.get_parameter(numbers[2])
        point_list = [
            (0.0, 0.0), (0.0, y), (d, y), (d, d),
            (x, d), (x, 0.0)
        ]
        # 4. Convert the point list to a closed profile.
        ifcpts = [self.ifcfile.createIfcCartesianPoint(
            point) for point in point_list]
        polyline = self.ifcfile.createIfcPolyline(ifcpts)
        ifcclosedprofile = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline)

        # 5. Return the closed profile
        return ifcclosedprofile

    def get_parameter(self, data):
        rtn = 0
        if '/' in data:
            if '-' in data:
                rtn = float(data[0:data.find('-')])
                data = data[data.find('-')]
            [numerator, denominator] = data.split('/')
            rtn += float(numerator) / float(denominator)
        else:
            rtn = float(data)
        return rtn

    def get_hssrect_profile(self, section_data, section_name):
        b = float(section_data['b'].iloc[0]) / 12
        h = float(section_data['h'].iloc[0]) / 12
        t = float(section_data['t'].iloc[0]) / 12
        right_points = [
            (0.0, -h/2), (b/2, -h/2), (b/2, h/2), (0.0, h/2),
            (0.0, h/2 - t), (b/2 - t, h/2 - t), (b/2 - t, -h/2 + t), (0.0, -h/2 + t)

        ]
        left_points = [
            (0.0, -h/2), (-b/2, -h/2), (-b/2, h/2), (0.0, h/2),
            (0.0, h/2 - t), (-b/2 + t, h/2 -
                             t), (-b/2 + t, -h/2 + t), (0.0, -h/2 + t)
        ]
        ifcpts_r = [self.ifcfile.createIfcCartesianPoint(
            point_r) for point_r in right_points]
        ifcpts_l = [self.ifcfile.createIfcCartesianPoint(
            point_l) for point_l in left_points]
        polyline_r = self.ifcfile.createIfcPolyline(ifcpts_r)
        polyline_l = self.ifcfile.createIfcPolyline(ifcpts_l)
        profile_r = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline_r)
        profile_l = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline_l)
        profile = self.ifcfile.createIfcCompositeProfileDef(
            "AREA", None, [profile_l, profile_r], None)
        return profile

    def get_hssround_profile(self, section_data, section_name):
        r = float(section_data['r'].iloc[0]) / 12
        t = float(section_data['t'].iloc[0]) / 12
        right_points = [
            (0.0, r), (r, 0.0), (0.0, -r),
            (0.0, -r + t), (r - t, 0.0), (0.0, r - t)
        ]
        left_points = [
            (0.0, r), (-r, 0.0), (0.0, -r),
            (0.0, -r + t), (-r + t, 0.0), (0.0, r - t)
        ]
        list_r = self.ifcfile.createIfcCartesianPointList2D(right_points, None)
        list_l = self.ifcfile.createIfcCartesianPointList2D(left_points, None)
        curve_r = self.ifcfile.createIfcIndexedPolyCurve(list_r, [
            self.ifcfile.createIfcCurveIndex(
                1, 2), self.ifcfile.createIfcCurveIndex(2, 3),
            self.ifcfile.createIfcLineIndex(
                3, 4), self.ifcfile.createIfcCurveIndex(4, 5),
            self.ifcfile.createIfcCurveIndex(
                5, 6), self.ifcfile.createIfcLineIndex(6, 1)
        ], None)
        curve_l = self.ifcfile.createIfcIndexedPolyCurve(list_l, [
            self.ifcfile.createIfcCurveIndex(
                1, 2), self.ifcfile.createIfcCurveIndex(2, 3),
            self.ifcfile.createIfcLineIndex(
                3, 4), self.ifcfile.createIfcCurveIndex(4, 5),
            self.ifcfile.createIfcCurveIndex(
                5, 6), self.ifcfile.createIfcLineIndex(6, 1)
        ], None)
        profile_r = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, curve_r)
        profile_l = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, curve_l)
        profile = self.ifcfile.createIfcCompositeProfileDef(
            "AREA", None, [profile_l, profile_r], None)
        return profile

    def get_rectangle(self, section_name, length, width):
        points = [
            [0.0, 0.0, 0.0], [0.0, width, 0.0], [
                length, width, 0.0], [length, 0.0, 0.0]
        ]
        print(f"Points: {points}")
        ifcpts = []
        for point in points:
            # Ensure all values are floats
            coords = list(map(float, point))
            ifc_point = self.ifcfile.createIfcCartesianPoint(coords)
            ifcpts.append(ifc_point)

        # # Print the created IFC points
        # for ifc_point in ifcpts:
        #     print(ifc_point)
        # print(f"IFC Points: {ifcpts}")
        polyline = self.ifcfile.createIfcPolyline(ifcpts)
        print(f"Polyline: {polyline}")
        ifcclosedprofile = self.ifcfile.createIfcArbitraryClosedProfileDef(
            "AREA", None, polyline)
        print(f"IFC Closed Profile: {ifcclosedprofile}")

        # 5. Return the closed profile
        return ifcclosedprofile
