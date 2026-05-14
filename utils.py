import json
import pandas as pd



def extract_schema_types(schema_dict, current_path="", types_dict=None):
    """
    Recursively parses the schema to map flattened dot-notation paths to their data types.
    Example output: {'documentation.identification.accession_number': 'text', ...}
    """
    if types_dict is None:
        types_dict = {}
        
    # Root level iteration
    if 'groups' in schema_dict:
        for group in schema_dict['groups']:
            extract_schema_types(group, current_path, types_dict)
        return types_dict
        
    # Append the current node's ID to the path
    path = f"{current_path}.{schema_dict['id']}" if current_path else schema_dict['id']
    
    # If the node is a group, recurse into its subgroups
    if schema_dict.get('dataType') == 'group' and 'subgroups' in schema_dict:
        for subgroup in schema_dict['subgroups']:
            extract_schema_types(subgroup, path, types_dict)
    else:
        # Otherwise, save the leaf node's data type
        types_dict[path] = schema_dict.get('dataType')
        
    return types_dict


def flatten_dict(d, parent_key='', sep='.'):
    """Secondary function to recursively flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        # Skip root-level schema metadata to handle them separately
        if k in ['schemaId', 'version']:
            continue
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def set_nested_value(d, keys, value):
    """Secondary function to set a value in a nested dictionary using a list of keys."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def json_to_csv_row(schema, metadata):
    """
    Converts a hierarchical JSON artifact metadata dict into a flat pandas DataFrame.
    """
    # Flatten the hierarchical JSON
    flat_data = flatten_dict(metadata)
    
    # Map out schema types to handle specific conversions (e.g., arrays)
    schema_types = extract_schema_types(schema)
    
    csv_row = {}
    
    # Preserve top-level schema tracking parameters
    csv_row['schemaId'] = metadata.get('schemaId')
    csv_row['version'] = metadata.get('version')
    
    for key, value in flat_data.items():
        # Retain None/Nulls as empty values
        if value is None:
            csv_row[key] = ""
            continue
            
        data_type = schema_types.get(key)
        
        # Convert multienum lists to semicolon-separated strings for CSV storage
        if data_type == 'multienum' and isinstance(value, list):
            csv_row[key] = ";".join(str(v) for v in value)
        elif data_type == 'boolean':
            csv_row[key] = str(value)
        else:
            csv_row[key] = value
            
    return pd.DataFrame([csv_row])


def csv_row_to_json(schema, csv_df):
    """
    Converts a flat pandas DataFrame row back into a hierarchical JSON artifact dict.
    """
    schema_types = extract_schema_types(schema)
    
    # Allow passing either a DataFrame (single row) or directly a dict/Series
    if isinstance(csv_df, pd.DataFrame):
        row = csv_df.iloc[0].to_dict()
    else:
        row = csv_df
        
    metadata = {}
    
    # Restore top-level schema parameters
    if 'schemaId' in row:
        metadata['schemaId'] = row['schemaId']
    if 'version' in row:
        metadata['version'] = int(row['version']) if not pd.isna(row['version']) else 1
        
    for key, value in row.items():
        if key in ['schemaId', 'version']:
            continue
            
        nested_keys = key.split('.')
        
        # Convert missing pandas values (NaN) or empty strings back to JSON null
        if pd.isna(value) or value == "":
            set_nested_value(metadata, nested_keys, None)
            continue
            
        data_type = schema_types.get(key)
        parsed_value = value
        
        # Recover data types distorted by CSV stringification
        if data_type == 'multienum':
            if isinstance(value, str):
                parsed_value = [v.strip() for v in value.split(';') if v.strip()]
        elif data_type == 'boolean':
            if isinstance(value, str):
                parsed_value = value.lower() in ('true', '1', 't', 'yes')
            else:
                parsed_value = bool(value)
        elif data_type == 'float':
            parsed_value = float(value)
            
        set_nested_value(metadata, nested_keys, parsed_value)
        
    return metadata



if __name__ == "__main__":
    """Example usage"""
    
    with open('puc_schema.json', 'r') as f:
        schema = json.load(f)

    with open('puc1_example.json', 'r') as f:
        artifact_metadata = json.load(f)

    # Convert to csv
    df = json_to_csv_row(schema, artifact_metadata)
    df.to_csv('artifact_database.csv', index=False)

    # Convert to json
    restored_json = csv_row_to_json(schema, df)
    with open('artifact_metadata.json', 'w') as f:
        json.dump(restored_json, f)
