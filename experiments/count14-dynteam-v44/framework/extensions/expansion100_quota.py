"""Conserved fixed cross-owner capacity: existing60 + new36 =96.

Each owner's MAIN+BRANCH retains its original shared admission condition and
physical UNKNOWN counters. This is not a new semaphore or an UNKNOWN release.
"""
from common import need,digest
from expansion100_contract import QUOTAS

def install(peer,capacities,*,gates=(),relay_ledgers=(),final_slots,group):
 need(group in QUOTAS,'EXP100_REGISTERED_QUOTA_GROUP');q=dict(QUOTAS[group])
 capacities=tuple(capacities);gates=tuple(gates);relay_ledgers=tuple(relay_ledgers)
 need(set(c.ledger for c in capacities)==set(peer.ledgers),'EXP100_ALL_MAIN_BRANCH_CAPACITIES')
 need(all(g.ledger in peer.ledgers and g.condition is peer.condition for g in gates),'EXP100_SAME_NATIVE_ADMISSION_CONDITION')
 need(all(l.ledger in peer.ledgers for l in relay_ledgers),'EXP100_SAME_NATIVE_RELAY_LEDGERS')
 need(type(final_slots.cap)is int and 1<=final_slots.cap<=12,'EXP100_ORIGINAL_FINAL_SLOT_OWNER')
 with peer.condition:
  physical=peer.physical()
  need(physical<=q['global'],'EXP100_EXISTING_PHYSICAL_SLOTS_CANNOT_BE_RELEASED_FOR_QUOTA')
  # Retain lower incident FINAL caps (e.g. original3); never raise them here.
  final_cap=min(final_slots.cap,q['final'])
  for l in peer.ledgers:
   with l.tx():l.event('GLOBAL','USER100M_CONSERVED_ROOT_FP8_QUOTA',{
    'quota_group':group,'root_global_cap':q['global'],'search_cap':q['search'],
    'auxiliary_cap':q['auxiliary'],'final_cap':final_cap,'all_roots_global_cap':96,
    'all_roots_final_cap':12,'physical_including_historical_unknown':physical,
    'UNKNOWN_released':0,'fees_changed':0,'requests_replayed':0})
  peer.global_cap=q['global'];peer.search_cap=q['search']
  for c in capacities:c.global_cap=q['global'];c.aux_cap=q['auxiliary'];c.ledger.model_capacity_global_cap=q['global']
  for g in gates:g.global_cap=q['global'];g.search_cap=q['search']
  for l in relay_ledgers:l.global_cap=q['global']
  final_slots.cap=final_cap;peer.condition.notify_all()
 return {'schema':'agensh-v2-user100m-conserved-quota-install-v1','group':group,
  'quota':q,'effective_final_cap':final_cap,'physical_including_historical_unknown':physical,
  'history_slots_released':0,'search_released':False,'capacity_policy_sha256':digest(QUOTAS)}
