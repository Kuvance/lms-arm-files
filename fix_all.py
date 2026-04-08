import json

# WHITELIST approach: ONLY keep these configs - they are safe to set on Azure PG Flexible Server
# Everything else is either read-only, internal, or auto-managed
SAFE_CONFIGS = {
    'shared_preload_libraries',       # Enables pg_cron, pg_stat_statements
    'azure.extensions',               # Azure-specific extensions
    'work_mem',                       # Memory per sort/hash operation
    'maintenance_work_mem',           # Memory for maintenance ops
    'lock_timeout',                   # Lock wait timeout
    'statement_timeout',             # Max statement execution time
    'idle_in_transaction_session_timeout',  # Idle tx timeout
    'log_min_duration_statement',    # Log slow queries
    'log_statement',                  # Which SQL to log
    'pg_stat_statements.track',      # Query tracking level
    'enable_partitionwise_join',
    'enable_partitionwise_aggregate',
    'max_parallel_workers_per_gather',
    'pg_qs.query_capture_mode',
    'pgms_wait_sampling.query_capture_mode',
    'pg_qs.max_query_text_length',
    'timezone',
}

# System databases that Azure auto-creates and cannot be deployed
SYSTEM_DBS = {'azure_maintenance', 'azure_sys'}

with open('database.json', 'r') as f:
    db = json.load(f)

def get_config_key(name_expr):
    # handles: [concat(parameters('...'), '/some_config')]
    parts = name_expr.rstrip("']").split('/')
    return parts[-1] if len(parts) > 1 else name_expr

before = len(db['resources'])

db['resources'] = [
    r for r in db['resources']
    if not (
        # Remove non-whitelisted configs
        (r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
         and get_config_key(r['name']) not in SAFE_CONFIGS)
        or
        # Remove system databases
        (r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/databases'
         and any(sd in r['name'] for sd in SYSTEM_DBS))
    )
]

after = len(db['resources'])
print(f"Removed {before - after} resources. Remaining: {after}")

# Add a uniqueSuffix parameter so server names can be made unique to avoid ServerNameAlreadyExists
db['parameters']['serverNameSuffix'] = {
    "type": "String",
    "defaultValue": "",
    "metadata": {
        "description": "Optional suffix appended to server names to make them globally unique (e.g. '-v2' or '-new'). Leave empty to use original names."
    }
}

# Update server names to include optional suffix
for res in db['resources']:
    t = res['type']
    name = res['name']
    
    if t == 'Microsoft.DBforPostgreSQL/flexibleServers':
        # Update server name to include suffix
        if 'flexibleServers_learnmanagement_name' in name:
            res['name'] = "[concat(parameters('flexibleServers_learnmanagement_name'), parameters('serverNameSuffix'))]"
        elif 'flexibleServers_lms_name' in name:
            res['name'] = "[concat(parameters('flexibleServers_lms_name'), parameters('serverNameSuffix'))]"
    
    elif t in [
        'Microsoft.DBforPostgreSQL/flexibleServers/configurations',
        'Microsoft.DBforPostgreSQL/flexibleServers/databases',
        'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules',
        'Microsoft.DBforPostgreSQL/flexibleServers/administrators',
        'Microsoft.DBforPostgreSQL/flexibleServers/advancedThreatProtectionSettings',
    ]:
        # Update child resource names to include suffix on server part
        if 'flexibleServers_learnmanagement_name' in name:
            config_part = name.split("', '/")[-1].rstrip("')]")
            res['name'] = f"[concat(parameters('flexibleServers_learnmanagement_name'), parameters('serverNameSuffix'), '/{config_part}')]"
        elif 'flexibleServers_lms_name' in name:
            config_part = name.split("', '/")[-1].rstrip("')]")
            res['name'] = f"[concat(parameters('flexibleServers_lms_name'), parameters('serverNameSuffix'), '/{config_part}')]"

with open('database.json', 'w') as f:
    json.dump(db, f, indent=4)

# Update main.json to pass the suffix parameter
with open('main.json', 'r') as f:
    main_tmpl = json.load(f)

main_tmpl['parameters']['serverNameSuffix'] = {
    "type": "String",
    "defaultValue": "",
    "metadata": {
        "description": "Optional suffix to make server names globally unique."
    }
}

for res in main_tmpl['resources']:
    if res['name'] == 'databaseDeployment':
        res['properties']['parameters']['serverNameSuffix'] = {
            "value": "[parameters('serverNameSuffix')]"
        }

with open('main.json', 'w') as f:
    json.dump(main_tmpl, f, indent=4)

print("Done!")
print()
print("IMPORTANT: If you get ServerNameAlreadyExists again, deploy with:")
print("  serverNameSuffix = \"-v2\"")
print("This will create servers named 'lms-v2' and 'learnmanagement-v2'")
