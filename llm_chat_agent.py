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
#register_bancs_tools(mcp)  
tool_fns = register_bancs_tools(mcp)

with open("C:/Users/AnithaS/Learning/ice_breaker_test/TestBancsAPI/api_examples.json") as f:
    example_bodies = json.load(f)
# Step 1: Load example JSON schema for request bodies
def attach_examples_to_tool_doc(tool_fn, tool_name):
    example = example_bodies.get(tool_name, {}).get("request_body")
    if example:
        example_str = json.dumps(example, indent=2)
        if tool_fn.__doc__:
            tool_fn.__doc__ += f"\n\nExample request_body:\n{example_str}"
        else:
            tool_fn.__doc__ = f"Example request_body:\n{example_str}"
# Step 3: Inject examples into tool docstrings
for fn in tool_fns:
    attach_examples_to_tool_doc(fn, fn.__name__)
# Register tools into FastMCP server

# Get tools as a list (not a dict)
mcp_tools = asyncio.run(mcp.list_tools())

# Convert to LangChain tools using Tool.from_function
langchain_tools = [
    Tool.from_function(
        func=fn,
        name=fn.__name__,
        description=fn.__doc__ or "No description."
    )
    for fn in tool_fns
]
#create prompt from mcp_tools prompt
def format_tool_functions_for_prompt(tool_fns):
    tool_descriptions = []
    tool_names = []

    for fn in tool_fns:
        name = fn.__name__
        doc = fn.__doc__ or "No description."
        tool_names.append(name)

        # Try to extract function signature (parameter names)
        try:
            import inspect
            sig = inspect.signature(fn)
            param_names = ", ".join(sig.parameters.keys())
        except Exception:
            param_names = "unknown"

        tool_descriptions.append(f"{name}: {doc.strip()}\nInputs: {param_names}")

    tools_str = "\n\n".join(tool_descriptions)
    tool_names_str = ", ".join(tool_names)

    return tools_str, tool_names_str
#tools_str, tool_names_str = format_tool_functions_for_prompt(tool_fns)

from langchain_core.prompts import PromptTemplate

prompt_template = """
Answer the following question as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
{agent_scratchpad}
"""

# Format tool prompt
tools_str, tool_names_str = format_tool_functions_for_prompt(tool_fns)
print("Tools for prompt:", tools_str)
print("Tool names for prompt:", tool_names_str)
# Create LangChain PromptTemplate with filled-in tool metadata
prompt = PromptTemplate.from_template(prompt_template).partial(
    tools=tools_str,
    tool_names=tool_names_str
)


#prompt = hub.pull("hwchase17/react")


# Set up LLM (ChatOllama running locally or use OpenAI)
llm = ChatOllama(model="llama3", temperature=0, max_tokens=1000)
# Create agent
agent = create_react_agent(llm=llm, tools=langchain_tools,prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=langchain_tools, verbose=True)