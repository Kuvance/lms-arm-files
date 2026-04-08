import json
import re

# WHITELIST: only these PostgreSQL configs are safe to set on Azure PaaS
SAFE_CONFIGS = {
    'shared_preload_libraries',
    'azure.extensions',
    'work_mem',
    'maintenance_work_mem',
    'lock_timeout',
    'statement_timeout',
    'idle_in_transaction_session_timeout',
    'log_min_duration_statement',
    'log_statement',
    'pg_stat_statements.track',
    'enable_partitionwise_join',
    'enable_partitionwise_aggregate',
    'max_parallel_workers_per_gather',
    'pg_qs.query_capture_mode',
    'pgms_wait_sampling.query_capture_mode',
    'pg_qs.max_query_text_length',
    'timezone',
}

SYSTEM_DBS = {'azure_maintenance', 'azure_sys'}

CHILD_TYPES = [
    'Microsoft.DBforPostgreSQL/flexibleServers/configurations',
    'Microsoft.DBforPostgreSQL/flexibleServers/databases',
    'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules',
    'Microsoft.DBforPostgreSQL/flexibleServers/administrators',
    'Microsoft.DBforPostgreSQL/flexibleServers/advancedThreatProtectionSettings',
]

def extract_child_name(name_expr):
    """Extract the child resource name part (after /) from a concat expression."""
    # Matches the part between the last '/' and the closing quote
    # e.g. [concat(parameters('lms'), '/some_config')] -> some_config
    match = re.search(r"'/([^']+)'", name_expr)
    if match:
        return match.group(1)
    return None

def get_config_key(name_expr):
    """Get just the config name (last part after slash)."""
    child = extract_child_name(name_expr)
    if child:
        return child.split('/')[-1]
    return name_expr

with open('database.json', 'r') as f:
    db = json.load(f)

# Filter out non-whitelisted configs and system databases
before = len(db['resources'])

db['resources'] = [
    r for r in db['resources']
    if not (
        (r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
         and get_config_key(r['name']) not in SAFE_CONFIGS)
        or
        (r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/databases'
         and any(sd in r['name'] for sd in SYSTEM_DBS))
    )
]

after = len(db['resources'])
print(f"Filtered: removed {before - after}, remaining {after}")

# Add serverNameSuffix parameter if not already there
if 'serverNameSuffix' not in db['parameters']:
    db['parameters']['serverNameSuffix'] = {
        "type": "String",
        "defaultValue": "",
        "metadata": {
            "description": "Optional suffix to make server names globally unique (e.g. '-v2'). Leave empty to use original names."
        }
    }

# Fix resource names: rebuild using correct ARM expressions
for res in db['resources']:
    t = res['type']
    name = res['name']

    if t == 'Microsoft.DBforPostgreSQL/flexibleServers':
        if 'flexibleServers_learnmanagement_name' in name:
            param = 'flexibleServers_learnmanagement_name'
        else:
            param = 'flexibleServers_lms_name'
        res['name'] = f"[concat(parameters('{param}'), parameters('serverNameSuffix'))]"

    elif t in CHILD_TYPES:
        child_part = extract_child_name(name)
        if child_part:
            if 'flexibleServers_learnmanagement_name' in name:
                param = 'flexibleServers_learnmanagement_name'
            else:
                param = 'flexibleServers_lms_name'
            res['name'] = f"[concat(parameters('{param}'), parameters('serverNameSuffix'), '/{child_part}')]"
        # else leave unchanged

with open('database.json', 'w') as f:
    json.dump(db, f, indent=4)

# Verify no double-bracket expressions were created
content = open('database.json').read()
if "'[concat" in content:
    print("WARNING: Nested expression detected! Check database.json")
else:
    print("Name expressions look clean.")

print("Done!")
