import socketio
from aiohttp import web
import os
from dotenv import load_dotenv
import asyncio
import sys
import requests
import asyncio
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi import Header, HTTPException
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from socket_server import sio
from agent_graph import model_streamer
from fastapi.staticfiles import StaticFiles
from tools_graph import create_on_start
import hashlib
import time
import logging

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


OPEN_API_KEY = os.getenv('OPEN_API_KEY')

## ---- WEBSOCKET SETUP ----- ##

# Create a Socket.IO server
app = FastAPI()
# Set up CORS middleware for FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://34.44.107.80:5173",
                   "http://localhost:3001",
                   "http://localhost:3000",
                   "https://client-next-supabase.vercel.app",
                   "https://buildsync-playground.app"],  # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
app.mount("/public", StaticFiles(directory="public"), name="public")
# Create a Socket.IO server allowing CORS for specific origins
combined_asgi_app = socketio.ASGIApp(sio, app)


@ sio.event
async def DOMContentLoaded(sid):
    await create_on_start()
    print("Created session start load with sid", sid)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), sid: str = Header(None)):
    print('Upload file received')
    try:
        logger.info(f"Starting upload for file: {file.filename}")

        # Save the uploaded file
        file_location = f"tmp/{file.filename}"
        logger.info(f"Saving file to: {file_location}")
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info("File saved successfully")

        logger.info(f"Emitting backgroundModelChange event. SID: {sid}")
        if sid:
            print('sid found')
            await sio.emit('backgroundModelChange', {'userId': sid, 'file_name': file_location}, skip_sid=sid)
        else:
            await sio.emit('backgroundModelChange', {'file_name': file_location})
        logger.info("Event emitted successfully")

        return JSONResponse(status_code=200, content={"message": "File uploaded successfully"})
    except Exception as e:
        logger.exception(
            f"An error occurred while uploading the file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"File upload failed: {str(e)}")


# Dictionary containing prompt outputs for specific commands
prompt_output_dict = {
    "/create new": """""",
    "/create an L-shaped building 3x6 grid of 12ft columns spaced 18ft apart, with 2x2 wing": """""",
    "/connect all tops of columns with beams in both directions.": """""",
    "/add floors and replicate this structure to second floor": """""",
    "/add another 3 stories & copy the 3x6 wing up to these new levels": """""",
    "/add roof and walls around structure. Let the roof have a 10ft overhang at the bottom of the L-shape": """""",
    "/add two kickers to support the overhang. They should connect to the overhang at 2ft away from the edge and be supported at the bottom of level 4.": """""",
    "/create this image as BIM": """""",
}



@ sio.event
async def userAction(sid, data):
    # Log that a user action has been received
    print('User Action received')
    # Emit the user action event to all connected clients
    await sio.emit('userAction', data)
    # Extract the user command from the received data
    user_command = data['message']
    print('User command:', user_command)
    # Check if the user command starts with a '/'
    if user_command.startswith('/'):
        # Get the first three words of the user command
        first_three_words = ' '.join(user_command.split()[:3])

        # Check if the first three words exactly match any key in prompt_output_dict
        matching_prompt = next((key for key in prompt_output_dict if key.startswith(first_three_words) and len(
            key.split()) >= 3 and ' '.join(key.split()[:3]) == first_three_words), None)

        # If a matching prompt is found
        if matching_prompt:
            # Use the matching prompt's output as the agent's prompt
            agent_prompt = user_command + \
                "YOU ARE IN DEMO MODE, USE DEMO FUNCTIONS WHERE NECESSARY."

            if "image" in matching_prompt:
                agent_prompt = user_command + \
                    "If there's no image, pretend there is. ONLY USE FUNCTIONS THAT START WITH 'image_to_bim'"
            # Generate a unique string using the agent's prompt and current time
            unique_string = f"{agent_prompt}-{time.time()}"
            # Generate a unique hash from the unique string
            unique_hash = "ai-" + \
                hashlib.sha256(unique_string.encode()).hexdigest()
            # Log the generated unique hash
            print(f"Generated unique hash: {unique_hash}")
            # Log the generated unique string
            print(f"Generated unique string: {unique_string}")
            # Emit the aiActionStart event with the unique hash
            await sio.emit('aiActionStart', {'hash':  unique_hash})
            # Call the model_streamer function with the data and unique hash
            await model_streamer(str(data), unique_hash)
            # Emit the aiActionEnd event with the unique hash
            await sio.emit('aiActionEnd', {'hash': unique_hash})
        else:
            # If no matching prompt is found, use the original user command
            # Generate a unique string using the user command and current time
            unique_string = f"{user_command}-{time.time()}"
            # Generate a unique hash from the unique string
            unique_hash = "ai-" + \
                hashlib.sha256(unique_string.encode()).hexdigest()
            # Log the generated unique hash
            print(f"Generated unique hash: {unique_hash}")

            # Emit the aiActionStart event with the unique hash
            await sio.emit('aiActionStart', {'hash':  unique_hash})
            # Call the model_streamer function with the data and unique hash
            await model_streamer(sid, str(data), unique_hash)
            # Emit the aiActionEnd event with the unique hash
            await sio.emit('aiActionEnd', {'hash': unique_hash})


@ sio.event
async def fileChange(sid, data):
    print('File change received:', data)
    file_name = data['file_name']
    print(f"Emitting fileChange event. SID: {sid}, File Name: {file_name}")
    await sio.emit('fileChange', {'userId': sid, 'file_name': file_name})


@ app.get("/")
async def health_check():
    print('Server is running')
    return {"message": "Server is running"}


async def send_agent_response(message):
    await sio.emit('agentResponse', {'message': message})


def perform_action():
    # url = 'http://127.0.0.1:8080/chat'
    # data = {'text': 'value'}
    # response = requests.post(url, json=data)
    # print(response.json())
    print('Perform action has been disabled')


def check_status():
    # url = 'http://127.0.0.1:8080/health'
    # response = requests.get(url)
    # print(response.json())
    print('Health check has been disabled')


if __name__ == '__main__':
    check_status()
    perform_action()
    # streaming_answer = agent_executor.invoke({"input": "Create a square 20x20 feet structure on level 1. Show your thinking step by step but be concise."})
    # asyncio.run(start())
    uvicorn.run("server:combined_asgi_app",
                host="localhost", port=8000, reload=True)
