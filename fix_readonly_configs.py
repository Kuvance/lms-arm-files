import json

# These are read-only or auto-computed by Azure - cannot be set via ARM
READONLY_CONFIGS = {
    'server_version',
    'server_version_num',
    'shared_memory_size',
    'shared_memory_size_in_huge_pages',
    'ssl_ca_file',
    'ssl_cert_file',
    'ssl_key_file',
    'ssl_ciphers',         # Managed by Azure internally
    'listen_addresses',    # Internal socket config
    'log_file_mode',       # Internal file permission
    'unix_socket_directories',   # Internal socket path
    'unix_socket_permissions',   # Internal socket permission
    'lc_messages',         # Locale - often read-only in PaaS
    'lc_monetary',
    'lc_numeric',
    'lc_time',
    'server_encoding',     # Set at init time only
    'log_timezone',        # Managed by Azure infra
}

with open('database.json', 'r') as f:
    db = json.load(f)

before = len(db['resources'])

def get_config_key(name_expr):
    # Extract the config name from concat expression
    # e.g. "[concat(parameters('flexibleServers_lms_name'), '/ssl_ca_file')]"
    if '/' in name_expr:
        return name_expr.split('/')[-1].rstrip("')]")
    return name_expr

db['resources'] = [
    r for r in db['resources']
    if not (
        r['type'] == 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
        and get_config_key(r['name']) in READONLY_CONFIGS
    )
]

after = len(db['resources'])
print(f"Removed {before - after} read-only configuration resources. Remaining: {after}")

with open('database.json', 'w') as f:
    json.dump(db, f, indent=4)

print("Done!")
