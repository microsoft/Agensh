"""Actual production reader for approved domain; OWN remains explicit/rejected."""
from pathlib import Path
import hashlib
from common import need,digest,sha
from final_queue import process_identity
from queue_control import CarrierReader as OriginalCarrierReader,DDL,AUTH,JOBS,POLICY,SCHEMA,source_pins
from allowance_control import read_public
from formal_scope import read_registered_contract,PUBLIC_CONTRACT_CANONICAL_SHA256
from approved_queue_install import APPROVAL,PROPOSAL,SQL_DIFF,approved_source_pins


class ApprovedCarrierReader(OriginalCarrierReader):
    def __init__(self,path,pin,*,allow_OWN=False):
        self.explicit_OWN=allow_OWN is True
        if self.explicit_OWN:
            OriginalCarrierReader.__init__(self,path,pin,allow_OWN=True)
            return
        self.path=Path(path);self.home=self.path.parent;self.pin=sha(pin)
        value=read_public(self.path,root=self.home,expected=self.pin)
        contract=read_registered_contract(Path(__file__).resolve().parents[1]/'contracts-two-arm-v4/PRODUCTION_PUBLIC_CONTRACT.json')
        home=Path(contract['arms'][0]['root'])/'owner'
        need(value['schema']==SCHEMA and value['contract_sha256']==PUBLIC_CONTRACT_CANONICAL_SHA256 and
             value['policy']==POLICY and value['carrier_table']==JOBS and value['authorization_table']==AUTH and
             value['DDL_sha256']==digest(DDL)and value['home']==str(self.home)and
             self.home==home/'final-control-carrier-approved-v1'and value['core_home']==str(home)and
             value['ledger_home']==str(home/'ledger')and value['queue_home']==str(home/'final-queue'),
             'APPROVED_CARRIER_PRODUCTION_EXACT_REGISTERED_NEW_ROOT_DESCRIPTOR')
        need(value['offline_OWN']is False and value['production_install_authorized']is True and
             value['approval']==APPROVAL and value['proposal_manifest_sha256']==PROPOSAL and value['sql_diff_sha256']==SQL_DIFF,
             'APPROVED_CARRIER_PRODUCTION_READER_NOT_OWN_OR_UNAPPROVED_DESCRIPTOR')
        self.value=value;self.fresh()
    def fresh(self):
        if self.explicit_OWN:return OriginalCarrierReader.fresh(self)
        need(read_public(self.path,root=self.home,expected=self.pin)==self.value and
             process_identity(self.value['owner']['pid'])==self.value['owner'],
             'APPROVED_CARRIER_SAME_LIVE_PID_START_BOOT_OWNER_DESCRIPTOR')
        need(self.value['control_source_sha256']==source_pins()and
             self.value['approved_source_sha256']==approved_source_pins(),'APPROVED_CARRIER_BOTH_ORIGINAL_AND_APPROVED_SOURCE_PINS')
        receipt=read_public(self.home/'APPROVED_INSTALL_PUBLIC.json',root=self.home,
            expected=self.value['installed_receipt_sha256'])
        need(receipt['approval']==APPROVAL and receipt['owner']==self.value['owner']and
             receipt['production_install_authorized']is True and receipt['offline_OWN']is False and
             all(receipt[k]is True for k in('old_queue_schema_equal','old_queue_rows_equal','old_event_prefix_equal',
                 'ledger_all_old_schema_rows_and_events_equal')),
             'APPROVED_CARRIER_EXACT_BEFORE_AFTER_ORIGINAL_ROWS_SCHEMA_EVENT_PREFIX_EVIDENCE')

# Export original import name, but no original module/global/class mutation.
CarrierReader=ApprovedCarrierReader
