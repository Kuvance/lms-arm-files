import json

with open('container-apps.json', 'r') as f:
    capps = json.load(f)

# Add a simple secure parameter for the ACR password
capps['parameters']['containerRegistryPassword'] = {
    "type": "secureString",
    "metadata": {
        "description": "Password for the Azure Container Registry (lmsrepository). Get it from Azure Portal > Container Registry > Access keys."
    }
}

# Replace the listCredentials() call in all secrets with the parameter reference
for res in capps['resources']:
    if res['type'] == 'Microsoft.App/containerapps':
        secrets = res.get('properties', {}).get('configuration', {}).get('secrets', [])
        for s in secrets:
            if 'value' in s:
                s['value'] = "[parameters('containerRegistryPassword')]"

with open('container-apps.json', 'w') as f:
    json.dump(capps, f, indent=4)

# Update main.json to pass the new parameter
with open('main.json', 'r') as f:
    main_tmpl = json.load(f)

main_tmpl['parameters']['containerRegistryPassword'] = {
    "type": "secureString",
    "metadata": {
        "description": "Password for the Azure Container Registry."
    }
}

for res in main_tmpl['resources']:
    if res['name'] == 'containerAppsDeployment':
        res['properties']['parameters']['containerRegistryPassword'] = {
            "value": "[parameters('containerRegistryPassword')]"
        }

with open('main.json', 'w') as f:
    json.dump(main_tmpl, f, indent=4)

print("Done! containerRegistryPassword parameter added.")
