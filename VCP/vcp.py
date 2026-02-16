import requests
import urllib3
import json
from vmware.vapi.vsphere.client import create_vsphere_client
from com.vmware.esx.settings.clusters.enablement_client import Configuration
from com.vmware.esx.settings.clusters_client import Configuration
from com.vmware.esx.settings.clusters.enablement.configuration_client import Transition
from com.vmware.esx.settings.clusters.configuration.reports_client import LastComplianceResult
from com.vmware.esx.settings.clusters.configuration_client import Drafts
import time

session = requests.session()
session.verify = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create vSphere Client Session
vsphere_client = create_vsphere_client(
    server='vc_fqdn_or_ip',
    username='vc_username',
    password='vc_password',
    session=session
)

print(f"\033[92mConnected to vCenter Server, Session ID: \033[0m {vsphere_client.session_id}")
#########################################################################################
#Transition a cluster to be managed by vSphere Configuration Profile 
#########################################################################################
#Check VCP Enablement Status on Cluster

print("\033[92m1. Checking VCP Configuration for cluster: domain-c8 \033[0m")
print("GET /esx/settings/clusters/:cluster/enablement/configuration")
vcp_service = Configuration(vsphere_client._stub_config)
result = vcp_service.get(cluster="domain-c10")
print(f"\033[92mvSphere Configuration Profile Enablement Status on cluster domain-c10: \033[0m {result.enabled} ")

#Invoke Cluster Eligibility Check for VCP Transition
print("\n\033[92m2. Invoking Cluster Eligibility Check for Configuration Transition...\033[0m")
print("POST /esx/settings/clusters/:cluster/enablement/configuration/transition?action=checkEligibility&vmw-task=true")
transition_service = Transition(vsphere_client._stub_config)
check_eligibility_task = transition_service.check_eligibility_task(cluster="domain-c10")
print(f"\033[92mCluster Eligibility check initiated successfully. VMware Task ID: \033[0m {check_eligibility_task.task_id}")

time.sleep(120)

#Import Configuration Profile from a reference Host for VCP Transition
print("\n\033[92m3. Importing Configuration Profile from reference Host for VCP Transition...\033[0m")
print("POST /esx/settings/clusters/:cluster/enablement/configuration/transition?action=importFromHost&vmw-task=true")
import_task = transition_service.import_from_host_task(cluster="domain-c10", host="host-13")
print(f"\033[92mConfiguration Profile import initiated successfully. VMware Task ID: \033[0m {import_task.task_id}")

time.sleep(120)

#Validate Imported Cluster Configuration Profile for VCP Transition
print("\n\033[92m4. Validating Imported Cluster Configuration Profile for VCP Transition...\033[0m")
print("POST /esx/settings/clusters/:cluster/enablement/configuration/transition?action=validateConfig&vmw-task=true")
validate_task = transition_service.validate_config_task(cluster="domain-c10")
print(f"\033[92mConfiguration Profile validation initiated successfully. VMware Task ID: \033[0m {validate_task.task_id}")

time.sleep(120)

#Enable VCP on Cluster using Imported Configuration Profile
print("\n\033[92m5. Enabling VCP on Cluster using Imported Configuration Profile...\033[0m")
print("POST /esx/settings/clusters/:cluster/enablement/configuration/transition?action=enable&vmw-task=true")
enable_task = transition_service.enable_task(cluster="domain-c10")
print(f"\033[92mVCP Enablement initiated successfully. VMware Task ID: \033[0m {enable_task.task_id}")

time.sleep(120)

#Check VCP Enablement Status on Cluster after Transition
print("\n\033[92m6. Checking VCP Configuration for cluster: domain-c10 \033[0m")
print("GET /esx/settings/clusters/:cluster/enablement/configuration")
vcp_service = Configuration(vsphere_client._stub_config)
result = vcp_service.get(cluster="domain-c10")
print(f"\033[92mvSphere Configuration Profile Enablement Status on cluster domain-c10: \033[0m {result.enabled} ")


########################################################################################
#Manage Desired State Configuration on the Cluster using vSphere Configuration Profile
########################################################################################

#Check Cluster Compliance Status with Desired State Configuration
print("\n\033[92m7. Checking Cluster Compliance Status with Desired State Configuration...\033[0m")
print("GET /esx/settings/clusters/:cluster/configuration?action=checkCompliance&vmw-task=true")
compliance_service = Configuration(vsphere_client._stub_config)
result = compliance_service.check_compliance_task(cluster="domain-c10")
print(f"\033[92mCluster Compliance Status: \033[0m {result.get_task_id()} ")

#Validate Cluster Desired State Configuration Compliance Results
print("\n\033[92m8. Validating Cluster Desired State Configuration Compliance Results...\033[0m")
print("GET /esx/settings/clusters/:cluster/configuration/reports/last-compliance-result")
report_service = LastComplianceResult(vsphere_client._stub_config)
compliance_report = report_service.get(cluster="domain-c10")
print(f"\033[92mCompliance Result Status: \033[0m {compliance_report.cluster_status} ")

#Create Configuration Draft for Cluster 
print("\n\033[92m9. Creating Configuration Draft for Cluster...\033[0m")
print("POST /esx/settings/clusters/:cluster/configuration/drafts")
draft_service = Drafts(vsphere_client._stub_config)
draft_id = draft_service.create(cluster="domain-c10")
print(f"\033[92mConfiguration Draft created successfully, Draft ID: \033[0m {draft_id}")

#Export Cluster Configuration from Draft
print("\n\033[92m10. Exporting Cluster Configuration from Draft...\033[0m")
print(f"POST /esx/settings/clusters/:cluster/configuration/drafts/{{draft}}?action=exportConfig ")
draft_config = draft_service.export_config(cluster="domain-c10", draft=draft_id)
print(draft_config)
data = vars(draft_config).copy()

# If 'config' is a JSON string, parse it to a dict
if isinstance(data.get("config"), str):
    try:
        data["config"] = json.loads(data["config"])
    except Exception:
        pass  # Leave as is if not valid JSON

with open("config_new.json", "w") as f:
    json.dump(data, f, indent=2)

# Load the JSON file into a Python object
with open("config.json", "r") as f:
    config_obj = json.load(f)

# Convert the Python object back into a JSON string
# 
config_json_string = json.dumps(config_obj["config"], indent=2)

#Update the Configuration Draft with new configurations 
print("\n\033[92m11. Updating the Configuration Draft with new configurations ...\033[0m")
print(f"POST /esx/settings/clusters/:cluster/configuration/drafts/{{draft}}?action=update ")
draft_spec = draft_service.UpdateSpec(expected_revision=None, config=config_json_string)
updated_draft = draft_service.update(cluster="domain-c10", draft=draft_id, spec=draft_spec)

#Run Draft Precheck 
print("\n\033[92m12. Running Draft Precheck ...\033[0m")
precheck_task = draft_service.precheck_task(cluster="domain-c10", draft=draft_id)
print(f"POST /esx/settings/clusters/:cluster/configuration/drafts/{{draft}}?action=precheck&vmw-task=true")
print(f"\033[92mDraft Precheck initiated successfully. VMware Task ID: \033[0m {precheck_task.task_id}")

#Apply the Configuration Draft
time.sleep(120)
print("\n\033[92m13. Applying the Configuration Draft ...\033[0m")
print(f"POST /esx/settings/clusters/:cluster/configuration/drafts/{{draft}}?action=apply")
apply_task = draft_service.apply(cluster="domain-c10", draft=draft_id)
print(f"\033[92mConfiguration Draft applied successfully. VMware Task ID: \033[0m {apply_task}")
