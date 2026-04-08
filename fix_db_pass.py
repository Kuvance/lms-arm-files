import json

# Update database.json
with open('database.json', 'r') as f:
    db = json.load(f)

db['parameters']['administratorLoginPassword'] = {'type': 'secureString'}
for res in db.get('resources', []):
    if res['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers':
        res['properties']['administratorLoginPassword'] = "[parameters('administratorLoginPassword')]"

with open('database.json', 'w') as f:
    json.dump(db, f, indent=4)

# Update main.json
with open('main.json', 'r') as f:
    main_tmpl = json.load(f)

main_tmpl['parameters']['administratorLoginPassword'] = {'type': 'secureString'}
for res in main_tmpl.get('resources', []):
    if res['name'] == 'databaseDeployment':
        if 'parameters' not in res['properties']:
            res['properties']['parameters'] = {}
        res['properties']['parameters']['administratorLoginPassword'] = {'value': "[parameters('administratorLoginPassword')]"}

with open('main.json', 'w') as f:
    json.dump(main_tmpl, f, indent=4)

print('Done')
