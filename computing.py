import random
import psycopg2
import json
from collections import defaultdict

def generate_spatial_question_from_data_with_postgis(
    data, 
    table_name="geometries",
    name_col="name", 
    geom_col="geom",
    geom_type_col="geom_type",
    tolerance=1.0 # Allow 1 unit (pixel/meter) gap for "aligned"
):
    """
    Generates a question/SQL pair using robust spatial predicates 
    (ST_Covers instead of ST_Within, ST_DWithin instead of ST_Touches).
    """
    
    # --- 1. ROBUST SQL MAPPINGS ---
    # ST_Covers: Returns TRUE even if the point is on the boundary line (ST_Within returns FALSE there).
    # ST_DWithin: Returns TRUE if geometries are within 'tolerance' distance (handles gaps).
    sql_functions = {
        "within": "ST_Covers({B}, {A})", # Note: ST_Covers(Polygon, Point) -> Polygon covers Point
        "contain": "ST_Covers({A}, {B})",
        "overlap": "ST_Overlaps({A}, {B})",
        "intersect": "ST_Intersects({A}, {B})",
        "disjoint": "ST_Disjoint({A}, {B})",
        "crosses": "ST_Crosses({A}, {B})",
        "borders": f"ST_DWithin({{A}}, {{B}}, {tolerance})" # Fuzzy matching for borders
    }
    
    SYMMETRIC_RELATIONS = ["borders", "intersect", "overlap", "disjoint", "crosses", "touches"]

    # --- Pre-process data ---
    relations_of_a = defaultdict(list)
    relations_of_b = defaultdict(list)
    
    for a_info, b_info, rel in data:
        if rel in sql_functions:
            a_key = (a_info[0], a_info[1]) 
            b_key = (b_info[0], b_info[1])
            
            relations_of_a[a_key].append((b_key, rel))
            relations_of_b[b_key].append((a_key, rel))

            if rel in SYMMETRIC_RELATIONS:
                relations_of_a[b_key].append((a_key, rel))
                relations_of_b[a_key].append((b_key, rel))

    # --- Template 1: Chained Relationship ---
    def template_chained_relationship(template_data):
        possible_b_keys = list(set(relations_of_a.keys()) & set(relations_of_b.keys()))
        if not possible_b_keys: return None 

        random.shuffle(possible_b_keys)
        entity_b_key = random.choice(possible_b_keys)
        
        # Ensure valid links exist
        if not relations_of_b[entity_b_key] or not relations_of_a[entity_b_key]: return None

        entity_a_key, rel_1_name = random.choice(relations_of_b[entity_b_key])
        entity_c_key, rel_2_name = random.choice(relations_of_a[entity_b_key])
        
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key

        if id_a == id_c: return None

        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]
        
        entity_c_str = f"{id_c}"
        question = f"Which {type_a}s in the image are {rel_1_name} a {type_b} that is {rel_2_name} with {entity_c_str}?"
        
        # Cleanup Text
        question = question.replace("is borders with", "borders") 
        question = question.replace("is within", "are within")

        reasoning = [
            f"Step 1: Find `{type_b}` geometries that match `{rel_2_name}` with {entity_c_str}.",
            f"Step 2: Find `{type_a}` geometries that match `{rel_1_name}` with the results from Step 1.",
        ]
        
        # --- SQL FIX: Robust JOINs ---
        # 1. We use ST_Covers instead of ST_Within to catch boundary cases.
        # 2. We use ST_DWithin for alignment to catch gap cases.
        # 3. We filter T_Bridge.name <> T_Target.name to avoid self-matches.
        
        sql = f"""
SELECT T_Final.{template_data['name_col']}
FROM {template_data['table_name']} AS T_Final
JOIN {template_data['table_name']} AS T_Bridge 
  ON {rel_1_sql.format(A='T_Final.' + template_data['geom_col'], B='T_Bridge.' + template_data['geom_col'])}
JOIN {template_data['table_name']} AS T_Target 
  ON {rel_2_sql.format(A='T_Bridge.' + template_data['geom_col'], B='T_Target.' + template_data['geom_col'])}
WHERE
    T_Final.{template_data['geom_type_col']} = '{type_a}'
    AND T_Bridge.{template_data['geom_type_col']} = '{type_b}'
    AND T_Target.{template_data['name_col']} = '{id_c}'
    AND T_Target.{template_data['geom_type_col']} = '{type_c}'
    AND T_Bridge.{template_data['name_col']} <> T_Target.{template_data['name_col']}
    AND T_Final.{template_data['name_col']} <> T_Bridge.{template_data['name_col']};
"""
        return {"question": question, "reasoning": reasoning, "sql": sql}

    # --- Template 2: Multiple Conditions (Intersection) ---
    def template_multiple_conditions(template_data):
        possible_a_keys = [a for a, rels in template_data['relations_of_a'].items() if len(rels) >= 2]
        if not possible_a_keys: return None
            
        entity_a_key = random.choice(possible_a_keys)
        (entity_b_key, rel_1_name), (entity_c_key, rel_2_name) = random.sample(
            template_data['relations_of_a'][entity_a_key], 2
        )
        
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key
        
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        question = f"Find all {type_a}s that both {rel_1_name} {id_b} and {rel_2_name} {id_c}."

        reasoning = [
            f"Step 1: Find `{type_a}`s that `{rel_1_name}` {id_b}.",
            f"Step 2: Find `{type_a}`s that `{rel_2_name}` {id_c}.",
            "Step 3: Return the intersection of these two sets."
        ]

        # Use Standard JOINs combined with AND logic (often faster and cleaner than INTERSECT for simple IDs)
        sql = f"""
SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1
JOIN {template_data['table_name']} AS T2 ON {rel_1_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}
JOIN {template_data['table_name']} AS T3 ON {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T3.' + template_data['geom_col'])}
WHERE
    T1.{template_data['geom_type_col']} = '{type_a}'
    AND T2.{template_data['name_col']} = '{id_b}'
    AND T3.{template_data['name_col']} = '{id_c}'
    AND T1.{template_data['name_col']} <> T2.{template_data['name_col']}
    AND T1.{template_data['name_col']} <> T3.{template_data['name_col']};
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
        return {"error": "No multi-step patterns found."}

    # Retry logic
    result = None
    for _ in range(20): 
        chosen_template = random.choice(possible_templates)
        result = chosen_template(template_data)
        if result: break
            
    if not result:
        return {"error": "Logic failed to generate a valid question."}

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