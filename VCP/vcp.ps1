$vc = "vc-fqdn-or-ip"
$cred = Get-Credential -Message "Enter vCenter Credentials"
Connect-VIServer -Server $vc -Credential $cred
$cluster = Get-Cluster -Name "cluster-name"

#########################################################################################
#Transition a cluster to be managed by vSphere Configuration Profile 
#########################################################################################

#Check if Cluster is managed by vSphere Configuration API 
$IsVCPEnabled = Invoke-GetClusterEnablementConfiguration -Cluster $cluster.ExtensionData.Moref.Value
Write-Host "vSphere Configuration Profile Enabled:" $IsVCPEnabled.Enabled

#Invoke Cluster Eligibility Check for Configuration Transition if not enabled
if (-not $IsVCPEnabled.Enabled) {
    Invoke-CheckEligibilityClusterConfigurationTransitionAsync -Cluster $cluster.ExtensionData.Moref.Value -Confirm:$false
}

#Import Configuration Profile from a reference host 
$referenceHost = Get-VMHost -Name "esx-fqdn-or-ip"
$body = $referenceHost.ExtensionData.Moref.Value
Invoke-ImportFromHostClusterConfigurationTransitionAsync -Body $body -Cluster $cluster.ExtensionData.MoRef.Value -Confirm:$false

#Validate cluster configuration 
Invoke-ValidateConfigClusterConfigurationTransitionAsync -Cluster $cluster.ExtensionData.Moref.Value -Confirm:$false

#Enable vSphere Configuration Profile on the cluster
Invoke-EnableClusterConfigurationTransitionAsync -Cluster $cluster.ExtensionData.Moref.Value -Confirm:$false
Start-Sleep -Seconds 60

#Check if the vSphere Configuration Profile is enabled
$IsVCPEnabled = Invoke-GetClusterEnablementConfiguration -Cluster $cluster.ExtensionData.Moref.Value
Write-Host "vSphere Configuration Profile Enabled:" $IsVCPEnabled.Enabled

#########################################################################################
#Manage Desired State Configuration on the Cluster using vSphere Configuration Profile
#########################################################################################

#Create a New Configuration Draft
$draftId = Invoke-CreateNewDraftClusterConfiguration -Cluster $cluster.ExtensionData.Moref.Value
Write-Host "Initialized Configuration Draft ID:" $draftId

#Export Cluster Configuration from Configuration Draft
 $configuration = Invoke-GetClusterDraftConfiguration  -Cluster $cluster.ExtensionData.Moref.Value -Draft $draftId
 $configuration |Out-File ClusterConfig.json

#Modify the Cluster Configuration JSON as needed
#For example, changing NTP settings, adding/removing tags, etc.
#Load your JSON file into a PowerShell Object
$configObj = Get-Content ./ClusterConfig.json -Raw | ConvertFrom-Json

#Convert that object into a JSON String 
# CRITICAL: We use -Depth 10 to ensure the nested ESX/NSX settings aren't lost
$configJsonString = $configObj | ConvertTo-Json -Depth 10

#Initialize the UpdateSpec using the JSON STRING
$updatedSpec = Initialize-SettingsClustersConfigurationDraftsUpdateSpec -Config $configJsonString

#Invoke the update to the Cluster Draft
Invoke-UpdateClusterDraft -Cluster $cluster.ExtensionData.MoRef.Value -Draft $draftId -EsxSettingsClustersConfigurationDraftsUpdateSpec $updatedSpec

#Validate the Cluster Draft Configuration Changes 
$configChanges = Invoke-GetClusterDraft0 -Cluster $cluster.ExtensionData.MoRef.Value -Draft $draftId
$configChanges |ConvertTo-Json -Depth 10 

#Run Prechecks on the Draft Configuration
Invoke-PrecheckClusterDraftAsync -Cluster $cluster.ExtensionData.MoRef.Value -Draft $draftId -Confirm:$false
Start-Sleep -Seconds 30

#Apply Config Profile Draft to the Cluster
Invoke-ApplyClusterDraft -Cluster $cluster.ExtensionData.MoRef.Value -Draft $draftId -Confirm:$false

#Monitor the Job 
#Check Cluster Compliance Status
Invoke-CheckComplianceClusterConfigurationAsync -Cluster $cluster.ExtensionData.MoRef.Value -Confirm:$false
$complianceResult = Invoke-GetClusterConfigurationReportsLastComplianceResult -Cluster $cluster.ExtensionData.MoRef.Value
Write-Host "Cluster Compliance Status:" $complianceResult.ClusterStatus
Write-Host "Cluster Compliance Summary:" $complianceResult.Summary.DefaultMessage
Write-Host "Compliant Hosts:"  $complianceResult.CompliantHosts
