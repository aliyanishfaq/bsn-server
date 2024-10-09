import os
from dotenv import load_dotenv
from tools_graph import create_beam, create_column, create_wall, create_session, create_roof, create_building_story, create_floor, search_canvas, delete_objects, create_grid, refresh_canvas, create_isolated_footing, create_strip_footing, create_void_in_wall, copy_element, create_door, create_window
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage, HumanMessage, ToolMessage, AIMessage)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import ToolNode
from typing import Literal
from langchain_core.messages import BaseMessage
import asyncio
from socket_server import sio
from langchain_core.runnables import RunnableConfig
from tenacity import retry, stop_after_attempt, wait_exponential
import base64
from langgraph.checkpoint.memory import MemorySaver
import re


# Constants
os.environ["LANGCHAIN_PROJECT"] = "BuildSync Agent v1.0"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
ANTRHOPIC_API_KEY = os.getenv('ANTRHOPIC_API_KEY')
LANGSMITH_API_KEY = os.getenv('LANGSMITH_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL_TYPE = 'CLAUDE'
IFC_MODEL = None
IMAGE_INPUT = True
O = 0., 0., 0.
X = 1., 0., 0.
Y = 0., 1., 0.
Z = 0., 0., 1.


# State definition
class State(TypedDict):
    messages: Annotated[list, add_messages]


buildsync_graph_builder = StateGraph(State)
# model to be used in production: claude-3-5-sonnet-20240620 cheaper option: claude-3-haiku-20240307
llm = ChatAnthropic(model='claude-3-5-sonnet-20240620',
                    streaming=True, verbose=True, api_key=ANTRHOPIC_API_KEY)
# llm = ChatOpenAI(model='gpt-4o', streaming=True, verbose=True, api_key=OPENAI_API_KEY)

# examples
examples = {
    "rectangle_building": [
        HumanMessage("Build a 1 story building", name="example_user"),
        # Create 1 story
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_building_story", "args": {"building_stories_amount": 1}, "id": "1"}]),
        ToolMessage("Created story 1", tool_call_id="1"),
        # Create 1 floor
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_floor", "args": {"story_n": 1}, "id": "2"}]),
        ToolMessage("Created floor on story 1", tool_call_id="2"),
        # Create 4 walls
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,0,0", "end_coord": "0,100,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 1/4 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,0,0", "end_coord": "100,0,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 2/4 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "100,0,0", "end_coord": "100,100,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 2/4 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,100,0", "end_coord": "100,100,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 4/4 walls on story 1", tool_call_id="3"),
        AIMessage("Created a one story building", name="example_assistant")
    ],

    "l_shaped_building": [
        HumanMessage("Build a L-shaped 1 story building",
                     name="example_user"),
        # Create 1 story
        AIMessage("I will invoke create_building_story, create_floor, create_wall", name="example_assistant",
                  tool_calls=[{"name": "create_building_story", "args": {"building_stories_amount": 1}, "id": "1"}]),
        ToolMessage("Created building stories", tool_call_id="1"),
        # Create 2 floors
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_floor", "args": {"story_n": 1, "start_coord": "0,0,0", "length_x": "50", "length_y": "100"}, "id": "2"}]),
        ToolMessage("Created 1st floor on story 1", tool_call_id="2"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_floor", "args": {"story_n": 1, "start_coord": "50,0,0", "length_x": "50", "length_y": "50"}, "id": "2"}]),
        ToolMessage("Created 2nd floor on story 1", tool_call_id="2"),
        # Create 6 walls to wrap around floors
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,0,0", "end_coord": "0,100,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 1/6 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,0,0", "end_coord": "100,0,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 2/6 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "0,100,0", "end_coord": "50,100,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 3/6 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "100,0,0", "end_coord": "100,50,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 4/6 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "50,100,0", "end_coord": "50,50,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 5/6 walls on story 1", tool_call_id="3"),
        AIMessage("", name="example_assistant",
                  tool_calls=[{"name": "create_wall", "args": {"story_n": 1, "start_coord": "50,50,0", "end_coord": "100,50,0", "height": 30}, "id": "3"}]),
        ToolMessage("Created 6/6 walls on story 1", tool_call_id="3"),
        # Success message
        AIMessage("Created a one story L-shaped building",
                  name="example_assistant")
    ]
}
flattened_examples = []
for key, value in examples.items():
    flattened_examples.extend(value)


def create_agent(llm, tools):
    """Create an agent."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system",
             """
            You are an AI BIM modeller. You are working with IFC files and you are provided with creation and editing tasks for IFC files.
            You will respond to user queries and invoke relevant tools to complete the user's request. 
            Do not ask follow up questions. If the user's answer is not clear, use default parameters. 
            Be as concise as possible. Keep your answer to 50 words.
            In case the user is referring to something specific, you should use search_canvas to retrieve specific information from file and then use that information to complete the user's request.
            You have access to the following tools: {tool_names}
            """
             ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    prompt = prompt.partial(tool_names=", ".join(
        [tool.name for tool in tools]))
    return prompt | llm.bind_tools(tools)


tools = [create_beam, create_column, create_wall, create_session, create_roof, create_building_story, create_floor,
         delete_objects, create_grid, search_canvas, refresh_canvas, create_isolated_footing, create_strip_footing, create_void_in_wall, copy_element, create_door, create_window]
llm_with_tools = create_agent(llm, tools)


async def chat_node(state: State, config: RunnableConfig):
    messages = state['messages']
    response = await llm_with_tools.ainvoke(messages, config)
    return {'messages': response}

tool_node = ToolNode(tools=tools)


def route_tools(state: State) -> Literal["tools", "__end__"]:
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    # Checks if dictionary or list
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(
            f"No messages found in input state to tool_edge: {state}")
    # print(ai_message.content)
    print('ai_message.content[0]', ai_message.content[0])
    if hasattr(ai_message.content[0], "text"):
        content = ai_message.content[0]["text"]
    else:
        content = ""
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    elif "invoked" in content.lower() and len(ai_message.tool_calls) == 0:  # if the tools weren't actually called
        return "tools"
    return "__end__"


buildsync_graph_builder.add_node("tools", tool_node)
buildsync_graph_builder.add_node("chat", chat_node)
buildsync_graph_builder.add_edge("tools", "chat")
buildsync_graph_builder.add_edge(START, "chat")

buildsync_graph_builder.add_conditional_edges(
    "chat",
    route_tools,
    {"tools": "tools", "__end__": "__end__"},
)

# memory = AsyncSqliteSaver.from_conn_string(":memory:", )
memory = MemorySaver()
config = {"configurable": {"thread_id": "1"}}
graph = buildsync_graph_builder.compile(checkpointer=memory)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
async def stream_with_backoff(data: dict, config: dict):
    user_command = data.get('message')
    image_data = data.get('imageData')
    message_type = data.get('messageType')
    if 'context' in data:
        context = data.get('context')
        print("Context: ", context)
    else:
        context = None
    if message_type == 'Image':
        prefix = re.match(r'data:image/(\w+);base64,(.+)', image_data)
        try:
            image_type = f"image/{prefix.group(1)}"
            encoded_image = prefix.group(2)
        except Exception as e:
            raise e
        # Read the image file in binary mode
        messages = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": encoded_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_command
                        }
                    ],
                }]
        }
    elif context:
        messages = {
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": context
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_command
                        }
                    ],
                }]
        }
    else:
        messages = {"messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_command
                }
            ]}]}
    async for event in graph.astream_events(messages, config, version='v1'):
        yield event


async def model_streamer(sid, data: dict, unique_hash: str):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    tools_end = False
    async for event in stream_with_backoff(data, config):
        kind = event['event']
        # print(kind)
        if kind == 'on_chat_model_stream':
            try:
                # print
                message = event.get('data').get('chunk').content[0].get('text')
                # print("on_chat_stream", message)
                if message:
                    await sio.emit('aiAction', {'word': message, 'hash': unique_hash, 'tools_end': tools_end})
            except (KeyError, IndexError, TypeError, AttributeError) as e:
                print(e)
        elif kind == "on_chat_model_end":
            content = {'hash': unique_hash}
            asyncio.run_coroutine_threadsafe(
                sio.emit('on_prompt_end', content), loop)

        elif kind == "on_tool_start":
            print(
                f"Starting tool: {event.get('name')} with inputs: {event.get('data').get('input')}"
            )
            message = f"Starting tool: {event.get('name')} with inputs: {event.get('data').get('input')}"
            await sio.emit('toolStart', {'word': message, 'hash': unique_hash})

        elif kind == "on_tool_end":
            tools_end = True
            print(f"Done tool: {event.get('name')}")
            print(f"Tool output was: {event.get('data').get('output')}")
            message = f"{event.get('name')} execution successfully completed"
            if bool(event.get('data').get('output')) is True:
                message = f"{event.get('name')} execution successfully completed"
                await sio.emit('toolEnd', {'word': message, 'hash': unique_hash})
            else:
                message = f"{event.get('name')} execution failed"
            print("emitting fileChange")
            print("SID: ", sid)
            fileContent = open('public/canvas.ifc', 'rb').read()
            filePath = 'public/canvas.ifc'
            await sio.emit('fileChange', {'userId': 'BuildSync', 'message': 'A new change has been made to the file', 'file_name': 'public/canvas.ifc', 'file_content': fileContent})
            print("fileChange emitted")
            # print('file contents: ', open('public/canvas.ifc', 'rb').read())
        elif kind == "on_chain_start":
            # print("event_data", event['data'])
            try:
                messages = event['data']['input']['messages']
                if type(messages) == list and type(messages[-1]) == AIMessage:
                    # print("yes, is AIMessage", messages[-1])
                    message_object = messages[-1].content
                    # print("message object", message_object)
                    message = message_object[0]['text']
                    # print("on_chain_start message", message)
                    await sio.emit('chainStart', {'word': message, 'hash': unique_hash, 'tools_end': tools_end})
            except (KeyError, IndexError, TypeError, AttributeError) as e:
                print(e)
        elif kind == "on_chain_end":
            # print("event_data", event['data'])
            messages = event['data']['output']
            # print("messages chain_end", messages)
            try:
                if type(messages) == dict and "chat" in messages.keys():
                    # print("yes, is AIMessage", messages[-1])
                    # AIMessage()
                    ai_message_object = messages["chat"]["messages"]
                    message_content = ai_message_object.content
                    print("message object", message_content)
                    message = message_content[0]['text']
                    print("on_chain_end message", message)
                    await sio.emit('chainStart', {'word': message, 'hash': unique_hash, 'tools_end': tools_end})
            except (KeyError, IndexError, TypeError, AttributeError) as e:
                print(e)
        elif kind == "on_chain_stream":
            # print(event)
            pass
