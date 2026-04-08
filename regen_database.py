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
        'metadata': {'description': "Optional suffix to make server names globally unique (e.g. '-v2')"}
    }
}

def get_param_key(name_expr):
    """Figure out which server parameter this resource belongs to."""
    if 'flexibleServers_learnmanagement_name' in name_expr:
        return 'flexibleServers_learnmanagement_name'
    if 'flexibleServers_lms_name' in name_expr:
        return 'flexibleServers_lms_name'
    return None

def get_child_part(name_expr):
    """Extract the child resource name part after '/' from original concat expression.
    These are ORIGINAL names like: [concat(parameters('lms'), '/some_child')]
    """
    # Match pattern: '/<child_name>')] at end
    m = re.search(r"'/([^']+)'\]", name_expr)
    if m:
        return m.group(1)
    return None

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
            continue

    # Skip non-whitelisted configs (only skip system-default ones)
    if t == 'Microsoft.DBforPostgreSQL/flexibleServers/configurations':
        source = res.get('properties', {}).get('source', '')
        if source == 'system-default':
            continue
        child = get_child_part(name)
        if child and child not in SAFE_CONFIGS:
            continue

    # Build a clean copy of this resource
    r = dict(res)

    param_key = get_param_key(name)

    if t == 'Microsoft.DBforPostgreSQL/flexibleServers':
        r['name'] = f"[concat(parameters('{param_key}'), parameters('serverNameSuffix'))]"
        # Inject admin password
        r['properties']['administratorLoginPassword'] = "[parameters('administratorLoginPassword')]"

    elif param_key:
        child = get_child_part(name)
        if child:
            r['name'] = f"[concat(parameters('{param_key}'), parameters('serverNameSuffix'), '/{child}')]"
        # Fix dependsOn to reference new server name pattern
        if 'dependsOn' in r:
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

print(f"Regenerated database.json with {len(db_resources)} resources")

# Sanity check: no nested bracket expressions
content = open('database.json').read()
if "'/[" in content or "\"[concat" in content.replace('"[concat(parameters', ''):
    print("WARNING: Possible nested expression detected - verify manually")
else:
    print("Expression sanity check passed OK")

# Count by type
types = {}
for r in db_resources:
    types[r['type']] = types.get(r['type'], 0) + 1
for k, v in sorted(types.items()):
    print(f"  {v}x {k}")
