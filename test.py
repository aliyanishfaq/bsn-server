"""
Error: TypeError("attribute 'Coordinates' for entity 'IFC2X3.IfcCartesianPoint' is expecting value of type 'AGGREGATE OF DOUBLE', got 'tuple'.")
 Please fix your mistakes.
"""
@tool
def create_floor(storey_n: int = 1, point_list: list = [(0.,0.,0.),(0.,100.,0.),(100.,100.,0.),(100.,0.,0.)], slab_thickness: float = 1.0) -> bool:
    """
    Creates a floor in the specified storey with given dimensions and thickness.

    Parameters:
    - storey_n (int): The storey number where the slab will be created.
    - point_list (list): The list of points that make up the floor boundary
    - slab_thickness (float): The thickness of the slab.
    """
    global retrieval_tool
    try:
        print(f"storey_n: {storey_n}, point_list: {point_list}, slab_thickness: {slab_thickness}")

        # Get model information
        context = IFC_MODEL.ifcfile.by_type("IfcGeometricRepresentationContext")[0]
        owner_history = IFC_MODEL.ifcfile.by_type("IfcOwnerHistory")[0]

        # Get story information
        if len(IFC_MODEL.building_storey_list) < storey_n:
            create_building_storey(elevation=0, name=f"Level {storey_n}")

        storey = IFC_MODEL.building_storey_list[storey_n - 1]
        elevation = (storey.Elevation)
        storey_placement = storey.ObjectPlacement # banana: is this needed?
        print(f"elevation: {elevation}")
        
        # Create slab boundary
        slab = ifcopenshell.api.run("root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlab") # create IFC slab entity
        slab_placement = IFC_MODEL.create_ifclocalplacement(
            (0, 0, elevation), Z, X, relative_to=storey_placement) # define local placement of slab within building model
        slab.ObjectPlacement = slab_placement # assign local placement to slab
        ifc_slabtype = ifcopenshell.api.run("root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlabType") # create IFC slab type entity
        ifcopenshell.api.run("type.assign_type", IFC_MODEL.ifcfile,
                            related_objects=[slab], relating_type=ifc_slabtype)
        
        # Ceate points for slab boundary
        points = [IFC_MODEL.ifcfile.createIfcCartesianPoint([x, y, float(elevation)]) for x, y in point_list]
        points.append(points[0]) # close loop


        # Create boundary polyline
        slab_line = IFC_MODEL.ifcfile.createIfcPolyline(points)
        slab_profile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef("AREA", None, slab_line)
        ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)

        # Create local axis placement
        point = IFC_MODEL.ifcfile.createIfcCartesianPoint([0.0, 0.0, 0.0])
        dir1 = IFC_MODEL.ifcfile.createIfcDirection((0., 0., 1.0))
        dir2 = IFC_MODEL.ifcfile.createIfcDirection((1.0, 0., 0.0))
        axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
            point, dir1, dir2)

        # Create extruded slab geometry
        extrusion = slab_thickness
        slab_solid = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid(
            slab_profile,  axis2placement, ifc_direction, extrusion)
        shape_representation = IFC_MODEL.ifcfile.createIfcShapeRepresentation(ContextOfItems=context,
                                                                            RepresentationIdentifier='Body',
                                                                            RepresentationType='SweptSolid',
                                                                            Items=[slab_solid])

        print(f"Shape Representation: {shape_representation}, IFC Slab Type: {ifc_slabtype}, IFC Slab: {slab}, Storey: {storey}, Elevation: {elevation}, Points: {points}")

        # Create product entity and assign to spatial container
        ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                            product=ifc_slabtype, representation=shape_representation) # geometric representation
        ifcopenshell.api.run("spatial.assign_container", IFC_MODEL.ifcfile,
                            products=[slab], relating_structure=storey) # assign to a spatial container (the story)

        # Save structure
        IFC_MODEL.save_ifc("public/canvas.ifc")
        retrieval_tool = parse_ifc()
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

async def create_slab(storey_n: int = 1, length_x: float = 100.0, length_y: float = 100.0, slab_thickness: float = 2.0) -> None:
    """
    Creates a slab in the specified storey with given dimensions and thickness.

    Parameters:
    - storey_n (int): The storey number where the slab will be created.
    - length_x (float): The length of the slab in the x-direction.
    - length_y (float): The length of the slab in the y-direction.
    - slab_thickness (float): The thickness of the slab.
    """
    global retrieval_tool
    print(
        f"storey_n: {storey_n}, length_x: {length_x}, length_y: {length_y}, slab_thickness: {slab_thickness}")

    # getting storey information
    if len(IFC_MODEL.building_storey_list) < storey_n:
        IFC_MODEL.create_building_storeys(
            building_storeys_amount=1, elevation=0, building_storey_height=30)

    storey = IFC_MODEL.building_storey_list[storey_n - 1]
    elevation = (storey.Elevation)
    storey_placement = storey.ObjectPlacement
    print(f"elevation: {elevation}")

    # populating start coord
    start_coord = list(map(float, ("0,0,0").split(',')))
    start_coord[2] = elevation
    start_coord = tuple(start_coord)

    # model information
    context = IFC_MODEL.ifcfile.by_type("IfcGeometricRepresentationContext")[0]

    # creating ifc slab
    ifc_slab = ifcopenshell.api.run(
        "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlab", name="slab")
    slab_placement = IFC_MODEL.create_ifclocalplacement(
        start_coord, Z, X, relative_to=storey_placement)
    # Assign the local placement to the slab
    ifc_slab.ObjectPlacement = slab_placement
    ifc_slabtype = ifcopenshell.api.run(
        "root.create_entity", IFC_MODEL.ifcfile, ifc_class="IfcSlabType")
    ifcopenshell.api.run("type.assign_type", IFC_MODEL.ifcfile,
                         related_objects=[ifc_slab], relating_type=ifc_slabtype)

    pnt1 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
        (0.0, 0.0, float(elevation)))
    pnt2 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
        (0.0, length_y, float(elevation)))
    pnt3 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
        (length_x, length_y, float(elevation)))
    pnt4 = IFC_MODEL.ifcfile.createIfcCartesianPoint(
        (length_x, 0.0, float(elevation)))

    slab_line = IFC_MODEL.ifcfile.createIfcPolyline(
        [pnt1, pnt2, pnt3, pnt4])
    ifcclosedprofile = IFC_MODEL.ifcfile.createIfcArbitraryClosedProfileDef(
        "AREA", None, slab_line)
    ifc_direction = IFC_MODEL.ifcfile.createIfcDirection(Z)

    point = IFC_MODEL.ifcfile.createIfcCartesianPoint((0.0, 0.0, 0.0))
    dir1 = IFC_MODEL.ifcfile.createIfcDirection((0., 0., 1.))
    dir2 = IFC_MODEL.ifcfile.createIfcDirection((1., 0., 0.))
    axis2placement = IFC_MODEL.ifcfile.createIfcAxis2Placement3D(
        point, dir1, dir2)

    extrusion = slab_thickness
    slab_solid = IFC_MODEL.ifcfile.createIfcExtrudedAreaSolid(
        ifcclosedprofile,  axis2placement, ifc_direction, extrusion)
    shape_representation = IFC_MODEL.ifcfile.createIfcShapeRepresentation(ContextOfItems=context,
                                                                          RepresentationIdentifier='Body',
                                                                          RepresentationType='SweptSolid',
                                                                          Items=[slab_solid])

    print(f"Shape Representation: {shape_representation}, IFC Slab Type: {ifc_slabtype}, IFC Slab: {ifc_slab}, Storey: {storey}, Elevation: {elevation}, Point 1: {pnt1}, Point 2: {pnt2}, Point 3: {pnt3}, Point 4: {pnt4}")

    ifcopenshell.api.run("geometry.assign_representation", IFC_MODEL.ifcfile,
                         product=ifc_slabtype, representation=shape_representation)
    ifcopenshell.api.run("spatial.assign_container", IFC_MODEL.ifcfile,
                         products=[ifc_slab], relating_structure=storey)

    # Save structure
    IFC_MODEL.save_ifc("public/canvas.ifc")
    asyncio.create_task(
        sio.emit('fileChange', {
                 'userId': 'BuildSync', 'message': 'A new column has been created successfully.', 'file_name': 'public/canvas.ifc'})
    )
    retrieval_tool = parse_ifc()

