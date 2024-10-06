from copy import deepcopy
from global_store import global_store
from feature_extractor import IfcEntityFeatureExtractor
from tool_helpers import format_output_search_result


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

def get_element_characteristics(sid, object_id):
    ifc_model = global_store.sid_to_ifc_model.get(sid, None)
    if ifc_model is None:
        return "No IFC model found for this session."
    ifc_entity = ifc_model.ifcfile.by_id(object_id)
    feature_extractor = IfcEntityFeatureExtractor()
    features = feature_extractor.extract_entity_features(ifc_entity)
    return format_output_search_result([features])