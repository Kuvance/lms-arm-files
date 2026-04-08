import json
import re

def get_used_parameters(resource, all_parameters_keys):
    s = json.dumps(resource)
    used = set()
    for p in all_parameters_keys:
        if f"parameters('{p}')" in s:
            used.add(p)
    return used

def read_template():
    with open('template.json', 'r') as f:
        return json.load(f)

def write_template(filename, resources, original_parameters, main=False):
    template = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "variables": {},
        "resources": resources
    }
    
    used_params = set()
    for r in resources:
        used_params.update(get_used_parameters(r, original_parameters.keys()))
        
        # strip dependsOn for resources not in this file to avoid conflicts
        if 'dependsOn' in r:
            valid_depends = []
            types_in_file = set([res['type'] for res in resources])
            for dep in r['dependsOn']:
                match = re.search(r"resourceId\('([^']+)'", dep)
                if match:
                    dep_type = match.group(1)
                    if dep_type in types_in_file:
                        valid_depends.append(dep)
                else:
                    valid_depends.append(dep)
                    
            if valid_depends:
                r['dependsOn'] = valid_depends
            else:
                del r['dependsOn']
            
    for p in used_params:
        template['parameters'][p] = original_parameters[p]
        
    if not main:
        with open(filename, 'w') as f:
            json.dump(template, f, indent=4)
    return template

def main():
    data = read_template()
    original_params = data.get('parameters', {})
    resources = data.get('resources', [])
    
    core_res = []
    db_res = []
    app_res = []
    opt_res = []
    
    for r in resources:
        t = r['type']
        
        # filtering backups and default configs
        if 'backups' in t:
            continue
            
        if 'configurations' in t:
            source = r.get('properties', {}).get('source', '')
            if source == 'system-default':
                continue
            
        # Grouping
        if 'registries/scopeMaps' in t:
            opt_res.append(r)
        elif 'ContainerRegistry' in t or 'Network' in t:
            core_res.append(r)
        elif 'DBforPostgreSQL' in t:
            db_res.append(r)
        elif 'App/containerapps' in t or 'managedEnvironments' in t:
            app_res.append(r)
        else:
            opt_res.append(r)
            
    write_template('core-infra.json', core_res, original_params)
    write_template('database.json', db_res, original_params)
    write_template('container-apps.json', app_res, original_params)
    write_template('optional-support.json', opt_res, original_params)
    
    main_resources = []
    main_params = original_params.copy()
    main_params['_artifactsLocation'] = {
        "type": "string",
        "defaultValue": "https://raw.githubusercontent.com/user/repo/main/templates/",
        "metadata": {
            "description": "Base URI where templates are stored."
        }
    }
    main_params.pop('managedEnvironments_managedEnvironment_eventresource_9067_externalid', None)
    
    def nested_deployment(target_file, name, depends_on_names=[]):
        target_template = json.load(open(target_file, 'r'))
        target_params = target_template.get('parameters', {})
        param_values = {}
        for k in target_params.keys():
            if k in main_params:
                param_values[k] = {"value": f"[parameters('{k}')]"}
            elif k == 'managedEnvironments_managedEnvironment_eventresource_9067_externalid':
                # hardcode or handle specifically if needed
                pass
                
        depends = []
        for d in depends_on_names:
            depends.append(f"[resourceId('Microsoft.Resources/deployments', '{d}')]")
            
        return {
            "type": "Microsoft.Resources/deployments",
            "apiVersion": "2021-04-01",
            "name": name,
            "dependsOn": depends,
            "properties": {
                "mode": "Incremental",
                "templateLink": {
                    "uri": f"[uri(parameters('_artifactsLocation'), '{target_file}')]",
                    "contentVersion": "1.0.0.0"
                },
                "parameters": param_values
            }
        }
        
    main_resources.append(nested_deployment('core-infra.json', 'coreInfraDeployment'))
    main_resources.append(nested_deployment('database.json', 'databaseDeployment', ['coreInfraDeployment']))
    main_resources.append(nested_deployment('container-apps.json', 'containerAppsDeployment', ['databaseDeployment']))
    main_resources.append(nested_deployment('optional-support.json', 'optionalSupportDeployment', ['coreInfraDeployment']))
    
    main_template = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": main_params,
        "variables": {},
        "resources": main_resources
    }
    with open('main.json', 'w') as f:
        json.dump(main_template, f, indent=4)
        
    print(f"Core: {len(core_res)}, DB: {len(db_res)}, Apps: {len(app_res)}, Opt: {len(opt_res)}")
    print("Done")

if __name__ == '__main__':
    main()
