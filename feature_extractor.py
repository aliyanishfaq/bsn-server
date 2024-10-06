"""
Class to extract features (parameters to BuildSync create functions) from IFC Entity into a dictionary.
"""
import numpy as np
import warnings

class IfcEntityFeatureExtractor:
    def extract_entity_features(self, entity):
        function_mapping = {
            'IfcWall': self.extract_wall_features,
            'IfcWallStandardCase': self.extract_wall_features,
            'IfcColumn': self.extract_column_features,
            'IfcBeam': self.extract_beam_features,
            'IfcSlab': self.extract_floor_features,
            'IfcBuildingStorey': self.extract_story_features,
            'IfcRoof': self.extract_roof_features
        }
        extraction_function = function_mapping.get(entity.is_a())
        if extraction_function is None:
            print('No extraction function found for entity type:', entity.is_a())
            return {}
        else:
            return extraction_function(entity)
    def extract_wall_features(self, wall):
        """
        Extracts the following features from the IfcWall:
        - wall
        - global_id
        - type
        - storey_name
        - start_coord
        - end_coord
        - height
        - thickness
        """
        features = {}
        wall_name = None
        wall_guid = None
        wall_type = None
        storey_name = None
        global_start = None
        global_end = None
        depth = None
        thickness = None

        try:
            # get the global id and wall
            wall_name = wall.Name
            wall_guid = wall.GlobalId
            wall_type = wall.is_a()
        except:
            raise Exception("Wall does not have a name or global id")
        try:
            # get the storey of the wall
            container_element = wall.ContainedInStructure[0]
            story = container_element.RelatingStructure
            storey_name = story.Name
        except:
            warnings.warn("Wall does not have a storey")
            storey_name = None
            storey_name = None
        try:
            # get the local placement coordinates of the wall
            points = wall.Representation.Representations[0].Items[0].Points
            local_start_coord = np.array(points[0].Coordinates)
            local_end_coord = np.array(points[1].Coordinates)
        except:
            warnings.warn("Wall does not have a local start or end coordinate")
            local_start_coord = None
            local_end_coord = None
        
        try:
            # get the relevant placement placement coordinate and reference direction
            relative_placement = wall.ObjectPlacement.RelativePlacement
            relative_coordinates = np.array(relative_placement.Location.Coordinates)
            ref_direction = np.array(relative_placement.RefDirection.DirectionRatios)
        except:
            warnings.warn("Wall does not have a relevant placement coordinate and/or reference direction")
            relative_coordinates = None
            ref_direction = None
        
        try:
            # get the height/depth of the wall
            depth = wall.Representation.Representations[1].Items[0].Depth
        except:
            warnings.warn("Wall does not have a height")
            depth = None
        try:
            # get the thickness of the wall
            wall_coordinates = wall.Representation.Representations[1].Items[0].SweptArea.OuterCurve.Points
            wall_coordinates = np.array([point.Coordinates for point in wall_coordinates])
            thickness = None
            first_point = wall_coordinates[0]
            for point in wall_coordinates:
                if first_point[0] == point[0]:
                    thickness = abs(first_point[1]) + abs(point[1])
                    break
            if thickness is None:
                warnings.warn("Wall does not have a thickness")
        except:
            warnings.warn("Wall does not have a thickness")
        
        try:
            euclidean_distance = np.linalg.norm(np.array(local_end_coord) - np.array(local_start_coord))
            global_start = np.array(relative_coordinates)
            global_end = np.array(global_start) + np.array(ref_direction) * euclidean_distance
        except:
            warnings.warn("Feature processing failed")
        
        features = {
            'name': wall_name,
            'global_id': wall_guid,
            'type': wall_type,
            'storey_name': storey_name,
            'start_coord': str(global_start),
            'end_coord': str(global_end),
            'height': depth,
            'thickness': thickness
        }
        return features
    def extract_column_features(self, column):
        """
        Extracts the following features from the IfcColumn:
        - name
        - global_id
        - type
        - storey_name
        - start_coord
        - height
        - section_name
        """
        features = {}
        column_name = None
        column_guid = None
        column_type = None
        storey_name = None
        relative_coordinates = None
        height = None
        section_name = None

        try:
            # get the global id and name
            column_name = column.Name
            column_guid = column.GlobalId
            column_type = column.is_a()
        except:
            raise Exception("Column does not have a name or global id")
        try:
            # get the storey of the column
            container_element = column.ContainedInStructure[0]
            story = container_element.RelatingStructure
            storey_name = story.Name
        except:
            warnings.warn("Column does not have a story")
        try:
            # get the relative placement coordinate
            relative_placement = column.ObjectPlacement.RelativePlacement
            relative_coordinates = np.array(relative_placement.Location.Coordinates)
        except:
            warnings.warn("Column does not have a relative placement coordinate")
        try:
            # get the height of the column
            height = column.Representation.Representations[0].Items[0].Depth
        except:
            warnings.warn("Column does not have a height")
        try:
            # get the section name of the column
            section_name = column.Representation.Representations[0].Items[0].SweptArea.ProfileName
        except:
            warnings.warn("Column does not have a section name")
        features = {
            'name': column_name,
            'global_id': column_guid,
            'type': column_type,
            'storey_name': storey_name,
            'start_coord': str(relative_coordinates),
            'height': height,
            'section_name': section_name
        }
        return features
    def extract_beam_features(self, beam):
        """
        Extracts the following features from the IfcBeam:
        - name
        - global_id
        - type
        - storey_name
        - start_coord
        - end_coord
        - length
        - section_name
        """
        features = {}
        beam_name = None
        beam_guid = None
        beam_type = None
        storey_name = None
        relative_coordinates = None
        end_coordinates = None
        length = None
        section_name = None 

        try:
            # get the global id an name
            beam_name = beam.Name
            beam_guid = beam.GlobalId
            beam_type = beam.is_a()
        except:
            raise Exception("Beam does not have a name or global id")
        try:
            # get the storey of the column
            container_element = beam.ContainedInStructure[0]
            story = container_element.RelatingStructure
            storey_name = story.Name
        except:
            warnings.warn("Beam does not have a story")
        try:
            # get the relative placement coordinate
            relative_placement = beam.ObjectPlacement.RelativePlacement
            relative_coordinates = np.array(relative_placement.Location.Coordinates)
            axis_ratio_vector = np.array(relative_placement.Axis.DirectionRatios)
        except:
            warnings.warn("Beam does not have a relative placement coordinate and/or axis placement coordinate")
        try:
            # get the length of the column
            length = beam.Representation.Representations[0].Items[0].Depth
        except:
            warnings.warn("Beam does not have a height")
        try:
            # get the section name of the column
            section_name = beam.Representation.Representations[0].Items[0].SweptArea.ProfileName
        except:
            warnings.warn("Beam does not have a section name")
        
        try:
            end_coordinates = relative_coordinates + axis_ratio_vector
        except:
            warnings.warn("Beam does not have a end coordinate")
        features = {
            'name': beam_name,
            'global_id': beam_guid,   
            'type': beam_type,
            'storey_name': storey_name,
            'start_coord': str(relative_coordinates),
            'end_coord': str(end_coordinates),
            'length': length,
            'section_name': section_name
        }
        return features
    def extract_floor_features(self, floor):
        """
        Extracts the following features from the IfcColumn:
        - name
        - global_id
        - type
        - storey_name
        - point_list
        - slab_thickness
        """
        features = {}
        floor_name = None
        floor_guid = None
        floor_type = None
        storey_name = None
        point_list = None
        slab_thickness = None

        try:
            # get the global id and name
            floor_name = floor.Name
            floor_guid = floor.GlobalId
            floor_type = floor.is_a()
        except:
            raise Exception("Floor does not have a name or global id")
        try:
            # get the storey of the column
            container_element = floor.ContainedInStructure[0]
            story = container_element.RelatingStructure
            storey_name = story.Name
        except:
            warnings.warn("Floor does not have a story")
        try:
            # get the point list of the slab
            point_objects = floor.Representation.Representations[0].Items[0].MappingSource.MappedRepresentation.Items[0].SweptArea.OuterCurve.Points
            point_list = np.array([np.array(point.Coordinates) for point in point_objects])
        except:
            warnings.warn("Floor does not have a point list")
        try:
            # get the slab thickness of the column
            slab_thickness = floor.Representation.Representations[0].Items[0].MappingSource.MappedRepresentation.Items[0].Depth
        except:
            warnings.warn("Floor does not have a slab thickness")
        
        features = {
            'name': floor_name,
            'global_id': floor_guid,
            'type': floor_type,
            'storey_name': storey_name,
            'point_list': str(point_list),
            'slab_thickness': slab_thickness
        }
        return features
    def extract_roof_features(self, roof):
        """
        Extracts the following features from the IfcRoof:
        - name
        - global_id
        - type
        - storey_name
        - point_list
        - roof_thickness
        """
        features = {}
        roof_name = None
        roof_guid = None
        roof_type = None
        storey_name = None
        point_list = None
        roof_thickness = None

        try:
            # get the global id and name
            roof_name = roof.Name
            roof_guid = roof.GlobalId
            roof_type = roof.is_a()
        except:
            raise Exception("Roof does not have a name or global id")
        try:
            # get the storey of the column
            container_element = roof.ContainedInStructure[0]
            story = container_element.RelatingStructure
            storey_name = story.Name
        except:
            warnings.warn("Roof does not have a story")
        try:
            # get the point list of the slab
            point_objects = roof.Representation.Representations[0].Items[0].SweptArea.OuterCurve.Points
            point_list = np.array([np.array(point.Coordinates) for point in point_objects])
        except:
            warnings.warn("Roof does not have a point list")
        try:
            # get the slab thickness of the column
            roof_thickness = roof.Representation.Representations[0].Items[0].Depth
        except:
            warnings.warn("Roof does not have a slab thickness")
        
        features = {
            'name': roof_name,
            'global_id': roof_guid,
            'type': roof_type,
            'storey_name': storey_name,
            'point_list': str(point_list),
            'roof_thickness': roof_thickness
        }
        return features
    def extract_story_features(self, story):
        """
        Extracts the following features from the IfcStorey:
        - name
        - global_id
        - type
        - elevation
        """
        features = {}
        story_name = None
        story_guid = None
        story_type = None
        story_elevation = None
        try:
            story_name = story.Name
            story_guid = story.GlobalId
            story_type = story.is_a()
            story_elevation = story.Elevation
        except:
            warnings.warn("Story features not found")
        features = {
            'name': story_name,
            'global_id': story_guid,
            'type': story_type,
            'elevation': story_elevation
        }
        return features
    