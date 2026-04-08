import json

with open('database.json', 'r') as f:
    db = json.load(f)

# Remove system-managed databases that cannot be deployed
system_dbs = ['azure_maintenance', 'azure_sys']

original_count = len(db['resources'])
db['resources'] = [
    r for r in db['resources']
    if not (
        r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/databases'
        and any(sd in r['name'] for sd in system_dbs)
    )
]
removed = original_count - len(db['resources'])
print(f"Removed {removed} system database resources. Remaining: {len(db['resources'])}")

with open('database.json', 'w') as f:
    json.dump(db, f, indent=4)

print("Done!")
