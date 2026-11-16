"""Compile original three MCP entries to fixed per-worker IPC transports.

Real tool metadata/scopes must already be qualified by the trusted owner. Native
services/notice executables and credentials remain host-side. This returns a
PRIVATE worker config (contains capabilities) and separate metadata-only pins;
it does not start services or claim native Gitea/Mattermost qualification.
"""
from pathlib import Path
import hashlib,json
from common import need,integer,digest,hash_file
from native_mcp_policy import McpPolicy,native_denials
from native_mcp_overlay import BASE,PUBLIC
PURPOSES=('gitea','mattermost','board')
CLIENT='/opt/count14/mcp_uds_client.py'
PYTHON='/usr/bin/python3'

def build_worker_config(policies,sockets,*,timeout_ms):
    need(type(policies)is dict and set(policies)==set(PURPOSES)and type(sockets)is dict and set(sockets)==set(PURPOSES),'MCP_COMPLETE_NATIVE_SERVER_SET')
    integer(timeout_ms,'MCP_NATIVE_TIMEOUT_REQUIRED',1)
    pins={row['path']:row['sha256']for row in json.loads((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_text())['sources']}
    originals={}
    for name in ('agent/config/mcp.json.tmpl','agent/config/copilot-deny-tools.json'):
        raw=(PUBLIC/name).read_bytes();need(hashlib.sha256(raw).hexdigest()==pins[name],'MCP_NATIVE_CONFIG_SOURCE_CHANGED');originals[name]=raw
    native=json.loads(originals['agent/config/mcp.json.tmpl']);denials=json.loads(originals['agent/config/copilot-deny-tools.json'])
    need(set(native)=={'mcpServers'}and set(native['mcpServers'])==set(PURPOSES),'MCP_NATIVE_CONFIG_SHAPE')
    config={'mcpServers':{}};identities=[];paths=[]
    for purpose in PURPOSES:
        policy=policies[purpose];need(isinstance(policy,McpPolicy)and policy.identity.purpose==purpose,'MCP_POLICY_PURPOSE')
        identity=policy.identity;identities.append((identity.trajectory,identity.role,identity.generation,identity.agent,identity.uid,identity.pid_namespace_inode))
        need(policy.deny==native_denials(purpose,denials),'MCP_ORIGINAL_CLI_AND_BROKER_DENIALS_REQUIRED')
        path=Path(sockets[purpose]);need(path.is_absolute()and path.resolve()==path,'MCP_FIXED_CANONICAL_WORKER_SOCKET');paths.append(str(path))
        # No worker-visible service URL/token/exec/host/general-network proxy.
        config['mcpServers'][purpose]={'type':'stdio','timeout':str(timeout_ms),'command':PYTHON,'args':['-B',CLIENT],'env':{'AGENSH_MCP_SOCKET':str(path),'AGENSH_MCP_CAPABILITY':identity.capability}}
    need(len(set(identities))==1 and len(set(paths))==3,'MCP_WORKER_OR_ENDPOINT_SCOPE_MISMATCH')
    receipt={'schema':'agensh-native-mcp-worker-config-v1','native_template_sha256':pins['agent/config/mcp.json.tmpl'],'original_cli_deny_sha256':pins['agent/config/copilot-deny-tools.json'],'private_worker_config_sha256':digest(config),'server_policy_sha256':{purpose:policies[purpose].sha for purpose in PURPOSES},'worker_service_credentials':False,'transport':'fixed-peer-uds','real_native_service_qualification':False}
    return config,denials,receipt
