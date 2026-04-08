import json

# Update container-apps.json
with open('container-apps.json', 'r') as f:
    capps = json.load(f)

if 'registries_lmsrepository_name' not in capps['parameters']:
    capps['parameters']['registries_lmsrepository_name'] = {'type': 'String', 'defaultValue': 'lmsrepository'}

secret_value_str = "[listCredentials(resourceId('Microsoft.ContainerRegistry/registries', parameters('registries_lmsrepository_name')), '2025-11-01').passwords[0].value]"

for res in capps.get('resources', []):
    if res['type'] == 'Microsoft.App/containerapps':
        secrets = res.get('properties', {}).get('configuration', {}).get('secrets', [])
        for s in secrets:
            s['value'] = secret_value_str

with open('container-apps.json', 'w') as f:
    json.dump(capps, f, indent=4)

# Update main.json
with open('main.json', 'r') as f:
    main_tmpl = json.load(f)

if 'registries_lmsrepository_name' not in main_tmpl['parameters']:
    main_tmpl['parameters']['registries_lmsrepository_name'] = {'type': 'String', 'defaultValue': 'lmsrepository'}

for res in main_tmpl.get('resources', []):
    if res['name'] == 'containerAppsDeployment':
        if 'parameters' not in res['properties']:
            res['properties']['parameters'] = {}
        res['properties']['parameters']['registries_lmsrepository_name'] = {'value': "[parameters('registries_lmsrepository_name')]"}

with open('main.json', 'w') as f:
    json.dump(main_tmpl, f, indent=4)
print('Done!')
