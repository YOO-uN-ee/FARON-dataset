# import random
# import json
# from collections import defaultdict

# def get_type(entity_name):
#     """Extracts the type (POLYGON, LINE, POINT) from a name.
#     TODO: Change it to Shapely so that SQL not rely on name but on shape form?
#     TODO: Or add category that is polygon, line, point when generating"""
#     return entity_name.split('_')[0]

# def generate_spatial_question_from_data_with_postgis(
#     data, 
#     table_name="geometries", 
#     name_col="name", 
#     geom_col="geom"
# ):
#     """
#     Generates a data-driven multi-step question and its PostGIS SQL.
    
#     Args:
#         data (list): A list of relationships
#         table_name (str): Name of the geometry table.
#         name_col (str): Name of the name/ID column.
#         geom_col (str): Name of the geometry column.
#     """
    
#     sql_functions = {
#         "within": "ST_Within({A}, {B})",
#         "contain": "ST_Contains({A}, {B})",
#         "overlap": "ST_Overlaps({A}, {B})",
#         "intersect": "ST_Intersects({A}, {B})",
#         "disjoint": "ST_Disjoint({A}, {B})",
#         "crosses": "ST_Crosses({A}, {B})"
#     }
    
#     relations_of_a = defaultdict(list)
#     relations_of_b = defaultdict(list)
    
#     for a, b, rel in data:
#         if rel in sql_functions:
#             relations_of_a[a].append((b, rel))
#             relations_of_b[b].append((a, rel))

#     def template_chained_relationship(template_data):
#         """
#         Find chain: A -> [Rel1] -> B -> [Rel2] -> C
#         Generates question: Find A that [Rel1] B, where B [Rel2] C.
#         """
#         # Find a valid chain (A -> B -> C)
#         # B object in at leat one relation and a subject in one other
#         possible_b = list(set(relations_of_a.keys()) & set(relations_of_b.keys()))
#         if not possible_b:
#             return None # No chains found

#         entity_b = random.choice(possible_b)
        
#         # Find A -> Rel1 -> B
#         entity_a, rel_1_name = random.choice(relations_of_b[entity_b])
        
#         # Find B -> Rel2 -> C
#         entity_c, rel_2_name = random.choice(relations_of_a[entity_b])
        
#         # Get types
#         type_a = get_type(entity_a)
#         type_b = get_type(entity_b)

#         # Get SQL functions
#         rel_1_sql = template_data['sql_functions'][rel_1_name]
#         rel_2_sql = template_data['sql_functions'][rel_2_name]

#         # Build Question
#         question = (
#             f"Which {type_a}s in the database {rel_1_name} the {type_b} "
#             f"that is {rel_2_name} {entity_c}?"
#         )

#         # Build Reasoning
#         reasoning = [
#             f"Step 1 (Intermediate Set): Find all `{type_b}` geometries that "
#             f"`{rel_2_name}` (`{rel_2_sql.format(A='..', B='..')}`) '{entity_c}'.",
            
#             f"Step 2 (Final Set): Find all `{type_a}` geometries that "
#             f"`{rel_1_name}` (`{rel_1_sql.format(A='..', B='..')}`) "
#             f"intermediate set.",
            
#             "Step 3: Return the distinct names of these final geometries."
#         ]
        
#         # Build SQL
#         sql = f"""
# WITH IntermediateSet AS (
#     SELECT T1.{template_data['geom_col']}
#     FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
#     WHERE
#         T1.{template_data['name_col']} LIKE '{type_b}_%'
#         AND T2.{template_data['name_col']} = '{entity_c}'
#         AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}
# )
# SELECT DISTINCT T_Final.{template_data['name_col']}
# FROM {template_data['table_name']} AS T_Final, IntermediateSet
# WHERE
#     T_Final.{template_data['name_col']} LIKE '{type_a}_%'
#     AND {rel_1_sql.format(A='T_Final.' + template_data['geom_col'], B='IntermediateSet.' + template_data['geom_col'])};
#         """
#         return {"question": question, "reasoning": reasoning, "sql": sql}

#     def template_multiple_conditions(template_data):
#         """
#         Finds a real entity A that has two+ relations:
#         A -> Rel1 -> B
#         A -> Rel2 -> C
#         Generates question: Find A that [Rel1] B AND [Rel2] C.
#         """
#         possible_a = [a for a, rels in template_data['relations_of_a'].items() if len(rels) >= 2]
#         if not possible_a:
#             return None
            
#         entity_a = random.choice(possible_a)
        
#         (entity_b, rel_1_name), (entity_c, rel_2_name) = random.sample(
#             template_data['relations_of_a'][entity_a], 2
#         )
        
#         # Get types and SQL
#         type_a = get_type(entity_a)
#         rel_1_sql = template_data['sql_functions'][rel_1_name]
#         rel_2_sql = template_data['sql_functions'][rel_2_name]

#         # Build Question
#         question = (
#             f"Find all {type_a}s that both "
#             f"{rel_1_name} '{entity_b}' AND "
#             f"{rel_2_name} '{entity_c}'."
#         )

#         # Build Reasoning
#         reasoning = [
#             f"Step 1: Find the set of all `{type_a}`s that `{rel_1_name}` "
#             f"(using `{rel_1_sql.format(A='..', B='..')}`) '{entity_b}'.",
#             f"Step 2: Find the set of all `{type_a}`s that `{rel_2_name}` "
#             f"(using `{rel_2_sql.format(A='..', B='..')}`) '{entity_c}'.",
#             "Step 3: Find the common geometries (the intersection) "
#             "between the sets from Step 1 and Step 2."
#         ]
        
#         sql = f"""
# SELECT T1.{template_data['name_col']}
# FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
# WHERE
#     T1.{template_data['name_col']} LIKE '{type_a}_%'
#     AND T2.{template_data['name_col']} = '{entity_b}'
#     AND {rel_1_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}

# INTERSECT
# SELECT T1.{template_data['name_col']}
# FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
# WHERE
#     T1.{template_data['name_col']} LIKE '{type_a}_%'
#     AND T2.{template_data['name_col']} = '{entity_c}'
#     AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])};
#         """
#         return {"question": question, "reasoning": reasoning, "sql": sql}

#     template_data = {
#         "table_name": table_name,
#         "name_col": name_col,
#         "geom_col": geom_col,
#         "sql_functions": sql_functions,
#         "relations_of_a": relations_of_a,
#         "relations_of_b": relations_of_b
#     }

#     # Find which templates are possible with the given data
#     possible_templates = []
    
#     # Check for multi-condition patterns
#     if any(len(rels) >= 2 for rels in relations_of_a.values()):
#         possible_templates.append(template_multiple_conditions)
        
#     # Check for chained-relationship patterns
#     if (set(relations_of_a.keys()) & set(relations_of_b.keys())):
#         possible_templates.append(template_chained_relationship)


#     if not possible_templates:
#         return {"error": "Could not find any multi-step patterns in the provided data."}

#     # Pick a random possible template and run it
#     chosen_template = random.choice(possible_templates)
#     result = chosen_template(template_data)
    
#     # Clean up SQL formatting
#     if result and 'sql' in result:
#         result['sql'] = "\n".join(
#             [line.strip() for line in result['sql'].strip().split('\n') if line.strip()]
#         )
    
#     return result









# with open('./relationship.json', 'r') as file:
#     sample_data = json.load(file)

# generated_data = generate_spatial_question_from_data_with_postgis(
#     sample_data["relationships"],
#     table_name="generated_geometries", 
#     name_col="id",      # All unique
#     geom_col="geom",
#     geom_type_col="geom_type",
# )

# if "error" in generated_data:
#     print(generated_data["error"])
# else:
#     print("Question\n")
#     print(generated_data['question'])
#     print("\n" + "---" + "\n")

#     print("Composition\n")
#     for step in generated_data['reasoning']:
#         print(f"* {step}")
#     print("\n" + "---" + "\n")

#     print("PostGIS/PostgreSQL Query\n")
#     print("```sql")
#     print("EXPLAIN ANALYZE")
#     print(generated_data['sql'])
#     print("```")


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
    
    Args:
        data (list): A list of relationships in the new format, e.g.,
                     [["POLYGON", 1], ["POLYGON", 3], "touches"]
        table_name (str): Name of the geometry table.
        name_col (str): Name of the name/ID column (for the integer ID).
        geom_col (str): Name of the geometry column.
        geom_type_col (str): Name of the geometry type column (e.g., 'POLYGON').
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
            # a_key = (type, id) -> ('POLYGON', 1)
            a_key = (a_info[0], a_info[1]) 
            # b_key = (type, id) -> ('POLYGON', 3)
            b_key = (b_info[0], b_info[1])
            
            relations_of_a[a_key].append((b_key, rel))
            relations_of_b[b_key].append((a_key, rel))

    # --- Template 1: Chained Relationship ---
    def template_chained_relationship(template_data):
        """
        Find chain: A -> [Rel1] -> B -> [Rel2] -> C
        Generates question: Find A that [Rel1] B, where B [Rel2] C.
        """
        possible_b_keys = list(set(relations_of_a.keys()) & set(relations_of_b.keys()))
        if not possible_b_keys:
            return None # No chains found

        # entity_b_key is a tuple: ('POLYGON', 5)
        entity_b_key = random.choice(possible_b_keys)
        
        # entity_a_key: (('POLYGON', 1), 'overlaps')
        entity_a_key, rel_1_name = random.choice(relations_of_b[entity_b_key])
        
        # entity_c_key: (('POINT', 3), 'contain')
        entity_c_key, rel_2_name = random.choice(relations_of_a[entity_b_key])
        
        # Get types and IDs
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key

        # Get SQL functions
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        # Build Question
        entity_c_str = f"the {type_c} with ID {id_c}"
        question = (
            f"Which **{type_a}s** in the database **{rel_1_name}** a **{type_b}** "
            f"that, in turn, **{rel_2_name}** **{entity_c_str}**?"
        )

        # Build Reasoning
        reasoning = [
            f"**Step 1 (Intermediate Set):** Find all `{type_b}` geometries that "
            f"`{rel_2_name}` (using `{rel_2_sql.format(A='..', B='..')}`) {entity_c_str}.",
            f"**Step 2 (Final Set):** Find all `{type_a}` geometries that "
            f"`{rel_1_name}` (using `{rel_1_sql.format(A='..', B='..')}`) any of the geometries "
            f"from the intermediate set.",
            "**Step 3:** Return the distinct names/IDs of these final geometries."
        ]
        
        # Build SQL
            # -- Step 1: Find all {type_b}s that {rel_2_name} {entity_c_str}
        # -- Step 2: Find all {type_a}s that {rel_1_name} an entity from Step 1


        sql = f"""
WITH IntermediateSet AS (
    SELECT T1.{template_data['geom_col']}
    FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
    WHERE
        T1.{template_data['geom_type_col']} = '{type_b}'
        AND T2.{template_data['name_col']} = {id_c}
        AND T2.{template_data['geom_type_col']} = '{type_c}'
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
        """
        Finds a real entity A that has two+ relations:
        A -> Rel1 -> B
        A -> Rel2 -> C
        Generates question: Find A that [Rel1] B AND [Rel2] C.
        """
        possible_a_keys = [a for a, rels in template_data['relations_of_a'].items() if len(rels) >= 2]
        if not possible_a_keys:
            return None
            
        entity_a_key = random.choice(possible_a_keys)
        
        (entity_b_key, rel_1_name), (entity_c_key, rel_2_name) = random.sample(
            template_data['relations_of_a'][entity_a_key], 2
        )
        
        # Get types and IDs
        type_a, id_a = entity_a_key
        type_b, id_b = entity_b_key
        type_c, id_c = entity_c_key
        
        # Get SQL
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        # Build Question
        entity_b_str = f"the {type_b} with ID {id_b}"
        entity_c_str = f"the {type_c} with ID {id_c}"
        question = (
            f"Find all **{type_a}s** that both "
            f"**{rel_1_name}** **{entity_b_str}** AND "
            f"**{rel_2_name}** **{entity_c_str}**."
        )

        # Build Reasoning
        reasoning = [
            f"**Step 1:** Find the set of all `{type_a}`s that `{rel_1_name}` "
            f"(using `{rel_1_sql.format(A='..', B='..')}`) {entity_b_str}.",
            f"**Step 2:** Find the set of all `{type_a}`s that `{rel_2_name}` "
            f"(using `{rel_2_sql.format(A='..', B='..')}`) {entity_c_str}.",
            "**Step 3:** Find the common geometries (the intersection) "
            "between the sets from Step 1 and Step 2."
        ]
        
#         -- Step 1: Find {type_a}s that {rel_1_name} {entity_b_str}
# -- Step 2: Find {type_a}s that {rel_2_name} {entity_c_str}

        # Build SQL
        sql = f"""
SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['geom_type_col']} = '{type_a}'
    AND T2.{template_data['name_col']} = {id_b}
    AND T2.{template_data['geom_type_col']} = '{type_b}'
    AND {rel_1_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}

INTERSECT

SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['geom_type_col']} = '{type_a}'
    AND T2.{template_data['name_col']} = {id_c}
    AND T2.{template_data['geom_type_col']} = '{type_c}'
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

    # Find which templates are possible with the given data
    possible_templates = []
    
    if any(len(rels) >= 2 for rels in relations_of_a.values()):
        possible_templates.append(template_multiple_conditions)
        
    if (set(relations_of_a.keys()) & set(relations_of_b.keys())):
        possible_templates.append(template_chained_relationship)

    if not possible_templates:
        return {"error": "Could not find any multi-step patterns in the provided data."}

    # Pick a random possible template and run it
    chosen_template = random.choice(possible_templates)
    result = chosen_template(template_data)
    
    # Clean up SQL formatting
    if result and 'sql' in result:
        result['sql'] = "\n".join(
            [line.strip() for line in result['sql'].strip().split('\n') if line.strip()]
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
            [["POLYGON", 1], ["POLYGON", 5], "within"],
            [["POLYGON", 1], ["LINE", 7], "intersects"],
            [["LINE", 7], ["POINT", 3], "within"],
            [["POLYGON", 5], ["POINT", 9], "contain"]
        ]
    }
except json.JSONDecodeError:
    print("Error: Could not decode relationship.json. Check file format.")
    # Fallback dummy data
    sample_data = {
        "relationships": [
            [["POLYGON", 1], ["POLYGON", 5], "within"],
            [["POLYGON", 1], ["LINE", 7], "intersects"],
            [["LINE", 7], ["POINT", 3], "within"],
            [["POLYGON", 5], ["POINT", 9], "contain"]
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