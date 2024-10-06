def format_output_search_canvas(data_list):
    formatted_output = "Relevant IFC Objects found through search_canvas:\n\n"
    for index, item in enumerate(data_list, 1):
        formatted_output += f"Object {index}:\n"
        for key, value in item.items():
            formatted_output += f"  {key}: {value}\n"
        formatted_output += "\n"
    return formatted_output

def format_output_search_result(data_list):
    formatted_output = ""
    for index, item in enumerate(data_list, 1):
        formatted_output += f"Selected Object"
        for key, value in item.items():
            formatted_output += f"  {key}: {value}\n"
        formatted_output += "\n"
    return formatted_output