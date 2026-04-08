import json
import re

# Regenerate database.json cleanly from the original template

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

DB_TYPES = {
    'Microsoft.DBforPostgreSQL/flexibleServers',
    'Microsoft.DBforPostgreSQL/flexibleServers/configurations',
    'Microsoft.DBforPostgreSQL/flexibleServers/databases',
    'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules',
    'Microsoft.DBforPostgreSQL/flexibleServers/administrators',
    'Microsoft.DBforPostgreSQL/flexibleServers/advancedThreatProtectionSettings',
}

def get_param_key(name_expr):
    if 'flexibleServers_learnmanagement_name' in name_expr:
        return 'flexibleServers_learnmanagement_name'
    if 'flexibleServers_lms_name' in name_expr:
        return 'flexibleServers_lms_name'
    return None

def get_child_part(name_expr):
    """
    Extract child resource name from original ARM concat expression.
    Handles: [concat(parameters('server'), '/child_name')]
    The fix: use '/([^']+)' without requiring ']' immediately after quote.
    """
    m = re.search(r"'/([^']+)'", name_expr)
    if m:
        return m.group(1)
    return None

# Read original source of truth
with open('template.json', 'r') as f:
    original = json.load(f)

original_params = original.get('parameters', {})
all_resources = original.get('resources', [])

# Build database.json parameters
params = {
    'flexibleServers_lms_name': original_params['flexibleServers_lms_name'],
    'flexibleServers_learnmanagement_name': original_params['flexibleServers_learnmanagement_name'],
    'administratorLoginPassword': {
        'type': 'secureString',
        'metadata': {'description': 'PostgreSQL administrator password'}
    },
    'serverNameSuffix': {
        'type': 'String',
        'defaultValue': '',
        'metadata': {'description': "Optional suffix for globally unique server names (e.g. '-v2')"}
    }
}

db_resources = []

for res in all_resources:
    t = res.get('type', '')
    name = res.get('name', '')

    if t not in DB_TYPES:
        continue

    # Skip backups
    if 'backups' in t:
        continue

    # Skip system databases
    if t == 'Microsoft.DBforPostgreSQL/flexibleServers/databases':
        child = get_child_part(name)
        if child and any(sd in child for sd in SYSTEM_DBS):
            print(f"  Skipping system DB: {child}")
            continue

    # Apply whitelist to configurations
    if t == 'Microsoft.DBforPostgreSQL/flexibleServers/configurations':
        source = res.get('properties', {}).get('source', '')
        if source == 'system-default':
            continue
        child = get_child_part(name)
        if child is None:
            # Can't parse name - skip to be safe
            print(f"  Skipping unparseable config: {name}")
            continue
        if child not in SAFE_CONFIGS:
            continue

    # Build a clean copy
    r = json.loads(json.dumps(res))  # deep copy
    param_key = get_param_key(name)

    if t == 'Microsoft.DBforPostgreSQL/flexibleServers':
        r['name'] = f"[concat(parameters('{param_key}'), parameters('serverNameSuffix'))]"
        r['properties']['administratorLoginPassword'] = "[parameters('administratorLoginPassword')]"

    elif param_key:
        child = get_child_part(name)
        if child:
            # Child name uses suffix to match parent server
            r['name'] = f"[concat(parameters('{param_key}'), parameters('serverNameSuffix'), '/{child}')]"
            # Update dependsOn
            r['dependsOn'] = [
                f"[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', concat(parameters('{param_key}'), parameters('serverNameSuffix')))]"
            ]

    db_resources.append(r)

db_template = {
    '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#',
    'contentVersion': '1.0.0.0',
    'parameters': params,
    'variables': {},
    'resources': db_resources
}

with open('database.json', 'w') as f:
    json.dump(db_template, f, indent=4)

print(f"\nFinal database.json: {len(db_resources)} resources")

# Sanity check: ensure suffix is in all child names
content = open('database.json').read()
problems = []
for r in db_resources:
    if r['type'] != 'Microsoft.DBforPostgreSQL/flexibleServers':
        if 'serverNameSuffix' not in r['name']:
            problems.append(r['name'])

if problems:
    print("PROBLEMS - these names are missing serverNameSuffix:")
    for p in problems:
        print(f"  {p}")
else:
    print("All child resource names include serverNameSuffix - OK")

# Type summary
types = {}
for r in db_resources:
    types[r['type']] = types.get(r['type'], 0) + 1
for k, v in sorted(types.items()):
    print(f"  {v}x {k.split('/')[-1]}")
