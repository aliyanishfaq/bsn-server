import ifcopenshell
import json
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.tools.retriever import create_retriever_tool
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def entityToDict(entity, id_objects):
    """
    Converts an IFC entity to a dictionary representation, including its attributes and nested entities.
    """
    ref = {
        "Type": entity.is_a()
    }
    attr_dict = entity.__dict__

    # check for globalid
    if "GlobalId" in attr_dict:
        ref["ref"] = attr_dict["GlobalId"]
        if not attr_dict["GlobalId"] in id_objects:
            d = {
                "Type": entity.is_a()
            }

            for i in range(0, len(entity)):
                attr = entity.attribute_name(i)
                if attr in attr_dict:
                    if not attr == "OwnerHistory":
                        jsonValue = getEntityValue(attr_dict[attr], id_objects)
                        if jsonValue:
                            d[attr] = jsonValue
                        if attr_dict[attr] == None:
                            continue
                        elif isinstance(attr_dict[attr], ifcopenshell.entity_instance):
                            d[attr] = entityToDict(attr_dict[attr], id_objects)
                        elif isinstance(attr_dict[attr], tuple):
                            subEnts = []
                            for subEntity in attr_dict[attr]:
                                if isinstance(subEntity, ifcopenshell.entity_instance):
                                    subEntJson = entityToDict(subEntity)
                                    if subEntJson:
                                        subEnts.append(subEntJson)
                                else:
                                    subEnts.append(subEntity)
                            if len(subEnts) > 0:
                                d[attr] = subEnts
                        else:
                            d[attr] = attr_dict[attr]
            id_objects[attr_dict["GlobalId"]] = d
        return ref
    else:
        d = {
            "Type": entity.is_a()
        }

        for i in range(0, len(entity)):
            attr = entity.attribute_name(i)
            if attr in attr_dict:
                if not attr == "OwnerHistory":
                    jsonValue = getEntityValue(attr_dict[attr], id_objects)
                    if jsonValue:
                        d[attr] = jsonValue
                    if attr_dict[attr] == None:
                        continue
                    elif isinstance(attr_dict[attr], ifcopenshell.entity_instance):
                        d[attr] = entityToDict(attr_dict[attr], id_objects)
                    elif isinstance(attr_dict[attr], tuple):
                        subEnts = []
                        for subEntity in attr_dict[attr]:
                            if isinstance(subEntity, ifcopenshell.entity_instance):
                                # subEnts.append(None)
                                subEntJson = entityToDict(
                                    subEntity, id_objects)
                                if subEntJson:
                                    subEnts.append(subEntJson)
                            else:
                                subEnts.append(subEntity)
                        if len(subEnts) > 0:
                            d[attr] = subEnts
                    else:
                        d[attr] = attr_dict[attr]
        return d


def getEntityValue(value, id_objects):
    """
    Retrieves the JSON-compatible value of an IFC entity attribute, handling nested entities and tuples.
    """
    if value == None:
        jsonValue = None
    elif isinstance(value, ifcopenshell.entity_instance):
        jsonValue = entityToDict(value, id_objects)
    elif isinstance(value, tuple):
        jsonValue = None
        subEnts = []
        for subEntity in value:
            subEnts.append(getEntityValue(subEntity, id_objects))
        jsonValue = subEnts
    else:
        jsonValue = value
    return jsonValue


def parse_ifc():
    """
    Parses an IFC file, converts relevant entities to JSON, and creates a retriever tool for searching the IFC data.
    """
    id_objects = {}
    jsonObjects = []
    ifc_file = ifcopenshell.open('tmp/canvas.ifc')
    entityIter = iter(ifc_file)
    for entity in entityIter:
        if entity.is_a() in ['IfcWallStandardCase', 'IfcWall', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcRoof', 'IfcBuilding', 'IfcDoor', 'IfcBuildingStorey', 'IfcFloor']:
            entityToDict(entity, id_objects)
    for key in id_objects:
        jsonObjects.append(id_objects[key])
    with open('tmp/canvas.json', 'w') as outfile:
        json.dump(jsonObjects, outfile, indent=4)
    loader = TextLoader('tmp/canvas.json')
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    vectorstore = Chroma.from_documents(
        documents=splits, embedding=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY))
    retriever = vectorstore.as_retriever()
    retriever_tool = create_retriever_tool(
        retriever, "search_canvas", "Searches the existing IFC file for the relevant objects and returns the JSON representation of the relevant objects")
    return retriever_tool


def parse_ifc_objects(objects: list) -> list:
    """
    Parses a list of IFC objects to JSON, containing all relevant information about the IFC objects
    """
    id_objects = {}
    jsonObjects = []
    for object in objects:
        entityToDict(object, id_objects)
    for key in id_objects:
        jsonObjects.append(id_objects[key])
    return jsonObjects
