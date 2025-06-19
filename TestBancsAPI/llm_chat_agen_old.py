import os
from dotenv import load_dotenv  # Load environment variables
import asyncio
import json
import streamlit as st
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import Tool
from langchain_community.chat_models import ChatOllama
from langchain import hub

from typing import Type
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from langchain.tools import BaseTool
from langchain_core.output_parsers import JsonOutputParser
from langchain.agents import AgentExecutor, create_react_agent
from typing import List, Tuple, Type

load_dotenv()  # Load environment variables from .env file

from mcp_tools_api import register_bancs_tools, mcp

# Register tools into FastMCP server
register_bancs_tools(mcp)
#REGISTERED_TOOL_MAP = {}

# Get tools as a list (not a dict)
langchain_tools  = asyncio.run(mcp.list_tools())
# Convert to LangChain tools by extracting the underlying function
langchain_tools = [
    Tool.from_function(
        func=tool.func,  # ✅ This is the real Python function
        name=tool.name,
        description=tool.description or "No description"
    )
    for tool in mcp_tools
]
for t in langchain_tools:
    print(type(t), getattr(t, '__name__', None))
# Convert to LangChain Tools
#langchain_tools = [
    #Tool.from_function(
     #   func=tool,
      #  name=tool.__name__,
       # description=tool.__doc__ or "No description provided."
    #)
    #for tool in tools_list
#]
# Convert FastMCP tools to LangChain tools
#langchain_tools = [Tool.from_function(f) for f in mcp.list_tools().values()]
#def capture_registered_tools():
 #   global REGISTERED_TOOL_MAP
  #  REGISTERED_TOOL_MAP = {tool.name: tool for tool in mcp._tools.values()} if hasattr(mcp, '_tools') else {}

#capture_registered_tools()

# Set up LLM (ChatOllama running locally or use OpenAI)
llm = ChatOllama(model="llama3", temperature=0, max_tokens=1000) 
prompt = hub.pull("hwchase17/react")
# Create agent
agent = create_react_agent(llm=llm, tools=langchain_tools,prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=langchain_tools, verbose=True)
