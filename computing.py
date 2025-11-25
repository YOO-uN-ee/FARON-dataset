import random
import psycopg2
import json
from collections import defaultdict

def generate_spatial_question_from_data_with_postgis(
    data, 
    table_name="geometries",
    name_col="name", 
    geom_col="geom",
    geom_type_col="geom_type" 
):
    """
    Generates a data-driven multi-step question and its PostGIS SQL.
    Includes logic to exclude self-referencing results (e.g., P1 within P1).
    """
    
    sql_functions = {
        "within": "ST_Within({A}, {B})",
        "contain": "ST_Contains({A}, {B})",
        "overlap": "ST_Overlaps({A}, {B})",
        "intersect": "ST_Intersects({A}, {B})",
        "disjoint": "ST_Disjoint({A}, {B})",
        "crosses": "ST_Crosses({A}, {B})"
    }
    
    # --- Pre-process data ---
    relations_of_a = defaultdict(list)
    relations_of_b = defaultdict(list)
    
    for a_info, b_info, rel in data:
        if rel in sql_functions:
            a_key = (a_info[0], a_info[1]) 
            b_key = (b_info[0], b_info[1])
            relations_of_a[a_key].append((b_key, rel))
            relations_of_b[b_key].append((a_key, rel))

    # --- Template 1: Chained Relationship ---
    def template_chained_relationship(template_data):
        possible_b_keys = list(set(relations_of_a.keys()) & set(relations_of_b.keys()))
        if not possible_b_keys:
            return None 

        entity_b_key = random.choice(possible_b_keys)
        entity_a_key, rel_1_name = random.choice(relations_of_b[entity_b_key])
        entity_c_key, rel_2_name = random.choice(relations_of_a[entity_b_key])
        
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key

        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        entity_c_str = f"{id_c}"
        question = (
            f"Which {type_a}s in the image is {rel_1_name} a {type_b} "
            f"that is {rel_2_name} {entity_c_str}?"
        )

        reasoning = [
            f"Step 1: Find all `{type_b}` geometries that `{rel_2_name}` {entity_c_str} (excluding {entity_c_str} itself).",
            f"Step 2: Find all `{type_a}` geometries that `{rel_1_name}` the results from Step 1.",
            "Step 3: Return the distinct names/IDs."
        ]
        
        # SQL UPDATE: Added 'AND T1.{name_col} <> T2.{name_col}' to exclude self-matches
        # Note: We also pull the ID in the CTE now to ensure we can exclude self-matches in the final step if needed,
        # though strictly speaking, simply preventing T2 matches in the Join is often enough. 
        # For simplicity, this version enforces the exclusion on the explicit relationship steps.

        sql = f"""
WITH IntermediateSet AS (
    SELECT T1.{template_data['geom_col']}
    FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
    WHERE
        T1.{template_data['geom_type_col']} = '{type_b}'
        AND T2.{template_data['name_col']} = '{id_c}'
        AND T2.{template_data['geom_type_col']} = '{type_c}'
        AND T1.{template_data['name_col']} <> T2.{template_data['name_col']} 
        AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}
)
SELECT DISTINCT T_Final.{template_data['name_col']}
FROM {template_data['table_name']} AS T_Final, IntermediateSet
WHERE
    T_Final.{template_data['geom_type_col']} = '{type_a}'
    AND {rel_1_sql.format(A='T_Final.' + template_data['geom_col'], B='IntermediateSet.' + template_data['geom_col'])};
        """
        return {"question": question, "reasoning": reasoning, "sql": sql}

    # --- Template 2: Multiple Conditions ---
    def template_multiple_conditions(template_data):
        possible_a_keys = [a for a, rels in template_data['relations_of_a'].items() if len(rels) >= 2]
        if not possible_a_keys:
            return None
            
        entity_a_key = random.choice(possible_a_keys)
        (entity_b_key, rel_1_name), (entity_c_key, rel_2_name) = random.sample(
            template_data['relations_of_a'][entity_a_key], 2
        )
        
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key
        
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        entity_b_str = f"{id_b}"
        entity_c_str = f"{id_c}"
        question = (
            f"Find all {type_a}s that both "
            f"{rel_1_name} {entity_b_str} and "
            f"{rel_2_name} {entity_c_str}."
        )

        reasoning = [
            f"Step 1: Find `{type_a}`s that `{rel_1_name}` {entity_b_str} (excluding self).",
            f"Step 2: Find `{type_a}`s that `{rel_2_name}` {entity_c_str} (excluding self).",
            "Step 3: Find the intersection."
        ]

        # SQL UPDATE: Added 'AND T1.{name_col} <> T2.{name_col}' to both subqueries
        sql = f"""
SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['geom_type_col']} = '{type_a}'
    AND T2.{template_data['name_col']} = '{id_b}'
    AND T2.{template_data['geom_type_col']} = '{type_b}'
    AND T1.{template_data['name_col']} <> T2.{template_data['name_col']} 
    AND {rel_1_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}

INTERSECT

SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['geom_type_col']} = '{type_a}'
    AND T2.{template_data['name_col']} = '{id_c}'
    AND T2.{template_data['geom_type_col']} = '{type_c}'
    AND T1.{template_data['name_col']} <> T2.{template_data['name_col']} 
    AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])};
        """
        return {"question": question, "reasoning": reasoning, "sql": sql}

    # --- Function Body ---
    template_data = {
        "table_name": table_name,
        "name_col": name_col,
        "geom_col": geom_col,
        "geom_type_col": geom_type_col,
        "sql_functions": sql_functions,
        "relations_of_a": relations_of_a,
        "relations_of_b": relations_of_b
    }

    possible_templates = []
    if any(len(rels) >= 2 for rels in relations_of_a.values()):
        possible_templates.append(template_multiple_conditions)
    if (set(relations_of_a.keys()) & set(relations_of_b.keys())):
        possible_templates.append(template_chained_relationship)

    if not possible_templates:
        return {"error": "Could not find any multi-step patterns in the provided data."}

    chosen_template = random.choice(possible_templates)
    result = chosen_template(template_data)
    
    if result and 'sql' in result:
        result['sql'] = "\n".join(
            [Line.strip() for Line in result['sql'].strip().split('\n') if Line.strip()]
        )
    
    return result

# --- Example Usage ---

# Load your relationship data
try:
    with open('./relationship.json', 'r') as file:
        sample_data = json.load(file)
except FileNotFoundError:
    print("Error: relationship.json not found. Using dummy data.")
    # Fallback dummy data
    sample_data = {
        "relationships": [
            [["Polygon", 1], ["Polygon", 5], "within"],
            [["Polygon", 1], ["Line", 7], "intersects"],
            [["Line", 7], ["Point", 3], "within"],
            [["Polygon", 5], ["Point", 9], "contain"]
        ]
    }
except json.JSONDecodeError:
    print("Error: Could not decode relationship.json. Check file format.")
    # Fallback dummy data
    sample_data = {
        "relationships": [
            [["Polygon", 1], ["Polygon", 5], "within"],
            [["Polygon", 1], ["Line", 7], "intersects"],
            [["Line", 7], ["Point", 3], "within"],
            [["Polygon", 5], ["Point", 9], "contain"]
        ]
    }


# Generate the question
generated_data = generate_spatial_question_from_data_with_postgis(
    sample_data["relationships"],
    table_name="generated_geometries",
    name_col="id",    
    geom_col="geom",
    geom_type_col="geom_type" 
)

with open('./question_detail.json', 'w') as f:
    json.dump(generated_data, f, indent=4)

if "error" in generated_data:
    print(generated_data["error"])
else:
    print("Question\n")
    print(generated_data['question'])
    print("\n" + "---" + "\n")

    print("Composition\n")
    for step in generated_data['reasoning']:
        print(f"* {step}")
    print("\n" + "---" + "\n")

    DB_CONFIG = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "jiYOON7162@",
        "host": "localhost",
        "port": "5432"
    }

    QUERY_TO_ANALYZE = generated_data['sql']
    OUTPUT_FILENAME = "query_plan.json"

    sql_explain_query = f"EXPLAIN (ANALYZE, FORMAT JSON) {QUERY_TO_ANALYZE}"

    plan_json = None

    try:
        print(f"Connecting to database '{DB_CONFIG['dbname']}'...")
        with psycopg2.connect(**DB_CONFIG) as conn:
            print("Connection successful.")
            
            with conn.cursor() as cur:
                
                print(f"Executing: {sql_explain_query}")
                cur.execute(sql_explain_query)
                
                plan_result = cur.fetchone()
                
                if plan_result:
                    plan_json = plan_result[0]
                else:
                    print("Error: Could not retrieve an explain plan.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")

    # --- Save to File ---
    if plan_json:
        try:
            print(f"Saving query plan to '{OUTPUT_FILENAME}'...")
            with open(OUTPUT_FILENAME, 'w') as f:
                json.dump(plan_json, f, indent=4)
            
            print(f"Successfully saved query plan to '{OUTPUT_FILENAME}'.")
        except (Exception, IOError) as error:
            print(f"Error writing to file: {error}")

    # print("PostGIS/PostgreSQL Query\n")
    # print("```sql")
    # print("EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)")
    # print(generated_data['sql'])
    # print("```")