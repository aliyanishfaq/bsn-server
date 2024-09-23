from copy import deepcopy


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
