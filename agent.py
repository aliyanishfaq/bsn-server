from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import ConfigurableField
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.prompts import MessagesPlaceholder
from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import sys
import asyncio
from tools import create_beam, create_column, create_wall, create_session, create_roof, create_building_storey, create_floor, retrieval_tool, delete_object
from socket_server import sio
from langchain_core.tools import tool


load_dotenv()

OPEN_API_KEY = os.getenv('OPEN_API_KEY')
IFC_MODEL = None
O = 0., 0., 0.
X = 1., 0., 0.
Y = 0., 1., 0.
Z = 0., 0., 1.


# --- LANGCHAIN INITIALIZATION ------ #

MEMORY_KEY = "chat_history"
chat_history = []

tools = [create_beam, create_column, create_wall,
         create_session, create_roof, create_building_storey, create_floor, retrieval_tool, delete_object]

llm = ChatOpenAI(model="ft:gpt-3.5-turbo-1106:buildsync:raw-toolcall:9jNxpQ5d", temperature=0.3,
                 openai_api_key=OPEN_API_KEY, streaming=True, verbose=True)  # callbacks=[CallbackHandler()] callbacks=[StreamingStdOutCallbackHandler()

examples = [
    HumanMessage(
        "Build a 1 storey building", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "create_building_storey", "args": {
                "building_storeys_amount": 1}, "id": "1"}
        ],
    ),
    ToolMessage("Created building storeys", tool_call_id="1"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "create_floor", "args": {
            "storey_n": 1}, "id": "2"}],
    ),
    ToolMessage("Created floor on storey 1", tool_call_id="2"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "create_wall", "args": {
            "storey_n": 1, "start_coord": "0,0,0", "end_coord": "0,100,0", "height": 30}, "id": "3"}],
    ),
    ToolMessage("Created 1/4 walls on storey 1", tool_call_id="3"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "create_wall", "args": {
            "storey_n": 1, "start_coord": "0,0,0", "end_coord": "100,0,0", "height": 30}, "id": "3"}],
    ),
    ToolMessage("Created 2/4 walls on storey 1", tool_call_id="3"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "create_wall", "args": {
            "storey_n": 1, "start_coord": "100,0,0", "end_coord": "100,100,0", "height": 30}, "id": "3"}],
    ),
    ToolMessage("Created 3/4 walls on storey 1", tool_call_id="3"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "create_wall", "args": {
            "storey_n": 1, "start_coord": "0,100,0", "end_coord": "100,100,0", "height": 30}, "id": "3"}],
    ),
    ToolMessage("Created 4/4 walls on storey 1", tool_call_id="3"),
    AIMessage(
        "Created a one storey building",
        name="example_assistant",
    ),
    HumanMessage
]

system_template = """You are an AI BIM modeller. Provided with creation and editing tasks for IFC files, you will respond to user queries and invoke
     relevant tools to complete the user's request. Multiple tools may be required to complete the one request.

     To show your thinking step by step:
     1. Determine if multiple tools are needed here
     2. What tools are needed and in what order.

     Then, REMEMBER to invoke the tools.

     If the prompt is more complex, like "create 2 storey building", try to break it down into the building's constituents: storeys, floors, walls. Then, consider what order you should call them in.

     Do not ask follow up questions. If the user's answer is not clear, use default parameters.

     Keep your answer to 20 words.
     """

prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    # *examples,
    MessagesPlaceholder(variable_name=MEMORY_KEY),
    ("human", "{input}. Show your thinking step by step."),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

llm_with_tools = llm.bind_tools(tools)

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_tool_messages(
            x["intermediate_steps"]
        ),
        "chat_history": lambda x: x["chat_history"],
    }
    | prompt
    | llm_with_tools
    | OpenAIToolsAgentOutputParser()
)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


async def chat_gpt_streamer(query: str, unique_hash: str):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    aiContentResult = ""
    async for event in agent_executor.astream_events({"input": query, "chat_history": chat_history}, version="v1"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                print(f"content: {content}")
                # Ensure that the emit is done in the correct event loop context
                asyncio.run_coroutine_threadsafe(
                    sio.emit('aiAction', {'word': content, 'hash': unique_hash}), loop)
            aiContentResult += (content)
        elif kind == "on_tool_start":
            inputs = event['data'].get('input')
            if (inputs):
                content = {
                    'word': f"Calling tool: {event['name']} with inputs: {inputs}\n", 'hash': unique_hash}
            else:
                content = {
                    'word': f"Calling tool: {event['name']}", 'hash': unique_hash}
            asyncio.run_coroutine_threadsafe(
                sio.emit('toolStart', content), loop)
        elif kind == "on_tool_end":
            print(f"Done tool: {event['name']}")
            print(f"Tool output was: {event['data'].get('output')}")
            print("--")

    chat_history.extend(
        [
            HumanMessage(content=query),
            AIMessage(content=aiContentResult),
        ]
    )


if __name__ == '__main__':
    # print("Registered tools:")
    # for tool_func in tools:
    #     print(f"Tool ID: {tool_func.name}")

    # async def main():
    #     async for event in agent_executor.astream_events(
    #             {"input": "Create a square 20x20 feet structure on level 1. ", "chat_history": [], "id": "1"}, version="v1"):
    #         print(event)

    # asyncio.run(main())
    async def main():
        res = agent_executor.invoke(
            {"input": "Create a square 20x20 feet structure on level 1. ", "chat_history": []})
    asyncio.run(main())
