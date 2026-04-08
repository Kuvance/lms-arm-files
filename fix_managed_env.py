import json

with open('container-apps.json', 'r') as f:
    capps = json.load(f)

# 1. Add a new parameter for the environment name
capps['parameters']['managedEnvironment_name'] = {
    "type": "String",
    "defaultValue": "lms-managed-environment"
}

# 2. Remove the old external ID parameter (no longer needed)
capps['parameters'].pop('managedEnvironments_managedEnvironment_eventresource_9067_externalid', None)

# 3. Build the new managed environment resource
managed_env_resource = {
    "type": "Microsoft.App/managedEnvironments",
    "apiVersion": "2024-03-01",
    "name": "[parameters('managedEnvironment_name')]",
    "location": "West US 2",
    "properties": {
        "zoneRedundant": False,
        "kedaConfiguration": {},
        "daprConfiguration": {},
        "appLogsConfiguration": {
            "destination": "none"
        },
        "workloadProfiles": [
            {
                "workloadProfileType": "Consumption",
                "name": "Consumption"
            }
        ]
    }
}

# 4. Insert managed environment FIRST in the resource list
capps['resources'].insert(0, managed_env_resource)

# 5. Update all Container Apps to reference the NEW local environment
new_env_id = "[resourceId('Microsoft.App/managedEnvironments', parameters('managedEnvironment_name'))]"
for res in capps['resources']:
    if res['type'] == 'Microsoft.App/containerapps':
        res['properties']['managedEnvironmentId'] = new_env_id
        res['properties']['environmentId'] = new_env_id
        # Add dependsOn to ensure env is created first
        res['dependsOn'] = [
            "[resourceId('Microsoft.App/managedEnvironments', parameters('managedEnvironment_name'))]"
        ]

# 6. Also replace the old concat() calls for certificateIds - sanitize them to just name-based for now
# (certificates need to be re-issued for the new environment)
for res in capps['resources']:
    if res['type'] == 'Microsoft.App/containerapps':
        ingress = res.get('properties', {}).get('configuration', {}).get('ingress', {})
        if 'customDomains' in ingress:
            # Strip custom domains and certificates - they need to be reconfigured
            # against the new environment separately
            ingress.pop('customDomains', None)

with open('container-apps.json', 'w') as f:
    json.dump(capps, f, indent=4)

# 7. Update main.json to pass the new parameter down
with open('main.json', 'r') as f:
    main_tmpl = json.load(f)

main_tmpl['parameters']['managedEnvironment_name'] = {
    "type": "String",
    "defaultValue": "lms-managed-environment"
}

# Remove old external env param from main if present
main_tmpl['parameters'].pop('managedEnvironments_managedEnvironment_eventresource_9067_externalid', None)

for res in main_tmpl['resources']:
    if res['name'] == 'containerAppsDeployment':
        res['properties']['parameters']['managedEnvironment_name'] = {
            "value": "[parameters('managedEnvironment_name')]"
        }
        # Remove old external env param if passed
        res['properties']['parameters'].pop('managedEnvironments_managedEnvironment_eventresource_9067_externalid', None)

with open('main.json', 'w') as f:
    json.dump(main_tmpl, f, indent=4)

print("Done! Managed environment added to container-apps.json")
print(f"Total resources in container-apps.json: {len(capps['resources'])}")
