"""Render the real pinned beta Compose, not a fictional new bootstrap schema.

Racing helpers occupy the existing native tester2..9 account/container slots;
the original tester1 remains unchanged. New helper AGENT_ROLE=racing bypasses
ProgramBench assignment refresh, while original workers/checker/tester retain
their source bytes. No Docker/host action is performed by this compiler.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

from common import need
from new_scope_ledger import native_catalogue


def native_aliases(arm):
    roles = native_catalogue(arm=arm)
    result = {}
    for role, kind in roles.items():
        if kind == "worker":
            short = "worker" + str(int(role.split("-")[1]) + 1)
        elif kind == "checker":
            short = "checker"
        elif kind == "tester":
            short = "tester1"
        elif kind == "racing_background":
            short = "tester2"
        else:
            short = "tester" + str(int(role.rsplit("-", 1)[1]) + 3)
        result[role] = dict(native_short=short, agent_service="agent-" + short,
                            router_service="mini-router-" + short, kind=kind)
    need(len({r["native_short"] for r in result.values()}) == len(roles),
         "DYNTEAM_NATIVE_ALIAS_ONE_TO_ONE_REGISTERED_ROSTER")
    return result


def render_native_base(source, *, source_sha256, arm):
    source = Path(source)
    raw = source.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == source_sha256 and not source.is_symlink(),
         "DYNTEAM_NATIVE_GENERATOR_IMMUTABLE_SOURCE_PIN")
    tree = ast.parse(raw)
    imports = [n for n in tree.body if isinstance(n, ast.Import)]
    need(len(imports) == 1 and len(imports[0].names) == 1 and imports[0].names[0].name == "os",
         "DYNTEAM_NATIVE_GENERATOR_ONLY_ENV_DEPENDENCY")
    tree.body.remove(imports[0])
    testers = 1 if arm == "DYNTEAM" else 9
    need(arm in ("DYNTEAM", "DYNTEAM_RACING"), "DYNTEAM_NATIVE_RENDER_EXACT_ARM")
    # Original generator body, deterministic environment input, no mutation of
    # this developer/owner process's environment or import path.
    namespace = {"__name__": "count14_pinned_native_generator", "__file__": str(source),
                 "os": SimpleNamespace(environ={"PBENCH_WORKERS_PER_TEAM": "32", "PBENCH_TESTERS": str(testers)})}
    exec(compile(tree, str(source), "exec"), namespace)
    expected = native_aliases(arm)
    native_names = set(namespace["ALL_AGENTS"] + namespace["TESTER_AGENTS"] + [namespace["CHECKER_AGENT"]])
    need(native_names == {r["native_short"] for r in expected.values()},
         "DYNTEAM_REAL_GENERATOR_MATCHES_FROZEN_BILLING_DIRECTORY")
    return namespace["build"](), expected


def racing_overlay(aliases, *, frozen_public_code_directory, private_role_mounts, role_relay_configuration):
    """JSON is a valid Compose overlay; it does not substitute the base stack.

    Public source + exact per-role private export directories are supplied by
    the real cold owner. Never mount owner root/financial/official-eval paths.
    Model credentials are original RELAY role tokens, not the provider key.
    """
    code = Path(frozen_public_code_directory)
    code_names = {"router-entry.mjs", "router-session-hook.mjs", "native-racing-phase-port.mjs", "native-racing-phase-entry.mjs"}
    need(code.is_absolute() and code.resolve() == code and code.is_dir() and
         code.name == "router-public-source" and {p.name for p in code.iterdir()} == code_names and
         all(p.is_file() and not p.is_symlink() for p in code.iterdir()),
         "DYNTEAM_RACING_PUBLIC_NATIVE_CODE_EXPORT")
    helpers = {r: v for r, v in aliases.items() if v["kind"] in ("racing_background", "racing_player")}
    need(len(helpers) == 8 and set(private_role_mounts) == set(helpers) == set(role_relay_configuration),
         "DYNTEAM_EIGHT_NATIVE_HELPER_PRIVATE_EXPORTS")
    services = {}
    for role, row in helpers.items():
        directory = Path(private_role_mounts[role])
        need(directory.is_absolute() and directory.resolve() == directory and directory.is_dir() and
             directory != code and not code.is_relative_to(directory) and not directory.is_relative_to(code),
             "DYNTEAM_NATIVE_PRIVATE_ROLE_EXPORT_NOT_OWNER_OR_CODE_ROOT")
        need(directory.name == role and directory.parent.name == "native-private-exports",
             "DYNTEAM_NATIVE_EXPORT_ONLY_ONE_ROLE_NOT_FINANCIAL_OWNER_ROOT")
        relay = role_relay_configuration[role]
        need(type(relay) is dict and set(relay) == {"COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_API_KEY", "COPILOT_MODEL"},
             "DYNTEAM_NATIVE_ORIGINAL_ROLE_RELAY_ENV_FIELDS")
        services[row["agent_service"]] = dict(environment={"AGENT_ROLE": "racing", **relay,
            "ANTHROPIC_BASE_URL": relay["COPILOT_PROVIDER_BASE_URL"],
            "ANTHROPIC_API_KEY": relay["COPILOT_PROVIDER_API_KEY"],
            "ANTHROPIC_MODEL": relay["COPILOT_MODEL"]}, labels={
            "count14.stable-billing-role": role, "count14.native-helper-not-free": "true"})
        services[row["router_service"]] = dict(environment={"AGENT_ROLE": "racing"},
            command=["node", "/app/count14/native-racing-phase-entry.mjs", "/run/count14-dynteam/route.json"],
            volumes=[str(code) + ":/app/count14:ro", str(directory) + ":/run/count14-dynteam"],
            healthcheck={"disable": True}, labels={
            "count14.stable-billing-role": role, "count14.native-private-scientific-transport": "true"})
    return {"services": services}


def racing_bridge_role_delta(raw):
    """Cold-only role compatibility, NOT the pending physical-retirement fix.

    Treat racing's repeated CLI conversation births like checker/tester for the
    account-reconnect guard, but keep public main repository (not claims/tests).
    Original normal worker/checker/tester branches are unchanged when false.
    """
    old = "is_checker = os.environ.get('AGENT_ROLE') == 'checker'\n"
    need(raw.count(old) == 1 and raw.count("not (is_tester or is_checker)") == 2,
         "DYNTEAM_NATIVE_BRIDGE_EXACT_RACING_ROLE_SITES")
    modified = raw.replace(old, old + "is_racing = os.environ.get('AGENT_ROLE') == 'racing'\n")
    modified = modified.replace("not (is_tester or is_checker)", "not (is_tester or is_checker or is_racing)")
    compile(modified, "count14-cold-racing-native-bridge.py", "exec")
    return modified


def guarded_native_overlay(aliases, *, guarded_agent_directory, compiled_router_directory, role_exports,
                           frozen_public_code_directory, role_relay_configuration):
    """Apply the actual cold guarded source to original Compose service names.

    No original service is replaced by another scientific loop. Code mounts
    are read-only, UIDs/daemon/network/cgroup settings are not changed. Exact
    role private exports avoid mounting the host owner/ledger root.
    """
    agent,router=Path(guarded_agent_directory),Path(compiled_router_directory)
    names={'acp-bridge.py','worker_session.py','native_bridge_client.py','native_bridge_protocol.py'}
    need(agent.is_absolute()and agent.resolve()==agent and agent.is_dir()and
         {p.name for p in agent.iterdir()}==names and
         all(p.is_file()and not p.is_symlink()for p in agent.iterdir())and
         (agent/'acp-bridge.py').stat().st_mode&0o111,
         'DYNTEAM_EXACT_GUARDED_NATIVE_AGENT_EXPORT')
    need(router.is_absolute()and router.resolve()==router and router.is_dir()and
         all((router/n).is_file()and not(router/n).is_symlink()for n in
             ('main.js','acp_socket_channel.js','count14_budget_pause_clock.js')),
         'DYNTEAM_EXACT_COMPILED_NATIVE_CLOCK_ROUTER_EXPORT')
    code = Path(frozen_public_code_directory)
    code_names = {'router-entry.mjs','router-session-hook.mjs','native-racing-phase-port.mjs',
                  'native-racing-phase-entry.mjs'}
    need(code.is_absolute() and code.resolve()==code and code.is_dir() and
         code.name=='router-public-source' and {p.name for p in code.iterdir()}==code_names and
         all(p.is_file() and not p.is_symlink() for p in code.iterdir()),
         'DYNTEAM_ALL_NATIVE_ROUTERS_REQUIRE_FROZEN_SESSION_PRELOAD')
    need(set(role_exports)==set(aliases)==set(role_relay_configuration),
         'DYNTEAM_EVERY_NATIVE_ROLE_GUARDED_EXPORT')
    services={}
    for role,alias in aliases.items():
        value=role_exports[role]
        need(set(value)=={'agent_control_directory','router_control_directory','clock_directory',
                          'clock_binding_sha256','clock_owner_uid'},'DYNTEAM_NATIVE_ROLE_EXPORT_FIELDS')
        ad,rd,cd=(Path(value[k])for k in('agent_control_directory','router_control_directory','clock_directory'))
        need(all(p.is_absolute()and p.resolve()==p and p.is_dir()for p in(ad,rd,cd))and
             ad.name==rd.name==role and ad.parent.name=='native-agent-control-exports'and
             rd.parent.name=='native-private-exports','DYNTEAM_EXACT_SINGLE_ROLE_CONTROL_EXPORTS')
        sha=value['clock_binding_sha256']
        need(type(sha)is str and len(sha)==64 and all(c in'0123456789abcdef'for c in sha)and
             type(value['clock_owner_uid'])is int and value['clock_owner_uid']>=0,
             'DYNTEAM_ORIGINAL_CLOCK_BINDING_METADATA')
        # A bind of '/' or the financial owner directory would expose unrelated
        # state even read-only. Only the original publisher's public leaf is
        # acceptable; all file reads below are fixed public clock metadata.
        leaves=list(cd.iterdir())
        clock_names = {p.name for p in leaves}
        allowed_clock_names={r+suffix for r in aliases for suffix in ('.json','.json.rearm')}
        partials={n for n in clock_names if n.startswith('.') and n.endswith('.partial') and
                  len(n)==41 and all(c in '0123456789abcdef' for c in n[1:-8])}
        need(cd.parent.name=='clocks' and clock_names and len(partials)<=1 and
             clock_names-partials <= allowed_clock_names and
             role+'.json' in clock_names and
             all(p.is_file() and not p.is_symlink() for p in leaves),
             'DYNTEAM_ONLY_ORIGINAL_PUBLIC_CLOCK_LEAF_MOUNT')
        relay=role_relay_configuration[role]
        need(type(relay)is dict and set(relay)=={'COPILOT_PROVIDER_BASE_URL','COPILOT_PROVIDER_API_KEY','COPILOT_MODEL'} and
             all(type(v)is str and v for v in relay.values()),'DYNTEAM_EVERY_NATIVE_AGENT_ORIGINAL_ROLE_RELAY')
        services[alias['agent_service']]={'environment':{
            'COUNT14_NATIVE_ROUTE':'/run/count14-dynteam/route.json',**relay,
            'ANTHROPIC_BASE_URL':relay['COPILOT_PROVIDER_BASE_URL'],
            'ANTHROPIC_API_KEY':relay['COPILOT_PROVIDER_API_KEY'],
            'ANTHROPIC_MODEL':relay['COPILOT_MODEL']},
            'volumes':[str(agent/n)+':/opt/omcgitea/'+n+':ro'for n in sorted(names)]+
                      [str(ad)+':/run/count14-dynteam:ro']}
        services[alias['router_service']]={'environment':{
            'ACP_SOCKET_PATH':'/var/run/acp/agent.sock',
            'COUNT14_BUDGET_PAUSE_FILE':'/run/count14-budget-clock/'+role+'.json',
            'COUNT14_BUDGET_PAUSE_BINDING_SHA256':sha,
            'COUNT14_BUDGET_PAUSE_OWNER_UID':str(value['clock_owner_uid'])},
            'command':['node','/app/count14/router-entry.mjs'],
            'volumes':[str(router)+':/app/dist:ro',str(code)+':/app/count14:ro',str(rd)+':/run/count14-dynteam',
                       str(cd)+':/run/count14-budget-clock:ro']}
    helpers = {r:a for r,a in aliases.items() if a['kind'] in ('racing_background','racing_player')}
    if helpers:
        helper_overlay = racing_overlay(aliases, frozen_public_code_directory=code,
            private_role_mounts={r:role_exports[r]['router_control_directory'] for r in helpers},
            role_relay_configuration={r:role_relay_configuration[r] for r in helpers})
        for name, row in helper_overlay['services'].items():
            service=services[name]
            service.setdefault('environment',{}).update(row.get('environment',{}))
            for key in ('command','healthcheck','labels'):
                if key in row:service[key]=row[key]
            # Compose merges volumes by CONTAINER target, not host path. Keep
            # clock/dist guards while replacing only the same private mount.
            mounts={v.split(':')[1]:v for v in service['volumes']}
            mounts.update({v.split(':')[1]:v for v in row.get('volumes',[])})
            service['volumes']=list(mounts.values())
    # All agent/router domains are strict kernel-census domains. Docker
    # HEALTHCHECK would spawn an unregistered process INSIDE those domains.
    # Readiness is still the original socket/native-session/physical proof;
    # no unknown birth is ignored and no ACK/TTL/health threshold is changed.
    census_services={a[k] for a in aliases.values()
                     for k in ('agent_service','router_service')}
    for service_name in census_services:
        service=services[service_name]
        service['healthcheck']={'disable':True}
        dependencies=service.get('depends_on',{})
        if isinstance(dependencies,dict):
            for dependency,condition in dependencies.items():
                if dependency in census_services and isinstance(condition,dict) and condition.get('condition')=='service_healthy':
                    dependencies[dependency]=dict(condition,condition='service_started')
    need(all(services[name].get('healthcheck',{}).get('disable') is True
             for name in census_services),
         'DYNTEAM_FINAL_COMPOSE_ALL_CENSUSED_AGENT_ROUTER_HEALTHCHECKS_DISABLED')
    return {'services':services}
