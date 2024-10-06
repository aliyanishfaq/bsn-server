from copy import deepcopy
import ifcopenshell
from feature_extractor import IfcEntityFeatureExtractor


def inject_sid(ai_message, sid):
    """
    Injects the session ID into the tool calls.
    """
    if not ai_message.tool_calls:
        return ai_message

    tool_calls = []
    for tool_call in ai_message.tool_calls:
        tool_call_copy = deepcopy(tool_call)
        tool_call_copy["args"]["sid"] = sid
        tool_calls.append(tool_call_copy)

    ai_message.tool_calls = tool_calls
    return ai_message

def format_output_search_canvas(data_list):
    formatted_output = "Relevant IFC Objects found through search_canvas:\n\n"
    for index, item in enumerate(data_list, 1):
        formatted_output += f"Object {index}:\n"
        for key, value in item.items():
            formatted_output += f"  {key}: {value}\n"
        formatted_output += "\n"
    return formatted_output


def get_element_characteristics(sid, object_id):
    ifc_file = ifcopenshell.open('/Users/aliyanishfaq/Documents/GitHub/bsn-server/public/user_uploaded.ifc')
    ifc_model = ifc_file
    #print(dir(ifc_model))
    #print(ifc_model.by_id(315))
    #print(dir(ifc_model.by_id(315)))
    ifc_entity = ifc_model.by_id(74)
    feature_extractor = IfcEntityFeatureExtractor()
    features = feature_extractor.extract_entity_features(ifc_entity)
    print('FEATURES: ', format_output_search_canvas([features]))


    #print('IFC ELEMENT: ', ifc_element)
    #ifc_element_2 = ifc_model.by_type('IfcWall')
    #print('IFC ELEMENT 2: ', ifc_element_2)
    #print('Ifc Element Id: ', ifc_element.GlobalId)
    #print('Ifc type:', ifc_element.is_a())
    #print(help(ifc_model.by_id))
    return

    if ifc_model is None:
        return "No IFC model found for this session."
    element = ifc_model.by_id(object_id)
    if element:
        return {
            "IFC Type": element.is_a(),
            "GlobalId": element.GlobalId,
            "Name": getattr(element, "Name", None),
            "ObjectType": getattr(element, "ObjectType", None),
            "Description": getattr(element, "Description", None),
            "Tag": getattr(element, "Tag", None),
            "PredefinedType": getattr(element, "PredefinedType", None)
        }
    else:
        return "Element not found."

print(get_element_characteristics('', '315'))