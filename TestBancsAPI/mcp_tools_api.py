import os
import httpx
import logging
#from fastmcp import FastMCP
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional
from collections import defaultdict
import asyncio
import json
import re
logger = logging.getLogger(__name__)
mcp = FastMCP("Bancs API Json")
# API Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://demoapps.tcsbancs.com/Core")
API_KEY = os.getenv("API_KEY")
TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
# API Catalog - Generated from OpenAPI spec
API_CATALOG = {
 "create_acnt_actv_using_post": {
        "method": "POST",
        "path": "/accountManagement/account",
        "description": "Create Account for a given customer",
        "tags": ["AccountManagement"],
        "deprecated": False,
        "auth_required": False,
        "operation_id": "Create Savings Accpunt ",
        "parameters": [
            {
                "name": "request_body",
                "type": "any",
                "location": "body",
                "required": True,
                "description": "input"
            }
            
        ]
    },
     "cbpetget_account_balance_using_get": {
        "method": "GET",
        "path": "/accountManagement/account/balanceDetails/{accountReference}",
        "description": "Fetch Account Balance Details",
        "tags": ["AccountManagement"],
        "deprecated": False,
        "auth_required": False,
        "operation_id": "CBPETGetAccountBalanceUsingGET",
        "parameters": [
            
            {
                "name": "accountReference",
                "type": "string",
                "location": "path",
                "required": True,
                "description": "Enter the Account Reference"
            }
            
        ]
    }    
 }

# Build tag-based index
TAG_INDEX = defaultdict(list)
for endpoint_name, endpoint_info in API_CATALOG.items():
    for tag in endpoint_info.get("tags", ["untagged"]):
        TAG_INDEX[tag.lower()].append(endpoint_name)

# Build operation ID index
OPERATION_ID_INDEX = {}
for endpoint_name, endpoint_info in API_CATALOG.items():
    if "operation_id" in endpoint_info:
        OPERATION_ID_INDEX[endpoint_info["operation_id"]] = endpoint_name

async def make_api_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Make authenticated request to API."""
    url = f"{BASE_URL.rstrip('/')}{path}"
    
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
   
    if headers:
        request_headers.update(headers)
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            logger.debug(f"API {method} {url}")
            logger.debug(f"Headers: {request_headers}")
            logger.debug(f"Params: {params}")
            logger.debug(f"Data: {data}")
            
            response = await client.request(
                method=method.upper(),
                url=url,
                params=params,
                json=data if data else None,
                headers=request_headers
            )
            
            response.raise_for_status()
            
            # Handle different response types
            content_type = response.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                return response.json()
            else:
                return {"data": response.text, "content_type": content_type}
                
        except httpx.HTTPStatusError as e:
            logger.error(f"API error {e.response.status_code}: {e.response.text}")
            error_detail = {
                "error": True,
                "status_code": e.response.status_code,
                "method": method,
                "url": url,
                "message": "Unknown error"
            }
            
            try:
                error_data = e.response.json()
                error_detail["error_details"] = error_data
                error_detail["message"] = error_data.get("message", error_data.get("error", str(error_data)))
            except:
                error_detail["message"] = e.response.text or str(e)
            
            # Add request details for debugging
            if logger.isEnabledFor(logging.DEBUG):
                error_detail["request"] = {
                    "headers": dict(request_headers),
                    "params": params,
                    "data": data
                }
            
            return error_detail
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "error": True,
                "message": str(e)
            }


def sanitize_param_name(name: str) -> str:
    """Convert parameter name to Python-friendly format."""
    # Replace spaces and hyphens with underscores
    name = name.replace(' ', '_').replace('-', '_')
    # Convert to lowercase
    name = name.lower()
    # Remove any other special characters
    name = re.sub(r'[^a-z0-9_]', '', name)
    # Ensure it doesn't start with a number
    if name and name[0].isdigit():
        name = f'param_{name}'
    return name

def register_bancs_tools(mcp: FastMCP):
    """Register all API tools with FastMCP server."""
    registered_funcs = []
    # Register API discovery tools
    @mcp.tool()
    async def list_api_endpoints(
        search_query: Optional[str] = None,
        tag: Optional[str] = None,
        method: Optional[str] = None,
        include_deprecated: bool = False
    ) -> Dict[str, Any]:
        """Search and list available API endpoints.
        
        Discover available operations by searching through:
        - search_query: Text to search in names, descriptions, or paths
        - tag: Filter by API domain/tag (e.g., "counterparties", "loans", "accounts")
        - method: Filter by HTTP method (GET, POST, PUT, DELETE, etc.)
        - include_deprecated: Include deprecated endpoints
        
        Returns grouped endpoints with descriptions and metadata.
        """
        results = []
        
        # Filter by tag
        if tag:
            endpoint_names = TAG_INDEX.get(tag.lower(), [])
        else:
            endpoint_names = list(API_CATALOG.keys())
        
        # Apply filters
        for name in endpoint_names:
            endpoint = API_CATALOG[name]
            
            # Skip deprecated if not requested
            if endpoint.get("deprecated") and not include_deprecated:
                continue
            
            # Filter by method
            if method and endpoint["method"] != method.upper():
                continue
            
            # Search filter
            if search_query:
                search_lower = search_query.lower()
                if not any(search_lower in text.lower() for text in [
                    name,
                    endpoint["description"],
                    endpoint["path"],
                    ' '.join(endpoint["tags"])
                ]):
                    continue
            
            results.append({
                "name": name,
                "method": endpoint["method"],
                "path": endpoint["path"],
                "description": endpoint["description"],
                "tags": endpoint["tags"],
                "deprecated": endpoint.get("deprecated", False),
                "auth_required": endpoint.get("auth_required", True),
                "parameter_count": len(endpoint["parameters"])
            })
        
        # Sort results
        results.sort(key=lambda x: (x["deprecated"], x["name"]))
        
        # Group by tags if no specific tag was requested
        if not tag and results:
            by_tag = defaultdict(list)
            for result in results:
                for t in result["tags"] or ["untagged"]:
                    by_tag[t].append(result)
            
            return {
                "total_endpoints": len(results),
                "endpoints_by_tag": dict(by_tag),
                "available_tags": sorted(list(TAG_INDEX.keys()))
            }
        
        return {
            "total_endpoints": len(results),
            "endpoints": results,
            "search_criteria": {
                "query": search_query,
                "tag": tag,
                "method": method,
                "include_deprecated": include_deprecated
            }
        }
   # registered_funcs.append(list_api_endpoints)
    @mcp.tool()
    async def get_api_endpoint_schema(
        endpoint_name: Optional[str] = None,
        operation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed schema for a specific API endpoint.
        
        Retrieve by either:
        - endpoint_name: The tool name (from list_api_endpoints)
        - operation_id: The original OpenAPI operationId
        
        Returns complete parameter schemas, types, constraints, and examples.
        """
        # Resolve endpoint name
        if operation_id and operation_id in OPERATION_ID_INDEX:
            endpoint_name = OPERATION_ID_INDEX[operation_id]
        
        if not endpoint_name or endpoint_name not in API_CATALOG:
            suggestions = []
            if endpoint_name:
                # Find similar names
                search_lower = endpoint_name.lower()
                suggestions = [
                    name for name in API_CATALOG.keys()
                    if search_lower in name.lower()
                ][:5]
            
            return {
                "error": True,
                "message": f"Endpoint '{endpoint_name or operation_id}' not found",
                "suggestions": suggestions or list(API_CATALOG.keys())[:10]
            }
        
        endpoint = API_CATALOG[endpoint_name]
        
        # Build parameter details with examples
        parameter_details = []
        for param in endpoint["parameters"]:
            param_detail = {
                "name": param["name"],
                "type": param["type"],
                "location": param["location"],
                "required": param["required"],
                "description": param.get("description", "")
            }
            if "example" in param:
                param_detail["example"] = param["example"]
            parameter_details.append(param_detail)
        
        # Build example call
        example_params = {}
        for param in endpoint["parameters"]:
            if "example" in param:
                example_params[param["name"]] = param["example"]
            elif param["required"]:
                # Generate a placeholder for required params without examples
                example_params[param["name"]] = f"<{param['type']}>"
        
        return {
            "endpoint_name": endpoint_name,
            "operation_id": endpoint.get("operation_id"),
            "method": endpoint["method"],
            "path": endpoint["path"],
            "description": endpoint["description"],
            "tags": endpoint["tags"],
            "deprecated": endpoint.get("deprecated", False),
            "auth_required": endpoint.get("auth_required", True),
            "parameters": parameter_details,
            "example_usage": {
                "endpoint": endpoint_name,
                "params": example_params
            }
        }
    #registered_funcs.append(get_api_endpoint_schema)
    @mcp.tool()
    async def invoke_api_endpoint(
        endpoint_name: Optional[str] = None,
        operation_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Dynamically invoke any API endpoint.
        
        Call endpoints discovered through list_api_endpoints:
        - endpoint_name: The tool name
        - operation_id: The original OpenAPI operationId
        - params: Parameters to pass (use get_api_endpoint_schema for requirements)
        
        Validates parameters and executes the API call.
        """
        # Resolve endpoint name
        if operation_id and operation_id in OPERATION_ID_INDEX:
            endpoint_name = OPERATION_ID_INDEX[operation_id]
        
        if not endpoint_name or endpoint_name not in API_CATALOG:
            return {
                "error": True,
                "message": f"Endpoint '{endpoint_name or operation_id}' not found",
                "hint": "Use list_api_endpoints to discover available endpoints"
            }
        
        endpoint = API_CATALOG[endpoint_name]
        params = params or {}
        
        # Validate required parameters
        missing_required = []
        for param_spec in endpoint["parameters"]:
            if param_spec["required"] and param_spec["name"] not in params:
                missing_required.append(param_spec["name"])
        
        if missing_required:
            return {
                "error": True,
                "message": "Missing required parameters",
                "missing_parameters": missing_required,
                "endpoint_schema": {
                    "method": endpoint["method"],
                    "path": endpoint["path"],
                    "parameters": endpoint["parameters"]
                }
            }
        
        # Separate parameters by location
        path_params = {}
        query_params = {}
        body_params = {}
        header_params = {}
        
        for param_spec in endpoint["parameters"]:
            param_name = param_spec["name"]
            if param_name in params:
                value = params[param_name]
                
                # Validate union types if present
                if "possible_types" in param_spec and value is not None:
                    # For path parameters with union types, ensure proper formatting
                    if param_spec["location"] == "path":
                        # Convert to string for path parameters
                        value = str(value)
                        
                        # Apply pattern validation if specified
                        if "pattern" in param_spec:
                            import re
                            if not re.match(param_spec["pattern"], value):
                                return {
                                    "error": True,
                                    "message": f"Path parameter '{param_name}' does not match required pattern",
                                    "pattern": param_spec["pattern"],
                                    "value": value
                                }
                
                if param_spec["location"] == "path":
                    path_params[param_name] = value
                elif param_spec["location"] == "query":
                    query_params[param_name] = value
                elif param_spec["location"] == "body":
                    body_params[param_name] = value
                elif param_spec["location"] == "header":
                    header_params[param_name] = value
        
        # Build path with parameters
        path = endpoint["path"]
        for param_name, param_value in path_params.items():
            path = path.replace(f"{{param_name}}", str(param_value))
        
        # Make request
        return await make_api_request(
            method=endpoint["method"],
            path=path,
            params=query_params if query_params else None,
            data=body_params if body_params else None,
            headers=header_params if header_params else None
        )
    #registered_funcs.append(get_api_endpoint_schema)
    @mcp.tool()
    async def create_acnt_actv_using_post(
        request_body:Dict[str, Any] ,  # createAccountResource,
        entity: Optional[str] = None,
        languagecode: Optional[int] = None,
        userid: Optional[int] = None
    ) -> Dict[str, Any]:
        """
            Create Account
    Sends a POST request to /accountManagement/account to create an account for a customer.
    Required:
    - request_body: JSON body with account creation details
    Optional Headers:
    Headers:
    - entity: string
        - entity: string
           entity
    - languageCode: integer
        - languageCode: integer
          languageCode
    - userId: integer
        - userId: integer
          userId
      
    """
    
       
        # Prepare request data
       
        # Single body parameter - send directly
        data = request_body if request_body is not None else {}
     
        # Prepare query parameters
        params = {}
      
        # Replace path parameters in URL
        path = "/accountManagement/account"
      
        # Prepare headers
        headers = {}
        if entity is not None:
            headers["entity"] = str(entity)
        if languagecode is not None:
            headers["languageCode"] = str(languagecode)
        if userid is not None:
            headers["userId"] = str(userid)
        
        return await make_api_request(
            "POST", 
            path, 
            data=data, 
            params=params if params else None, 
            headers=headers if headers else None
        )
    registered_funcs.append(create_acnt_actv_using_post)
  
    @mcp.tool()
    async def cbpetget_account_balance_using_get(
            accountreference: str,
            accesstoken: Optional[str] = None,
            channeltype: Optional[int] = None,
            co_relationid: Optional[int] = None,
            initiatingsystem: Optional[str] = None,
            servicemode: Optional[int] = None,
            uuidseqno: Optional[int] = None,
            entity: Optional[str] = None,
            languagecode: Optional[int] = None,
            referenceid: Optional[str] = None,
            userid: Optional[int] = None
        ) -> Dict[str, Any]:
            """
            Fetch Account Balance Details
            
            Generated from: GET /accountManagement/account/balanceDetails/{accountReference}
            Source: swagger_2_0
            Operation ID: CBPETGetAccountBalanceUsingGET
            
            
            Authentication: Not required
            
            Parameters:
            - accountReference: string (required)
              Enter the Account Reference
            
            
            
            Headers:
            - Accesstoken: string
              Authorization token for identification of the caller
            - ChannelType: integer
              Channel identifier from where the TXN has originated (Internet, Mobile, ATM, Branch Channel )
            - Co-Relationid: integer
              Unique ID for the service invoked, will be set by the TXN system
            - InitiatingSystem: string
              Indicating the initiated system
            - ServiceMode: integer
              Used for branch channel to indicate the type of customer
            - UUIDSeqNo: integer
              UUID Sequence Number
            - entity: string
              entity
            - languageCode: integer
              languageCode
            - referenceId: string
              Place holder for Token based authentication
            - userId: integer
              userId
            
            
            """
            
            
            # Prepare query parameters
            params = {}
            
            
            # Replace path parameters in URL
            path = "/accountManagement/account/balanceDetails/{accountReference}"
            if accountreference is not None:
                path = path.replace("{accountReference}", str(accountreference))
            
            
            # Prepare headers
            headers = {}
            if accesstoken is not None:
                headers["Accesstoken"] = str(accesstoken)
            if channeltype is not None:
                headers["ChannelType"] = str(channeltype)
            if co_relationid is not None:
                headers["Co-Relationid"] = str(co_relationid)
            if initiatingsystem is not None:
                headers["InitiatingSystem"] = str(initiatingsystem)
            if servicemode is not None:
                headers["ServiceMode"] = str(servicemode)
            if uuidseqno is not None:
                headers["UUIDSeqNo"] = str(uuidseqno)
            if entity is not None:
                headers["entity"] = str(entity)
            if languagecode is not None:
                headers["languageCode"] = str(languagecode)
            if referenceid is not None:
                headers["referenceId"] = str(referenceid)
            if userid is not None:
                headers["userId"] = str(userid)
            
            
            return await make_api_request(
                "GET", 
                path, 
                
                params=params if params else None, 
                headers=headers if headers else None
            )
    registered_funcs.append(cbpetget_account_balance_using_get)
    return registered_funcs

if __name__ == "__main__":
    mcp.run(transport="stdio")