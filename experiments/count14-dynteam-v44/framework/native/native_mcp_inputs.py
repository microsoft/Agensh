"""Pinned full native tools/list metadata; never executes public binaries.

The three-field declaration summary omits native `_meta`, annotations and output
schemas and is NOT an interchangeable protocol listing. Tool authorization still
requires an independently compiled fixed-scope McpPolicy; this loader grants none.
"""
from pathlib import Path
import copy
from common import need,hash_file,strict
BASE=Path(__file__).resolve().parent
ROOT=BASE/'native-mcp-public-metadata'
def load_native_tools(purpose):
    need(purpose in('gitea','mattermost'),'MCP_NATIVE_INPUT_PURPOSE')
    origin=strict((BASE/'NATIVE_MCP_DECLARATIONS_CONSUMED.json').read_bytes());row=origin['servers'][purpose];path=ROOT/(purpose+'-wire.json')
    need(hash_file(path)==row['wire_pin'],'MCP_NATIVE_WIRE_PIN_CHANGED');body=strict(path.read_bytes())
    need(body['binary_sha256']==row['binary_sha256']and body['source_image_id']==row['source_image_id']and body['serverInfo']==row['protocol_server_info'],'MCP_NATIVE_WIRE_ORIGIN')
    need(body['tools_call_sent']==0 and body['child_exit']==0 and len(body['tools'])==row['tool_count']==body['tool_count'],'MCP_NATIVE_DECLARATION_NOT_BUSINESS_CALL')
    return copy.deepcopy(body['tools'])
